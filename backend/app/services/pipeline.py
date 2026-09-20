"""Holding on to background work, so it cannot be garbage-collected mid-run.

An HTTP request must not wait for a whole case to be processed — the browser watches progress
over SSE instead. So the API hands the case to the process engine and returns immediately.

`asyncio.create_task` alone is not enough: the event loop keeps only a weak reference, so a
task can be collected while it is still running. Everything launched here is kept in a set
until it finishes, and a failure is logged rather than disappearing into a task nobody awaited.

Since M4 the only caller is the in-process process engine. Under Conductor the same work is
driven by a worker polling a task queue, which is what makes it survive a restart of this
container.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_running: set[asyncio.Task[Any]] = set()


def launch(coro: Coroutine[Any, Any, Any], *, label: str) -> asyncio.Task[Any]:
    """Run a coroutine in the background and keep a strong reference to it."""
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


def in_flight() -> int:
    """How many background runs are going on. Used by tests and the health endpoint."""
    return len(_running)


async def drain(timeout: float = 10.0) -> None:  # noqa: ASYNC109
    """Wait for in-flight runs to finish. Used on shutdown and in tests.

    ASYNC109 suggests `asyncio.timeout` instead, but that *cancels* the tasks when the time is
    up, which is exactly what we must not do to a half-written case. `asyncio.wait` stops
    waiting and leaves the runs alone, which is the behaviour shutdown needs.
    """
    if not _running:
        return
    await asyncio.wait(set(_running), timeout=timeout)
