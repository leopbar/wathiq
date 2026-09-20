"""Container entry point for the Conductor workers: `python -m app.process.worker_main`.

The same image as the API, started as a task worker instead of a web server. That is
deliberate: the worker runs the LangGraph graph, so it needs the same code, the same models and
the same database. Two images would mean two versions of the reasoning, which is the last thing
an auditable system should have.

What this adds around the polling loop:

* it waits for the database, because Compose starts everything at once;
* it warms the things a graph run needs — the checkpointer's tables, the policy index and the
  calibration curve — before accepting a task, so the first case is not slower than the rest;
* it waits for Conductor and registers the definitions, retrying rather than exiting, so a
  worker started before Conductor comes up recovers by itself;
* it stops cleanly on SIGTERM, letting the task in flight finish.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys

from sqlalchemy import text

from app.agent import runner
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.process import definition
from app.process.conductor import ConductorEngine
from app.process.worker import WorkerPool
from app.services import assurance, pipeline

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("wathiq.worker")

# The worker long-polls six queues every second. At INFO, httpx would log a line for each one,
# and the worker's own messages would be lost in it.
logging.getLogger("httpx").setLevel(logging.WARNING)

DB_WAIT_ATTEMPTS = 60
DB_WAIT_SECONDS = 2.0
CONDUCTOR_WAIT_SECONDS = 5.0


async def _wait_for_database() -> None:
    for attempt in range(1, DB_WAIT_ATTEMPTS + 1):
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            logger.info("database ready")
            return
        except Exception as exc:
            if attempt == DB_WAIT_ATTEMPTS:
                raise
            logger.info("waiting for the database (%d): %s", attempt, type(exc).__name__)
            await asyncio.sleep(DB_WAIT_SECONDS)


async def _warm_up() -> None:
    """Everything a graph run needs, prepared before the first task is accepted."""
    await runner.get_checkpointer()
    logger.info("agent checkpointer ready")
    try:
        async with SessionLocal() as db:
            built = await assurance.ensure_policy_index(db)
            if built:
                logger.info("policy index built: %d chunk(s)", built)
            curve = await assurance.load_active(db)
            logger.info(
                "confidence calibration: %s",
                f"fitted on {curve.sample_count} reviewed field(s)"
                if curve.fitted
                else "not fitted yet — raw scores shown as raw",
            )
    except Exception:
        # The same degradation the API accepts: no citations, uncalibrated scores, and both
        # say so in the UI. A worker that refuses to start would be worse.
        logger.exception("assurance warm-up failed; continuing with degraded assurance")


async def _register(conductor: ConductorEngine) -> None:
    """Keep trying until Conductor accepts the definitions."""
    while True:
        reachable, detail = await conductor.client.health()
        if reachable and await conductor.ensure_registered(force=True):
            logger.info(
                "registered %s v%d with Conductor at %s",
                definition.WORKFLOW_NAME,
                definition.WORKFLOW_VERSION,
                conductor.client.base_url,
            )
            return
        logger.info("waiting for Conductor at %s: %s", conductor.client.base_url, detail)
        await asyncio.sleep(CONDUCTOR_WAIT_SECONDS)


async def main() -> int:
    if not settings.conductor_url:
        logger.error(
            "WATHIQ_CONDUCTOR_URL is not set. The worker has nothing to poll — the API's "
            "in-process engine runs the process when Conductor is switched off."
        )
        return 2

    logger.info("Wathiq Conductor worker starting (%s mode)", settings.mode)
    await _wait_for_database()
    await _warm_up()

    conductor = ConductorEngine()
    await _register(conductor)

    pool = WorkerPool(conductor.client)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows has no SIGTERM handler
            loop.add_signal_handler(sig, pool.request_stop)

    try:
        await pool.run()
    finally:
        logger.info("worker stopping: %s", pool.summary())
        await pipeline.drain(timeout=30.0)
        await conductor.client.close()
        await runner.close_checkpointer()
        await engine.dispose()
        logger.info("worker stopped")
    return 0


if __name__ == "__main__":  # pragma: no cover - container entry point
    sys.exit(asyncio.run(main()))
