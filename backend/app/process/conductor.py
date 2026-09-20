"""The Conductor process engine.

Conductor owns the state machine. Wathiq's part is small and worth being able to say in one
breath:

* **start** a workflow instance for a case, and make the case's LangGraph thread id the same
  string as Conductor's workflow id — one identifier for the business process, the AI reasoning
  and the audit trail;
* **complete the HUMAN task** when a reviewer decides, which is how a person's answer re-enters
  an automated process;
* **read the instance back** so the UI can show what Conductor thinks, next to what our own
  event log recorded.

Everything else — scheduling, retries, timers, redelivery after a crash — is Conductor's job,
and deliberately not reimplemented here. That is the whole reason for having a process engine.

The steps themselves are not in this file. They live in `process/tasks.py` and are shared with
the fallback engine; the workers in `process/worker.py` are what connect the two.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db import models
from app.db.enums import ActorType
from app.db.session import SessionLocal
from app.process import base, definition
from app.process.conductor_client import ConductorClient, ConductorError
from app.process.inprocess import status_for_case
from app.services.events import record_event

logger = logging.getLogger(__name__)


class ConductorEngine:
    """Starts workflows and answers human tasks. Conductor does the rest."""

    name = "conductor"

    def __init__(self, client: ConductorClient | None = None) -> None:
        self.client = client or ConductorClient()
        self._registered = False

    # -- definitions ----------------------------------------------------------

    async def ensure_registered(self, *, force: bool = False) -> bool:
        """Register the definitions with Conductor. Safe to call repeatedly."""
        if self._registered and not force:
            return True
        try:
            await self.client.register(
                definition.workflow_definition(), definition.task_definitions()
            )
        except Exception as exc:
            logger.warning("could not register the Conductor definitions: %s", exc)
            self._registered = False
            return False
        self._registered = True
        logger.info(
            "registered %s v%d with Conductor",
            definition.WORKFLOW_NAME,
            definition.WORKFLOW_VERSION,
        )
        return True

    # -- the process ----------------------------------------------------------

    async def start_case(self, case_id: UUID) -> str:
        """Start a Conductor workflow for the case and return its instance id."""
        await self.ensure_registered()

        async with SessionLocal() as db:
            case = (
                await db.execute(select(models.Case).where(models.Case.id == case_id))
            ).scalar_one()
            reference = case.reference

        workflow_id = await self.client.start_workflow(
            definition.WORKFLOW_NAME,
            definition.WORKFLOW_VERSION,
            workflow_input={"case_id": str(case_id), "case_reference": reference},
            correlation_id=reference,
            # One case, one workflow — even if the start request is sent twice.
            idempotency_key=str(case_id),
        )

        async with SessionLocal() as db:
            case = (
                await db.execute(select(models.Case).where(models.Case.id == case_id))
            ).scalar_one()
            previous = case.thread_id
            # The invariant, applied as early as possible. The intake step checks it again
            # before anything reads it, which closes the gap if this update were ever missed.
            case.thread_id = workflow_id
            await record_event(
                db,
                case_id=case_id,
                action=base.STARTED,
                label=(
                    f"Process started: {definition.WORKFLOW_NAME} "
                    f"v{definition.WORKFLOW_VERSION} on Conductor"
                ),
                actor=f"{definition.WORKFLOW_NAME}/start",
                actor_type=ActorType.system,
                detail={
                    "engine": self.name,
                    "workflow": definition.WORKFLOW_NAME,
                    "workflow_version": definition.WORKFLOW_VERSION,
                    "workflow_id": workflow_id,
                    "thread_id": workflow_id,
                    "thread_id_replaced": previous if previous != workflow_id else "",
                    "note": "the workflow id is also the LangGraph thread id",
                },
            )
            await db.commit()

        logger.info("started Conductor workflow %s for case %s", workflow_id, reference)
        return workflow_id

    async def submit_decision(
        self, case_id: UUID, decision: str, corrections: dict[str, str] | None = None
    ) -> None:
        """Complete the waiting HUMAN task with the reviewer's answer.

        If there is no waiting human task, something is wrong with our picture of the process,
        and that is recorded rather than patched over: the case would otherwise look decided
        while Conductor still waits.
        """
        async with SessionLocal() as db:
            case = (
                await db.execute(select(models.Case).where(models.Case.id == case_id))
            ).scalar_one()
            workflow_id = case.thread_id

        task = await self.client.find_open_task(workflow_id, task_type="HUMAN")
        if task is None:
            await self._record_problem(
                case_id,
                f"No waiting human task in workflow {workflow_id}; the decision could not be "
                "handed to Conductor.",
            )
            raise ConductorError(f"No waiting human task in workflow {workflow_id}")

        await self.client.complete(
            workflow_id=workflow_id,
            task_id=str(task["taskId"]),
            output={"decision": decision, "corrections": corrections or {}},
            logs=[f"decision={decision}", f"corrections={sorted(corrections or {})}"],
        )
        logger.info(
            "completed the human task of workflow %s with decision '%s'", workflow_id, decision
        )
        await self._release_sla_timer(workflow_id)

    async def _release_sla_timer(self, workflow_id: str) -> None:
        """Let the SLA branch finish now that the review has been answered.

        The timer runs in its own branch of the fork, and the JOIN waits only for the review —
        which is what stops a fired timer from finishing a case on a human's behalf. The
        consequence is that the branch is still sitting in its WAIT once the review is answered,
        and the workflow instance would stay RUNNING for the rest of the SLA window.

        Completing the WAIT task releases it. The escalation step then runs, finds the review
        already closed, records that there was nothing to escalate, and the instance reaches
        COMPLETED. **Order matters**: the human task is completed first, so the review is
        already decided in the database by the time the escalation step looks at it.
        """
        try:
            timer = await self.client.find_open_task(workflow_id, task_type="WAIT")
            if timer is None:
                return
            await self.client.complete(
                workflow_id=workflow_id,
                task_id=str(timer["taskId"]),
                output={"released": True},
                logs=["the review was answered, so the SLA timer was released"],
            )
        except Exception as exc:
            # Not worth failing a decision over: the branch would end by itself when the SLA
            # window closes, and the escalation step is safe to run then because it checks
            # whether the review is still open.
            logger.warning("could not release the SLA timer of %s: %s", workflow_id, exc)

    async def _record_problem(self, case_id: UUID, message: str) -> None:
        async with SessionLocal() as db:
            await record_event(
                db,
                case_id=case_id,
                action=base.FAILED,
                label=message,
                actor=f"{definition.WORKFLOW_NAME}/human_review",
                actor_type=ActorType.system,
                detail={"ref": "human_review", "error": message},
            )
            await db.commit()

    async def recover(self) -> int:
        """Nothing to do — and that is the point.

        Conductor redelivers a task whose worker stopped answering, so a crash needs no sweep
        of our own. The in-process engine has to do this itself, which is the clearest
        difference between the two.
        """
        return 0

    # -- reporting ------------------------------------------------------------

    async def health(self) -> base.EngineHealth:
        reachable, detail = await self.client.health()
        registered = False
        if reachable:
            registered = await self.client.workflow_registered(
                definition.WORKFLOW_NAME, definition.WORKFLOW_VERSION
            )
            detail = (
                f"{detail} Workflow {definition.WORKFLOW_NAME} "
                f"v{definition.WORKFLOW_VERSION} "
                f"{'is registered' if registered else 'is NOT registered yet'}."
            )
        return base.EngineHealth(
            engine=self.name,
            reachable=reachable,
            detail=detail,
            workflow_registered=registered,
            url=self.client.base_url,
        )

    async def status(self, case: Any) -> base.ProcessStatus:
        """Our own record of the process, plus what Conductor says about it."""
        status = await status_for_case(case, engine=self.name)
        try:
            workflow = await self.client.get_workflow(case.thread_id)
        except Exception as exc:
            status.note = (
                f"Conductor could not be asked about this workflow ({type(exc).__name__}); "
                "the steps below come from Wathiq's own event log."
            )
            return status

        status.live = {
            "workflow_id": workflow.get("workflowId"),
            "status": workflow.get("status"),
            "start_time": workflow.get("startTime"),
            "end_time": workflow.get("endTime"),
            "tasks": [
                {
                    "ref": task.get("referenceTaskName"),
                    "type": task.get("taskType"),
                    "status": task.get("status"),
                    "retried": task.get("retryCount", 0),
                }
                for task in (workflow.get("tasks") or [])
            ],
        }
        return status
