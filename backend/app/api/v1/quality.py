"""Quality Lab: five test bands, regression history and confidence calibration.

M1 reads the seeded results. M5 runs the real evaluation suites and writes rows here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.errors import NotFoundError
from app.db import models
from app.db.enums import QualityBand, Role
from app.schemas.common import Page
from app.schemas.quality import (
    BandSummary,
    Calibration,
    CalibrationPointOut,
    QualityCaseOut,
    QualityRunDetail,
    QualityRunOut,
    QualitySummary,
    RunRequest,
)
from app.services.catalog import BAND_LABELS

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("/summary", response_model=QualitySummary)
async def summary(db: DbSession, _: CurrentUser) -> QualitySummary:
    """Latest run per band."""
    latest = (
        select(
            models.QualityRun.band,
            func.max(models.QualityRun.started_at).label("started_at"),
        )
        .group_by(models.QualityRun.band)
        .subquery()
    )
    rows = (
        await db.execute(
            select(models.QualityRun).join(
                latest,
                (models.QualityRun.band == latest.c.band)
                & (models.QualityRun.started_at == latest.c.started_at),
            )
        )
    ).scalars().all()
    by_band = {run.band: run for run in rows}

    bands: list[BandSummary] = []
    for band in QualityBand:
        label, description = BAND_LABELS[band]
        run = by_band.get(band)
        bands.append(
            BandSummary(
                band=band,
                label=label,
                description=description,
                passed=run.passed if run else 0,
                failed=run.failed if run else 0,
                total=(run.passed + run.failed) if run else 0,
                score=run.score if run else 0.0,
                last_run_at=run.started_at if run else None,
            )
        )

    total_cases = sum(b.total for b in bands)
    passed = sum(b.passed for b in bands)
    regressions = (
        await db.execute(
            select(func.count(models.QualityCase.id)).where(
                models.QualityCase.is_regression.is_(True)
            )
        )
    ).scalar_one()

    return QualitySummary(
        bands=bands,
        overall_score=round(passed / total_cases, 4) if total_cases else 0.0,
        total_cases=total_cases,
        regression_cases=regressions,
    )


@router.get("/runs", response_model=Page[QualityRunOut])
async def list_runs(
    db: DbSession,
    _: CurrentUser,
    band: QualityBand | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[QualityRunOut]:
    stmt = select(models.QualityRun).order_by(models.QualityRun.started_at.desc())
    if band:
        stmt = stmt.where(models.QualityRun.band == band)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    runs = (
        await db.execute(stmt.offset((page - 1) * size).limit(size))
    ).scalars().all()
    return Page.build(
        [QualityRunOut.model_validate(r) for r in runs], total=total, page=page, size=size
    )


@router.get("/runs/{run_id}", response_model=QualityRunDetail)
async def run_detail(run_id: UUID, db: DbSession, _: CurrentUser) -> QualityRunDetail:
    run = (
        await db.execute(
            select(models.QualityRun)
            .where(models.QualityRun.id == run_id)
            .options(selectinload(models.QualityRun.cases))
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Evaluation run")
    return QualityRunDetail(
        run=QualityRunOut.model_validate(run),
        cases=[QualityCaseOut.model_validate(c) for c in run.cases],
    )


@router.get("/calibration", response_model=Calibration)
async def calibration(db: DbSession, _: CurrentUser) -> Calibration:
    points = (
        await db.execute(
            select(models.CalibrationPoint).order_by(models.CalibrationPoint.predicted)
        )
    ).scalars().all()

    total = sum(p.n for p in points) or 1
    # Expected Calibration Error: weighted average gap between promise and reality.
    ece = sum(abs(p.predicted - p.observed) * p.n for p in points) / total
    brier = sum(((p.predicted - p.observed) ** 2) * p.n for p in points) / total

    return Calibration(
        points=[CalibrationPointOut.model_validate(p) for p in points],
        ece=round(ece, 4),
        brier=round(brier, 4),
        model_version=points[0].model_version if points else "",
    )


@router.post("/runs", response_model=QualityRunOut)
async def start_run(
    payload: RunRequest,
    db: DbSession,
    _: Annotated[models.User, Depends(require_roles(Role.admin, Role.supervisor, Role.reviewer))],
) -> QualityRunOut:
    """M1: returns the most recent run (for the band, or overall). M5 runs a real evaluation."""
    stmt = select(models.QualityRun).order_by(models.QualityRun.started_at.desc()).limit(1)
    if payload.band != "all":
        stmt = stmt.where(models.QualityRun.band == payload.band)

    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Evaluation run for this band")
    return QualityRunOut.model_validate(run)
