"""Wathiq API entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.session import engine

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("wathiq")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Wathiq API starting in %s mode (v%s)", settings.mode, settings.app_version)
    yield
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
