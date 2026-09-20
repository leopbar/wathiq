"""The fallback process engine: the same steps, scheduled by Python.

Conductor needs roughly 2 GB of RAM. On a 16 GB laptop that is a real cost, and a demo that
cannot run without it is a fragile demo. So the process layer has a second engine that walks
the steps in `process/tasks.py` itself.

What it keeps:

* the same steps, in the same order, from the same functions;
* the same records in the append-only event log, so the UI and the audit trail look identical;
* durability where it matters — the case never lives only in memory. Every step commits, and
  the LangGraph checkpoint is in PostgreSQL, so `recover` can pick a case up after a crash.

What it honestly does not have:

* a task queue with at-least-once delivery. If this container dies mid-step, nothing retries
  until `recover` runs at startup — whereas Conductor would redeliver the task by itself;
* a timer per case. A single sweep finds overdue reviews instead.

Which engine ran a case is written into the case's event log, so a case run here can never be
mistaken for one that went through Conductor.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.db import models
from app.db.enums import ActorType, CaseStatus
from app.db.session import SessionLocal
from app.process import base, definition
from app.process import tasks as steps
from app.services import escalation, pipeline
from app.services.events import record_event

logger = logging.getLogger(__name__)

# Mirrors the retry policy in `definition.task_definitions`, so a step that Conductor would
# retry is also retried here. Same behaviour, different scheduler.
RETRY_ATTEMPTS = {"post": 3, "audit": 3}
RETRY_DELAY_SECONDS = 2.0


class InProcessEngine:
    """Walks the process in the API container."""

    name = "inprocess"

    def __init__(self) -> None:
        self._sweeper: asyncio.Task[None] | None = None

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        """Start the SLA sweep. Conductor's timer does this job when Conductor is running."""
        if self._sweeper is None and settings.sla_sweep_seconds > 0:
            self._sweeper = asyncio.create_task(self._sweep_forever(), name="sla-sweeper")
            logger.info("SLA sweeper started (every %ds)", settings.sla_sweep_seconds)

    async def stop(self) -> None:
        if self._sweeper is not None:
            self._sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sweeper
            self._sweeper = None

    async def _sweep_forever(self) -> None:
        while True:
            await asyncio.sleep(settings.sla_sweep_seconds)
            try:
                escalated = await escalation.escalate_overdue()
                if escalated:
                    logger.info("SLA sweep escalated %d review(s)", escalated)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A failed sweep must never take the API down with it.
                logger.exception("SLA sweep failed")

    # -- the process ----------------------------------------------------------

    async def start_case(self, case_id: UUID) -> str:
        """Begin the process. The workflow instance id is the case's thread id."""
        workflow_id = await _record_started(case_id, engine=self.name, note="")
        pipeline.launch(self._run(case_id), label=f"process.start:{case_id}")
        return workflow_id

    async def submit_decision(
        self, case_id: UUID, decision: str, corrections: dict[str, str] | None = None
    ) -> None:
        """The human step has its answer: carry on from there."""
        pipeline.launch(
            self._continue(case_id, decision, corrections or {}),
            label=f"process.decision:{case_id}",
        )

    async def _run(self, case_id: UUID) -> None:
        """intake → agent → (park for a human | finish)."""
        try:
            await steps.intake(case_id)
            result = await steps.run_agent(case_id)
        except steps.ProcessStepFailed as exc:
            await _record_failed(case_id, "agent", str(exc))
            return

        if result["route"] == definition.ROUTE_REVIEW:
            # Parked. `submit_decision` picks the process up again, possibly in another process
            # after a restart, because everything needed is in the database.
            return
        await self._finish(case_id)

    async def _continue(
        self, case_id: UUID, decision: str, corrections: dict[str, str]
    ) -> None:
        try:
            outcome = await steps.apply_decision(case_id, decision, corrections)
        except steps.ProcessStepFailed as exc:
            await _record_failed(case_id, "apply_decision", str(exc))
            return
        if outcome.get("case_status") == CaseStatus.needs_review.value:
            # An escalation keeps the case at the human step: someone else still has to answer.
            return
        await self._finish(case_id)

    async def _finish(self, case_id: UUID) -> None:
        """post → audit, each retried the way Conductor would retry it."""
        for ref, runner_fn in (("post", steps.post), ("audit", steps.audit)):
            attempts = RETRY_ATTEMPTS.get(ref, 1)
            for attempt in range(1, attempts + 1):
                try:
                    await runner_fn(case_id)
                    break
                except steps.ProcessStepFailed as exc:
                    if attempt == attempts:
                        await _record_failed(case_id, ref, str(exc))
                        return
                    logger.warning(
                        "step %s failed for case %s (attempt %d/%d): %s",
                        ref,
                        case_id,
                        attempt,
                        attempts,
                        exc,
                    )
                    await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)

    # -- recovery -------------------------------------------------------------

    async def recover(self) -> int:
        """Pick up cases a crash left half-processed. Returns how many were restarted.

        This is the part Conductor would do for us. Without it, a container that dies between
        two steps leaves a case sitting in `processing` or `approved` forever — which is
        exactly the failure a process engine exists to prevent, so the fallback has to answer
        for it too.
        """
        async with SessionLocal() as db:
            stuck = (
                await db.execute(
                    select(models.Case.id, models.Case.reference, models.Case.status).where(
                        models.Case.status.in_(
                            (CaseStatus.processing, CaseStatus.approved, CaseStatus.posting)
                        )
                    )
                )
            ).all()

        for case_id, reference, status in stuck:
            async with SessionLocal() as db:
                await record_event(
                    db,
                    case_id=case_id,
                    action="process.recovered",
                    label=f"{reference} was left in '{status.value}' by a restart — continuing",
                    actor=f"{definition.WORKFLOW_NAME}/recovery",
                    actor_type=ActorType.system,
                    detail={"status": status.value, "engine": self.name},
                )
                await db.commit()

            if status == CaseStatus.processing:
                pipeline.launch(
                    self._recover_agent(case_id), label=f"process.recover:{case_id}"
                )
            else:
                # Approved or mid-posting: the graph is done, the business steps are not.
                pipeline.launch(self._finish(case_id), label=f"process.finish:{case_id}")

        if stuck:
            logger.info("recovery picked up %d case(s)", len(stuck))
        return len(stuck)

    async def _recover_agent(self, case_id: UUID) -> None:
        """Continue the graph from its last checkpoint, then run the rest of the process."""
        from app.agent import runner

        status = await runner.continue_case(case_id)
        if status == CaseStatus.needs_review.value:
            return
        if status == CaseStatus.failed.value:
            await _record_failed(case_id, "agent", "the graph failed after a restart")
            return
        await self._finish(case_id)

    # -- reporting ------------------------------------------------------------

    async def health(self) -> base.EngineHealth:
        return base.EngineHealth(
            engine=self.name,
            reachable=True,
            detail=(
                "Running the process in the API container. Durable through the database and "
                "the LangGraph checkpoint, but without a task queue: a crash is recovered at "
                "the next startup rather than redelivered immediately."
            ),
            workflow_registered=True,
        )

    async def status(self, case: Any) -> base.ProcessStatus:
        return await status_for_case(case, engine=self.name)


# --------------------------------------------------------------------- shared helpers


async def _record_started(case_id: UUID, *, engine: str, note: str) -> str:
    """Record that the process began, and return the workflow instance id."""
    async with SessionLocal() as db:
        case = (
            await db.execute(select(models.Case).where(models.Case.id == case_id))
        ).scalar_one()
        workflow_id = case.thread_id
        await record_event(
            db,
            case_id=case_id,
            action=base.STARTED,
            label=(
                f"Process started: {definition.WORKFLOW_NAME} "
                f"v{definition.WORKFLOW_VERSION} on the {engine} engine"
            ),
            actor=f"{definition.WORKFLOW_NAME}/start",
            actor_type=ActorType.system,
            detail={
                "engine": engine,
                "workflow": definition.WORKFLOW_NAME,
                "workflow_version": definition.WORKFLOW_VERSION,
                "workflow_id": workflow_id,
                "thread_id": case.thread_id,
                "note": note,
            },
        )
        await db.commit()
    return workflow_id


async def _record_failed(case_id: UUID, ref: str, error: str) -> None:
    async with SessionLocal() as db:
        await record_event(
            db,
            case_id=case_id,
            action=base.FAILED,
            label=f"Process stopped at '{ref}': {error}",
            actor=f"{definition.WORKFLOW_NAME}/{ref}",
            actor_type=ActorType.system,
            detail={"ref": ref, "error": error},
        )
        await db.commit()
    logger.error("process failed at %s for case %s: %s", ref, case_id, error)


async def status_for_case(case: Any, *, engine: str) -> base.ProcessStatus:
    """Rebuild the process position for a case from its events."""
    async with SessionLocal() as db:
        events = (
            (
                await db.execute(
                    select(models.Event)
                    .where(models.Event.case_id == case.id)
                    .order_by(models.Event.seq.asc())
                )
            )
            .scalars()
            .all()
        )
    return base.status_from_events(
        engine=engine,
        workflow_id=case.thread_id,
        events=list(events),
        case_status=case.status.value,
    )
