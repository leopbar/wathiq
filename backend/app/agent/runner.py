"""Running the graph for a case, and saving what it produced.

This module is the bridge between the graph (which thinks in plain dictionaries) and the
database (which holds the records the UI reads). Keeping the bridge in one place means the
nodes stay easy to test and the write rules live somewhere you can point at.

Two entry points:

* `start_case`  — run from the beginning. If the graph stops at the review gate, create the
                  review task and leave the case waiting.
* `resume_case` — a reviewer answered; carry on from the checkpoint.

The LangGraph thread id is the case's `thread_id`, which in M4 is also the Conductor workflow
id. One identifier ties the whole audit trail together.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.agent.graph import build_graph
from app.agent.state import CaseState
from app.core.config import settings
from app.db import models
from app.db.enums import (
    ActorType,
    CaseStatus,
    DocTypeKey,
    DocumentStatus,
    FieldStatus,
    FindingStatus,
    ReviewDecision,
    ReviewReason,
    ReviewStatus,
    Role,
    Severity,
)
from app.db.session import SessionLocal
from app.services.events import record_event
from app.services.sla import default_due_at

logger = logging.getLogger(__name__)

# Fields at or above this are accepted without a reviewer looking at them.
AUTO_ACCEPT_THRESHOLD = 0.85

_checkpointer: AsyncPostgresSaver | None = None
_checkpointer_cm: Any = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """One shared Postgres checkpointer for the process.

    The checkpointer is what makes a case survive a restart: after every node, the state is
    written to PostgreSQL, so a case can sit at the review gate for hours and continue in a
    different process.
    """
    global _checkpointer, _checkpointer_cm
    if _checkpointer is None:
        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.sync_database_url)
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()  # creates its own tables, idempotent
    return _checkpointer


async def close_checkpointer() -> None:
    """Release the checkpointer's connection pool on shutdown."""
    global _checkpointer, _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
    _checkpointer, _checkpointer_cm = None, None


async def _compiled():
    return build_graph().compile(checkpointer=await get_checkpointer())


# --------------------------------------------------------------------------- state


async def _initial_state(case: models.Case) -> CaseState:
    return {
        "case_id": str(case.id),
        "thread_id": case.thread_id,
        "case_type": case.case_type.value,
        "documents": [
            {
                "document_id": str(d.id),
                "filename": d.filename,
                "mime_type": d.mime_type,
                "storage_path": d.storage_path,
                "doc_type": d.doc_type.value,
                "classification_confidence": d.classification_confidence or 0.0,
                "ocr_text": "",
                "ocr_confidence": 0.0,
                "page_count": d.page_count,
                "language": d.language.value,
            }
            for d in case.documents
        ],
        "fields": [],
        "findings": [],
        "review_reasons": [],
    }


async def _load_case(db, case_id: UUID) -> models.Case | None:
    return (
        await db.execute(
            select(models.Case)
            .options(selectinload(models.Case.documents))
            .where(models.Case.id == case_id)
        )
    ).scalar_one_or_none()


# ------------------------------------------------------------------------ persist


async def _persist(db, case: models.Case, state: dict[str, Any]) -> None:
    """Write what the graph produced into the records the UI reads.

    Fields and findings are replaced wholesale rather than merged: the graph's output is the
    single source of truth for a run, and replacing avoids half-updated rows if a run is
    repeated. The event log is append-only and is never touched here.
    """
    corrections: dict[str, str] = state.get("corrections") or {}

    # --- documents: classification and OCR results ---
    by_id = {str(d.id): d for d in case.documents}
    for doc_state in state.get("documents", []):
        document = by_id.get(doc_state["document_id"])
        if document is None:
            continue
        document.doc_type = DocTypeKey(doc_state["doc_type"])
        document.classification_confidence = doc_state["classification_confidence"]
        document.ocr_confidence = doc_state["ocr_confidence"]
        document.ocr_text = doc_state["ocr_text"][:200_000]
        document.status = (
            DocumentStatus.extracted if doc_state["ocr_text"] else DocumentStatus.failed
        )

    # --- fields ---
    await db.execute(
        delete(models.ExtractedField).where(models.ExtractedField.case_id == case.id)
    )
    for field_state in state.get("fields", []):
        corrected = corrections.get(field_state["name"])
        confidence = 1.0 if corrected is not None else field_state["confidence"]
        if corrected is not None:
            status = FieldStatus.corrected
        elif confidence >= AUTO_ACCEPT_THRESHOLD:
            status = FieldStatus.auto_accepted
        else:
            status = FieldStatus.needs_review
        db.add(
            models.ExtractedField(
                case_id=case.id,
                document_id=UUID(field_state["document_id"])
                if field_state["document_id"]
                else None,
                name=field_state["name"],
                label_en=field_state["label_en"],
                label_ar=field_state["label_ar"],
                value=field_state["value"],
                corrected_value=corrected,
                confidence=field_state["confidence"],
                # Real calibration arrives in M3; until then we are honest and show the raw
                # score in both places rather than inventing a calibrated number.
                calibrated_confidence=field_state["confidence"],
                status=status,
                is_critical=field_state["is_critical"],
                page=field_state.get("page"),
                bbox=field_state.get("bbox"),
                source_text=field_state.get("source_text"),
                order_index=field_state["order_index"],
            )
        )

    # --- findings ---
    # A reviewer may already have resolved or waived a finding before the graph resumed. The
    # rules re-run on resume and would recreate it as `open`, silently undoing their decision,
    # so the previous status is carried over by rule code.
    previous_status = {
        row.code: row.status
        for row in (
            await db.execute(select(models.Finding).where(models.Finding.case_id == case.id))
        ).scalars()
    }
    await db.execute(delete(models.Finding).where(models.Finding.case_id == case.id))
    for finding_state in state.get("findings", []):
        db.add(
            models.Finding(
                case_id=case.id,
                code=finding_state["code"],
                severity=Severity(finding_state["severity"]),
                title=finding_state["title"],
                description=finding_state["description"],
                policy_citation=finding_state["policy_citation"],
                status=previous_status.get(finding_state["code"], FindingStatus.open),
            )
        )

    case.confidence = state.get("confidence")


# -------------------------------------------------------------------------- start


async def start_case(case_id: UUID) -> str:
    """Run the pipeline for a case. Returns the status it ended in."""
    started = datetime.now(UTC)
    async with SessionLocal() as db:
        case = await _load_case(db, case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        state = await _initial_state(case)

    graph = await _compiled()
    config = {"configurable": {"thread_id": state["thread_id"]}}

    try:
        result = await graph.ainvoke(state, config=config)
    except Exception:
        logger.exception("Pipeline failed for case %s", case_id)
        await _fail(case_id, "The pipeline hit an unexpected error.")
        return CaseStatus.failed.value

    return await _apply_result(case_id, result, config, started)


async def _apply_result(
    case_id: UUID, result: dict[str, Any], config: dict[str, Any], started: datetime
) -> str:
    """Save the run and set the case status, including the paused-for-review case."""
    graph = await _compiled()
    snapshot = await graph.aget_state(config)
    interrupts = snapshot.interrupts if snapshot else ()

    async with SessionLocal() as db:
        case = await _load_case(db, case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")

        await _persist(db, case, result)
        elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
        case.processing_ms = (case.processing_ms or 0) + elapsed_ms

        if interrupts:
            # The graph is parked at the review gate. Create the review tasks here, outside
            # the graph, so they are created exactly once even though the gate node re-runs.
            payload = interrupts[0].value or {}
            reasons = payload.get("reasons") or [{"code": "MANUAL", "label": "Review required"}]
            await _create_review_tasks(db, case, reasons)
            case.status = CaseStatus.needs_review
            case.sla_due_at = case.sla_due_at or default_due_at()
            await record_event(
                db,
                case_id=case.id,
                action="pipeline.paused",
                label=f"Paused for human review ({len(reasons)} reason(s))",
                actor="system",
                actor_type=ActorType.system,
                detail={"reasons": reasons, "thread_id": case.thread_id},
            )
        else:
            decision = result.get("decision")
            rejected = decision == ReviewDecision.reject.value
            case.status = CaseStatus.rejected if rejected else CaseStatus.completed
            case.straight_through = bool(result.get("straight_through"))
            case.completed_at = datetime.now(UTC)
            await record_event(
                db,
                case_id=case.id,
                action="pipeline.completed",
                label=f"Pipeline finished: {case.status.value}",
                actor="system",
                actor_type=ActorType.system,
                detail={
                    "straight_through": case.straight_through,
                    "confidence": case.confidence,
                    "thread_id": case.thread_id,
                },
                duration_ms=elapsed_ms,
            )

        status = case.status.value
        await db.commit()
        return status


async def _create_review_tasks(db, case: models.Case, reasons: list[dict[str, str]]) -> None:
    """One task per distinct reason, skipping any that already exist for this case."""
    existing = {
        row.reason_code
        for row in (
            await db.execute(
                select(models.ReviewTask).where(
                    models.ReviewTask.case_id == case.id,
                    models.ReviewTask.status != ReviewStatus.completed,
                )
            )
        ).scalars()
    }
    mandatory = {"SANCTIONS_POSSIBLE_MATCH", "DOCUMENT_EXPIRED", "NEW_DOCUMENT_TYPE"}
    seen: set[str] = set()

    for reason in reasons:
        code = reason.get("code", "MANUAL")
        if code in existing or code in seen:
            continue
        seen.add(code)
        db.add(
            models.ReviewTask(
                case_id=case.id,
                reason=ReviewReason.mandatory if code in mandatory else ReviewReason.dynamic,
                reason_code=code,
                reason_label=reason.get("label", code),
                status=ReviewStatus.pending,
                assigned_role=Role.reviewer,
                sla_due_at=default_due_at(),
            )
        )


# ------------------------------------------------------------------------- resume


async def resume_case(
    case_id: UUID, decision: str, corrections: dict[str, str] | None = None
) -> str:
    """A reviewer answered — continue the graph from its checkpoint."""
    started = datetime.now(UTC)
    async with SessionLocal() as db:
        case = await _load_case(db, case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")
        thread_id = case.thread_id

    graph = await _compiled()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await graph.ainvoke(
            Command(resume={"decision": decision, "corrections": corrections or {}}),
            config=config,
        )
    except Exception:
        logger.exception("Resume failed for case %s", case_id)
        await _fail(case_id, "The pipeline could not resume after review.")
        return CaseStatus.failed.value

    return await _apply_result(case_id, result, config, started)


async def _fail(case_id: UUID, message: str) -> None:
    async with SessionLocal() as db:
        case = await _load_case(db, case_id)
        if case is None:
            return
        case.status = CaseStatus.failed
        await record_event(
            db,
            case_id=case.id,
            action="pipeline.failed",
            label=message,
            actor="system",
            actor_type=ActorType.system,
        )
        await db.commit()


async def has_checkpoint(thread_id: str) -> bool:
    """Whether this thread has a saved checkpoint to resume from."""
    graph = await _compiled()
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    return bool(snapshot and snapshot.created_at)
