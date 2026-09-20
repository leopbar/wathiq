"""Choosing a process engine, and remembering which one ran each case.

`WATHIQ_PROCESS_ENGINE` decides:

* `conductor` — always Conductor. If it is not reachable, starting a case fails loudly. That is
  what a real deployment wants: quietly degrading would hide a broken orchestrator.
* `inprocess` — always the fallback. Useful on a small machine, and in tests.
* `auto` (the default) — Conductor when it answers, the fallback when it does not, and the
  choice is written into the case's event log either way.

**A decision always goes back to the engine that started the case.** A case parked at the human
step may have been started by Conductor an hour ago, while the API has since fallen back — so
the engine is looked up from the case's own `process.started` event, not from today's
configuration. Getting this wrong would leave a Conductor workflow waiting forever for an
answer that went somewhere else.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import models
from app.process import base, definition
from app.process.base import EngineHealth, ProcessEngine, ProcessStatus
from app.process.conductor import ConductorEngine
from app.process.inprocess import InProcessEngine

logger = logging.getLogger(__name__)

_inprocess = InProcessEngine()
_conductor = ConductorEngine()

# In `auto` mode, how long a reachability answer is trusted before asking Conductor again.
PROBE_TTL_SECONDS = 30.0
_probe: tuple[float, bool] | None = None


def by_name(name: str) -> ProcessEngine:
    return _conductor if name == _conductor.name else _inprocess


def configured_engine() -> str:
    return settings.process_engine


async def _conductor_available(force: bool = False) -> bool:
    global _probe
    now = time.monotonic()
    if not force and _probe is not None and now - _probe[0] < PROBE_TTL_SECONDS:
        return _probe[1]
    reachable, detail = await _conductor.client.health()
    if not reachable:
        logger.info("Conductor unavailable: %s", detail)
    _probe = (now, reachable)
    return reachable


async def engine_for_new_case() -> ProcessEngine:
    """The engine a case starting now should use."""
    mode = settings.process_engine
    if mode == "inprocess":
        return _inprocess
    if mode == "conductor":
        return _conductor
    return _conductor if await _conductor_available() else _inprocess


async def engine_for_case(db: AsyncSession, case: models.Case) -> ProcessEngine:
    """The engine that started this case, so its decision goes to the right place."""
    row = (
        await db.execute(
            select(models.Event)
            .where(models.Event.case_id == case.id, models.Event.action == base.STARTED)
            .order_by(models.Event.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        # No recorded start: a seeded demo case, or one created before M4. Today's choice is
        # the only sensible answer, and the fallback can always finish a case.
        return await engine_for_new_case()
    name = str((row.detail or {}).get("engine") or _inprocess.name)
    return by_name(name)


async def engine_name_for_case(db: AsyncSession, case: models.Case) -> str:
    engine = await engine_for_case(db, case)
    return engine.name


# --------------------------------------------------------------------------- lifecycle


async def start() -> None:
    """Called once when the API starts."""
    mode = settings.process_engine
    if mode in ("auto", "conductor"):
        available = await _conductor_available(force=True)
        if available:
            await _conductor.ensure_registered(force=True)
        elif mode == "conductor":
            logger.warning(
                "WATHIQ_PROCESS_ENGINE=conductor but Conductor is not reachable at %s. "
                "Starting a case will fail until it is.",
                settings.conductor_url or "(no URL configured)",
            )

    # The fallback's sweeper and recovery are only wanted when the fallback can actually be
    # used. Under `conductor`, Conductor owns timers and redelivery.
    if mode != "conductor":
        await _inprocess.start()
        if settings.process_recover_on_startup:
            try:
                recovered = await _inprocess.recover()
                if recovered:
                    logger.info("recovered %d case(s) left mid-process", recovered)
            except Exception:
                logger.exception("crash recovery failed; cases may need starting by hand")


async def stop() -> None:
    await _inprocess.stop()
    await _conductor.client.close()


# ----------------------------------------------------------------------------- health


async def health() -> dict[str, Any]:
    """What the Settings and About screens show about the process layer."""
    engines = [await _inprocess.health()]
    if settings.conductor_url:
        engines.append(await _conductor.health())
    chosen = (await engine_for_new_case()).name
    return {
        "configured": settings.process_engine,
        "active": chosen,
        "fell_back": settings.process_engine == "auto" and chosen == _inprocess.name,
        "engines": [item.as_dict() for item in engines],
        "process": definition.describe(),
    }


__all__ = [
    "EngineHealth",
    "ProcessEngine",
    "ProcessStatus",
    "by_name",
    "configured_engine",
    "engine_for_case",
    "engine_for_new_case",
    "engine_name_for_case",
    "health",
    "start",
    "stop",
]
