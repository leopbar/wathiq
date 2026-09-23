"""Wathiq API entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.agent import runner
from app.api.v1 import api_router
from app.azure import monitor
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.session import SessionLocal, engine
from app.process import start as start_process_layer
from app.process import stop as stop_process_layer
from app.services import assurance, pipeline

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("wathiq")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Wathiq API starting in %s mode (v%s)", settings.mode, settings.app_version)
    # Tracing first, so the startup work below is itself inside a trace when it is switched on.
    # A no-op when APPLICATIONINSIGHTS_CONNECTION_STRING is not set, which is the default.
    monitor.configure()
    # Two things the pipeline needs ready before the first case arrives: the policy index
    # (built once, then reused) and the calibration curve (held in memory so scoring a field
    # never touches the database). Neither is fatal if it fails — the pipeline degrades to
    # "no citation" and "uncalibrated", and both say so rather than pretending.
    try:
        # The checkpointer creates its own tables and indexes the first time it is used. Doing
        # that here, before the server accepts traffic, keeps schema creation out of the first
        # case's critical path — and away from the open transactions that ordinary requests
        # would otherwise be holding while `CREATE INDEX CONCURRENTLY` waits for them.
        await runner.get_checkpointer()
        logger.info("agent checkpointer ready")

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
        logger.exception("startup preparation failed; continuing with degraded assurance")

    # The process layer last, because it may pick up cases a crash left half-finished, and
    # those runs need the checkpointer and the policy index that were just made ready.
    try:
        await start_process_layer()
    except Exception:
        logger.exception("the process layer failed to start; cases cannot be processed")

    yield
    await stop_process_layer()
    # Let in-flight pipeline runs finish before the pools close, so a case is never left
    # half-written when the container is asked to stop.
    await pipeline.drain()
    await runner.close_checkpointer()
    await engine.dispose()
    logger.info("Wathiq API stopped")


app = FastAPI(
    title="Wathiq API",
    version=settings.app_version,
    summary="Assurance-first intelligent document processing for banking operations.",
    description=(
        "Two layers: Orkes Conductor runs the business process, LangGraph runs the AI reasoning "
        "inside the agent task. Demo mode runs fully offline."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(api_router, prefix=settings.api_prefix)


async def _database_ok() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


@app.get("/healthz", tags=["system"], summary="Liveness and database check")
async def healthz() -> dict[str, Any]:
    """Is the process alive? Always 200 while it can answer at all.

    Reports the database as a *fact*, and deliberately does not fail on it. This is what a
    liveness probe reads, and a liveness probe that fails when the database is unreachable
    restarts the API in a loop for something restarting cannot fix — while killing every case
    that was mid-run. `/readyz` is the one that fails.
    """
    db_ok = await _database_ok()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "down",
        "mode": settings.mode,
        "version": settings.app_version,
    }


@app.get("/readyz", tags=["system"], summary="Readiness: can this instance serve traffic?")
async def readyz(response: Response) -> dict[str, Any]:
    """Can this instance actually serve? **503 when it cannot.**

    Separate from `/healthz` on purpose, and the difference is the status code. A readiness
    probe decides whether a pod is in the Service; a liveness probe decides whether it is
    killed. An instance that cannot reach PostgreSQL can serve nothing useful, so it should
    leave the load balancer — and should not be restarted, because the problem is not in this
    process. (M6, for the AKS deployment.)
    """
    db_ok = await _database_ok()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if db_ok else "not-ready",
        "db": "ok" if db_ok else "down",
        "mode": settings.mode,
        "version": settings.app_version,
    }
