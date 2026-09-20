"""Wathiq API entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.agent import runner
from app.api.v1 import api_router
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


@app.get("/healthz", tags=["system"], summary="Liveness and database check")
async def healthz() -> dict[str, Any]:
    db_ok = True
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "down",
        "mode": settings.mode,
        "version": settings.app_version,
    }
