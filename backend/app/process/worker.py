"""Conductor task workers.

A worker is a loop: ask Conductor for work on a queue, do it, report the result. Conductor
decides *when* each task runs and what happens if it fails; the worker only knows how to do one
kind of job.

The jobs themselves are the functions in `process/tasks.py` — the same ones the in-process
engine calls. This file is only the glue between a Conductor task payload and a Python call,
which is why it is short and why the two engines cannot drift apart.

Three details that matter in a real deployment:

* **A crash is safe.** If a worker dies mid-task, Conductor stops receiving updates and
  redelivers the task after `responseTimeoutSeconds`. Every step is idempotent, so doing it
  again is harmless — and the posting step's idempotency key means even the money-side step can
  be redelivered.
* **A failed task is reported, not swallowed.** Conductor needs to know, or it will wait for an
  answer that never comes.
* **Nothing is polled that nobody handles.** The queue list comes from the process definition,
  so adding a step to the process without a handler fails at startup instead of leaving a
  workflow stuck.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.process import definition
from app.process import tasks as steps
from app.process.conductor_client import ConductorClient

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _case_id(payload: dict[str, Any]) -> UUID:
    raw = payload.get("case_id")
    if not raw:
        raise steps.ProcessStepFailed("The task payload has no case_id")
    return UUID(str(raw))


async def _intake(payload: dict[str, Any]) -> dict[str, Any]:
    return await steps.intake(_case_id(payload), str(payload.get("workflow_id") or ""))


async def _agent(payload: dict[str, Any]) -> dict[str, Any]:
    return await steps.run_agent(_case_id(payload))


async def _apply_decision(payload: dict[str, Any]) -> dict[str, Any]:
    corrections = payload.get("corrections") or {}
    if not isinstance(corrections, dict):
        corrections = {}
    return await steps.apply_decision(
        _case_id(payload),
        str(payload.get("decision") or "approve"),
        {str(k): str(v) for k, v in corrections.items()},
    )


async def _post(payload: dict[str, Any]) -> dict[str, Any]:
    return await steps.post(_case_id(payload))


async def _audit(payload: dict[str, Any]) -> dict[str, Any]:
    return await steps.audit(_case_id(payload))


async def _escalate(payload: dict[str, Any]) -> dict[str, Any]:
    return await steps.escalate(_case_id(payload))


HANDLERS: dict[str, Handler] = {
    "wathiq_intake": _intake,
    "wathiq_agent": _agent,
    "wathiq_apply_decision": _apply_decision,
    "wathiq_post": _post,
    "wathiq_audit": _audit,
    "wathiq_escalate": _escalate,
}


def missing_handlers() -> list[str]:
    """Queues the process defines but nothing here can serve."""
    return [queue for queue in definition.WORKER_QUEUES if queue not in HANDLERS]


class TaskWorker:
    """Polls one queue and runs one handler."""

    def __init__(self, queue: str, handler: Handler, client: ConductorClient) -> None:
        self.queue = queue
        self.handler = handler
        self.client = client
        self.handled = 0
        self.failed = 0

    async def run_forever(self, stop: asyncio.Event) -> None:
        poll_ms = max(int(settings.conductor_poll_seconds * 1000), 100)
        while not stop.is_set():
            try:
                batch = await self.client.poll(
                    self.queue, count=settings.conductor_batch_size, timeout_ms=poll_ms
                )
            except Exception as exc:
                # Conductor restarting, or a network blip. Back off and try again; the worker
                # must not exit, or the queue would silently stop being served.
                logger.warning("poll of %s failed: %s", self.queue, exc)
                await asyncio.sleep(min(settings.conductor_poll_seconds * 5, 10.0))
                continue

            if not batch:
                continue
            for task in batch:
                if stop.is_set():
                    break
                await self.run_one(task)

    async def run_one(self, task: dict[str, Any]) -> None:
        task_id = str(task.get("taskId", ""))
        workflow_id = str(task.get("workflowInstanceId", ""))
        payload = dict(task.get("inputData") or {})
        logger.info("%s: picked up task %s", self.queue, task_id)

        try:
            output = await self.handler(payload)
        except steps.ProcessStepFailed as exc:
            self.failed += 1
            logger.warning("%s: task %s failed: %s", self.queue, task_id, exc)
            await self._report_failure(workflow_id, task_id, str(exc), terminal=False)
            return
        except Exception as exc:
            self.failed += 1
            logger.exception("%s: task %s raised", self.queue, task_id)
            await self._report_failure(
                workflow_id, task_id, f"{type(exc).__name__}: {exc}", terminal=False
            )
            return

        try:
            await self.client.complete(
                workflow_id=workflow_id, task_id=task_id, output=output
            )
            self.handled += 1
        except Exception:
            # The work is done and committed, but Conductor was not told. It will redeliver the
            # task, and every step is safe to repeat — which is exactly why they are idempotent.
            logger.exception(
                "%s: task %s finished but Conductor could not be told; it will be redelivered",
                self.queue,
                task_id,
            )

    async def _report_failure(
        self, workflow_id: str, task_id: str, reason: str, *, terminal: bool
    ) -> None:
        try:
            await self.client.fail(
                workflow_id=workflow_id, task_id=task_id, reason=reason, terminal=terminal
            )
        except Exception:
            logger.exception("could not report the failure of task %s to Conductor", task_id)


class WorkerPool:
    """One worker per queue, all in the same event loop."""

    def __init__(self, client: ConductorClient | None = None) -> None:
        self.client = client or ConductorClient()
        self.stop = asyncio.Event()
        self.workers = [
            TaskWorker(queue, HANDLERS[queue], self.client)
            for queue in definition.WORKER_QUEUES
            if queue in HANDLERS
        ]

    async def run(self) -> None:
        absent = missing_handlers()
        if absent:
            # A queue nobody polls leaves every workflow stuck at that step, with no error.
            # Better to refuse to start.
            raise RuntimeError(f"No handler for the process queue(s): {', '.join(absent)}")
        logger.info(
            "worker pool serving %d queue(s): %s",
            len(self.workers),
            ", ".join(worker.queue for worker in self.workers),
        )
        await asyncio.gather(*(worker.run_forever(self.stop) for worker in self.workers))

    def request_stop(self) -> None:
        self.stop.set()

    def summary(self) -> dict[str, Any]:
        return {
            "queues": {
                worker.queue: {"handled": worker.handled, "failed": worker.failed}
                for worker in self.workers
            }
        }
