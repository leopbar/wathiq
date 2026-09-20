"""The work each process step does.

One function per step, and **both engines call these same functions**. Conductor's workers call
them when a task is polled; the in-process engine calls them in order. That is what makes the
fallback trustworthy: it is not a second implementation of the business process, it is the same
steps with a different scheduler.

Three properties every function here has, because a process engine will retry:

* it takes only identifiers and plain values, never objects, so a task payload can be JSON;
* it can be called again without doing its work twice;
* it records what it did in the append-only event log before it returns.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.agent import runner
from app.db import models
from app.db.enums import ActorType, CaseStatus, FindingStatus
from app.db.session import SessionLocal
from app.process import base, definition
from app.services import audit_trail, escalation, posting
from app.services.events import record_event

logger = logging.getLogger(__name__)


class ProcessStepFailed(RuntimeError):
    """A step could not do its job. The engine decides whether to retry."""


async def _record_step(
    case_id: UUID,
    ref: str,
    *,
    outcome: str = "completed",
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """One line in the audit trail per finished step, in its own transaction.

    Its own transaction on purpose: the record of "this step finished" must not be lost if the
    next step fails, and must not be visible before the step's own work is committed.
    """
    step = definition.STEP_BY_REF[ref]
    async with SessionLocal() as db:
        await record_event(
            db,
            case_id=case_id,
            action=base.STEP,
            label=f"{step.label}: {outcome}" + (f" — {note}" if note else ""),
            actor=f"{definition.WORKFLOW_NAME}/{ref}",
            actor_type=ActorType.system,
            detail={"ref": ref, "outcome": outcome, "note": note, **(extra or {})},
        )
        await db.commit()


async def _case_status(case_id: UUID) -> CaseStatus | None:
    async with SessionLocal() as db:
        return (
            await db.execute(select(models.Case.status).where(models.Case.id == case_id))
        ).scalar_one_or_none()


# ------------------------------------------------------------------------- intake


async def intake(case_id: UUID, workflow_id: str = "") -> dict[str, Any]:
    """Check the case can start, put it into `processing`, and tie the two ids together.

    Called again after a retry, this is a no-op: a case already processing stays processing.

    `workflow_id` is Conductor's own id for this workflow instance. Intake is the last moment
    before anything needs the LangGraph thread id, so this is where the invariant
    **workflow id == thread id** is enforced rather than hoped for. Under the in-process engine
    there is no separate id and nothing changes.
    """
    async with SessionLocal() as db:
        case = (
            await db.execute(select(models.Case).where(models.Case.id == case_id))
        ).scalar_one_or_none()
        if case is None:
            raise ProcessStepFailed(f"Case {case_id} does not exist")

        documents = (
            await db.execute(
                select(func.count(models.Document.id)).where(models.Document.case_id == case_id)
            )
        ).scalar_one()
        if not documents:
            raise ProcessStepFailed(f"Case {case.reference} has no documents to process")

        realigned = ""
        if workflow_id and case.thread_id != workflow_id:
            realigned = case.thread_id
            case.thread_id = workflow_id

        if case.status in (CaseStatus.intake, CaseStatus.processing):
            case.status = CaseStatus.processing
        reference = case.reference
        thread_id = case.thread_id
        await db.commit()

    if realigned:
        logger.info("case %s thread id realigned to the workflow id %s", reference, workflow_id)

    await _record_step(
        case_id,
        "intake",
        note=f"{documents} document(s) accepted",
        extra={
            "reference": reference,
            "thread_id": thread_id,
            "workflow_id": workflow_id or thread_id,
            "thread_id_replaced": realigned,
        },
    )
    return {"documents": documents, "reference": reference, "thread_id": thread_id}


# -------------------------------------------------------------------------- agent


async def run_agent(case_id: UUID) -> dict[str, Any]:
    """Run the whole reasoning graph, and report which route the case takes.

    The process layer asks the agent one question — "does a human have to look?" — and takes
    the answer. It never second-guesses it, which is why the decision to involve a person
    lives in one place.

    **Delivered at least once.** If the worker died half way through, Conductor hands this task
    to another worker, and a graph that already has a checkpoint must be *continued*, not
    started again: starting again would feed the initial state in a second time, and the keys
    the parallel workers write use appending reducers, so every list would gain a duplicate.
    `continue_case` resumes from the last completed node instead.
    """
    async with SessionLocal() as db:
        thread_id = (
            await db.execute(select(models.Case.thread_id).where(models.Case.id == case_id))
        ).scalar_one()

    if await runner.has_checkpoint(thread_id):
        logger.info("case %s already has a checkpoint — continuing it, not restarting", case_id)
        status = await runner.continue_case(case_id)
    else:
        status = await runner.start_case(case_id)
    if status == CaseStatus.failed.value:
        await _record_step(case_id, "agent", outcome="failed", note="the graph raised an error")
        raise ProcessStepFailed(f"The agent graph failed for case {case_id}")

    needs_review = status == CaseStatus.needs_review.value
    route = definition.ROUTE_REVIEW if needs_review else definition.ROUTE_STRAIGHT_THROUGH

    reasons: list[dict[str, str]] = []
    if needs_review:
        async with SessionLocal() as db:
            reasons = [
                {"code": task.reason_code, "label": task.reason_label}
                for task in (
                    await db.execute(
                        select(models.ReviewTask).where(models.ReviewTask.case_id == case_id)
                    )
                ).scalars()
            ]

    await _record_step(
        case_id,
        "agent",
        note=(
            "a human has to look" if needs_review else "confident enough to go straight through"
        ),
        extra={"route": route, "case_status": status},
    )
    await _record_step(case_id, "review_needed", note=route, extra={"route": route})

    if needs_review:
        async with SessionLocal() as db:
            await record_event(
                db,
                case_id=case_id,
                action=base.WAITING,
                label=f"Process waiting at the human review step ({len(reasons)} reason(s))",
                actor=f"{definition.WORKFLOW_NAME}/human_review",
                actor_type=ActorType.system,
                detail={"note": "waiting for a reviewer", "reasons": reasons},
            )
            await db.commit()

    return {"route": route, "needs_review": needs_review, "review_reasons": reasons}


# ----------------------------------------------------------------- apply decision


async def apply_decision(
    case_id: UUID, decision: str, corrections: dict[str, str] | None = None
) -> dict[str, Any]:
    """Resume the graph from its checkpoint with the reviewer's answer."""
    status = await runner.resume_case(case_id, decision, corrections or {})
    if status == CaseStatus.failed.value:
        await _record_step(
            case_id, "apply_decision", outcome="failed", note="the graph could not resume"
        )
        raise ProcessStepFailed(f"Could not resume case {case_id} after review")

    # The human step is finished, and the timer beside it is moot. Recording both keeps the
    # process view truthful: without this the review would stay "waiting" for ever, next to
    # steps that had already run after it.
    await _record_step(
        case_id,
        "human_review",
        note=f"reviewer decided: {decision}",
        extra={"decision": decision},
    )
    await _record_step(
        case_id,
        "sla_timer",
        outcome="skipped",
        note="the review was answered before the SLA expired",
    )
    await _record_step(
        case_id, "review_join", note="the decision arrived, so the process carried on"
    )
    await _record_step(
        case_id,
        "apply_decision",
        note=f"reviewer decided: {decision}",
        extra={
            "decision": decision,
            "corrections": sorted(corrections or {}),
            "case_status": status,
        },
    )
    return {"decision": decision, "case_status": status}


# --------------------------------------------------------------------- escalation


async def escalate(case_id: UUID) -> dict[str, Any]:
    """The SLA timer fired. Escalate if the review is still open."""
    result = await escalation.escalate_case(case_id)
    escalated = int(result.get("escalated", 0) or 0)
    await _record_step(
        case_id,
        "sla_escalation",
        outcome="completed" if escalated else "skipped",
        note=str(result.get("note", "")),
        extra={"escalated": escalated},
    )
    return result


# ------------------------------------------------------------------------- posting


async def post(case_id: UUID) -> dict[str, Any]:
    """Hand the approved case to the system of record.

    `services.posting` holds the rules and writes the `postings` row and its event; this step
    only moves the case into `posting` first, so the UI can show what is happening, and hands
    the outcome back to the engine.
    """
    status = await _case_status(case_id)
    if status is None:
        raise ProcessStepFailed(f"Case {case_id} does not exist")

    if status == CaseStatus.approved:
        async with SessionLocal() as db:
            case = (
                await db.execute(select(models.Case).where(models.Case.id == case_id))
            ).scalar_one()
            case.status = CaseStatus.posting
            await db.commit()

    result = await posting.post_case(case_id)
    if result["status"] == "failed":
        # Left as a failure for the engine to retry. The idempotency key makes that safe: if
        # the first attempt actually reached the system of record, the retry is recognised as
        # a duplicate instead of posting twice.
        raise ProcessStepFailed(f"Posting failed for case {case_id}: {result.get('note')}")
    return result


# --------------------------------------------------------------------------- audit


async def audit(case_id: UUID) -> dict[str, Any]:
    """Close the case and write the entry an auditor would start from.

    This is the last step, and the only one that moves a case to `completed`: a case is
    finished when it has been posted and sealed, not when the model stopped thinking.
    """
    state = None
    async with SessionLocal() as db:
        case = (
            await db.execute(select(models.Case).where(models.Case.id == case_id))
        ).scalar_one_or_none()
        if case is None:
            raise ProcessStepFailed(f"Case {case_id} does not exist")

        record = await posting.for_case(db, case_id)
        integrity = await audit_trail.verify(db, case_id=case_id)
        field_count = (
            await db.execute(
                select(func.count(models.ExtractedField.id)).where(
                    models.ExtractedField.case_id == case_id
                )
            )
        ).scalar_one()
        open_findings = (
            await db.execute(
                select(func.count(models.Finding.id)).where(
                    models.Finding.case_id == case_id,
                    models.Finding.status == FindingStatus.open,
                )
            )
        ).scalar_one()
        decisions = [
            {
                "by": task.assigned_to.full_name if task.assigned_to else "",
                "decision": task.decision.value if task.decision else None,
                "reason_code": task.decision_reason_code,
                "escalated": task.escalated_at is not None,
            }
            for task in (
                await db.execute(
                    select(models.ReviewTask)
                    .where(models.ReviewTask.case_id == case_id)
                    .order_by(models.ReviewTask.created_at)
                )
            ).scalars()
        ]
        thread_id = case.thread_id
        reference = case.reference

        # A rejected or failed case keeps its status: the process finished, the case did not
        # succeed, and flattening the two would be a lie in the KPI the dashboard shows.
        if case.status not in (CaseStatus.rejected, CaseStatus.failed):
            case.status = CaseStatus.completed
        case.completed_at = case.completed_at or datetime.now(UTC)
        final_status = case.status.value
        await db.commit()

    try:
        state = await runner.get_state(thread_id)
    except Exception:  # the seal must still be written if the checkpoint cannot be read
        logger.warning("could not read the checkpoint for %s while sealing the audit", thread_id)

    summary = {
        "case_status": final_status,
        "reference": reference,
        "thread_id": thread_id,
        "workflow": definition.WORKFLOW_NAME,
        "workflow_version": definition.WORKFLOW_VERSION,
        "fields": int(field_count),
        "open_findings": int(open_findings),
        "decisions": decisions,
        "posting": {
            "status": record.status.value if record else "none",
            "reference": record.reference if record else None,
            "approval_kind": record.approval_kind if record else "",
            "approved_by": record.approved_by if record else "",
            "idempotency_key": record.idempotency_key if record else None,
        },
        "prompt_versions": (state or {}).get("prompt_versions") or {},
        "rule_packs": (state or {}).get("rule_packs") or {},
        "calibration": (state or {}).get("calibration") or {},
        "audit_trail": integrity,
    }

    async with SessionLocal() as db:
        await record_event(
            db,
            case_id=case_id,
            action=base.COMPLETED,
            label=f"Process finished: {final_status} — audit trail sealed",
            actor=f"{definition.WORKFLOW_NAME}/audit",
            actor_type=ActorType.system,
            detail=summary,
        )
        await db.commit()

    await _record_step(
        case_id,
        "audit",
        note=f"{integrity['rows']} event(s) recorded for this case",
        extra={"status": final_status},
    )
    return {"status": final_status, **summary["posting"]}
