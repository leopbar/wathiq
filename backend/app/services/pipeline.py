"""Launching pipeline runs in the background.

An HTTP request should not wait for the whole pipeline, and the browser watches progress over
SSE instead. So `/start` and the review decision both hand off to here and return immediately.

`asyncio.create_task` alone is not enough: the event loop keeps only a weak reference, so a
task can be garbage-collected mid-run. We hold a strong reference until it finishes, and we
log failures rather than letting them disappear into a never-awaited task.

In M4 Conductor takes this over: the same functions get called by a Conductor worker instead
of a background task, which is what makes the run durable across a restart.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from app.agent import runner

logger = logging.getLogger(__name__)

_running: set[asyncio.Task[Any]] = set()


def _launch(coro: Coroutine[Any, Any, Any], *, label: str) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro, name=label)
    _running.add(task)

    def _done(finished: asyncio.Task[Any]) -> None:
        _running.discard(finished)
        if finished.cancelled():
            logger.warning("%s was cancelled", label)
            return
        error = finished.exception()
        if error is not None:
            logger.error("%s failed: %s", label, error, exc_info=error)

    task.add_done_callback(_done)
    return task


def start(case_id: UUID) -> None:
    """Run the pipeline for a case, from the beginning."""
    _launch(runner.start_case(case_id), label=f"pipeline.start:{case_id}")


def resume(case_id: UUID, decision: str, corrections: dict[str, str] | None = None) -> None:
    """Continue a case that was waiting at the review gate."""
    _launch(
        runner.resume_case(case_id, decision, corrections),
        label=f"pipeline.resume:{case_id}",
    )


async def drain(timeout: float = 10.0) -> None:  # noqa: ASYNC109
    """Wait for in-flight runs to finish. Used on shutdown and in tests.

    ASYNC109 suggests `asyncio.timeout` instead, but that *cancels* the tasks when the time is
    up, which is exactly what we must not do to a half-written case. `asyncio.wait` stops
    waiting and leaves the runs alone, which is the behaviour shutdown needs.
    """
    if not _running:
        return
    await asyncio.wait(set(_running), timeout=timeout)
