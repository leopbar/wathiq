"""Quality Lab: five test bands, regression history and confidence calibration.

M1 reads the seeded results. M5 runs the real evaluation suites and writes rows here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.agent import calibration as calibration_math
from app.core.deps import CurrentUser, DbSession, require_roles
from app.core.errors import NotFoundError
from app.db import models
from app.db.enums import QualityBand, Role
from app.quality.dataset import archive
from app.quality.service import evaluate
from app.schemas.common import Page
from app.schemas.quality import (
    BandSummary,
    Calibration,
    CalibrationPointOut,
    CurveOut,
    QualityCaseOut,
    QualityRunDetail,
    QualityRunOut,
    QualitySummary,
    RunBatch,
    RunRequest,
)
from app.services import assurance
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
        .where(models.QualityRun.provenance["kind"].astext == "measured")
        .group_by(models.QualityRun.band)
        .subquery()
    )
    rows = (
        (
            await db.execute(
                select(models.QualityRun).join(
                    latest,
                    (models.QualityRun.band == latest.c.band)
                    & (models.QualityRun.started_at == latest.c.started_at),
                )
            )
        )
        .scalars()
        .all()
    )
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
    regressions = (await db.execute(select(func.count(models.RegressionExample.id)))).scalar_one()

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
    runs = (await db.execute(stmt.offset((page - 1) * size).limit(size))).scalars().all()
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
    samples = await assurance.collect_samples(db)
    curve = await assurance.load_active(db)
    points = calibration_math.reliability(samples, curve)
    latest = (
        await db.execute(
            select(models.CalibrationExperiment)
            .order_by(models.CalibrationExperiment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    total = sum(p.n for p in points) or 1
    # Expected Calibration Error: weighted average gap between promise and reality.
    ece = sum(abs(p.predicted - p.observed) * p.n for p in points) / total
    brier = sum((curve.apply(raw) - int(correct)) ** 2 for raw, correct in samples) / total

    return Calibration(
        points=[
            CalibrationPointOut(predicted=p.predicted, observed=p.observed, n=p.n) for p in points
        ],
        ece=round(ece, 4),
        brier=round(brier, 4),
        model_version=curve.model_version,
        curve=CurveOut(**curve.as_dict()),
        sample_count=len(samples),
        tracking=latest.tracking if latest else {"status": "not_run"},
    )


@router.post("/calibration/refit", response_model=Calibration)
async def refit_calibration(
    db: DbSession,
    _: Annotated[models.User, Depends(require_roles(Role.admin, Role.supervisor))],
) -> Calibration:
    """Fit the confidence curve again on everything reviewers have decided so far.

    The training examples are free and they grow every day: a field a reviewer accepted was
    read correctly, a field they corrected was not. Refitting turns that into a better answer
    to "how often is the extractor right when it says it is this sure".

    If there is too little data, or the fit would be worse than doing nothing, the curve stays
    unfitted and the scores stay raw — which the UI then says out loud.
    """
    await assurance.refit(db)
    await db.commit()
    return await calibration(db, _)


@router.get("/dataset")
async def download_dataset(_: CurrentUser) -> Response:
    return Response(
        await run_in_threadpool(archive),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="wathiq-golden.zip"'},
    )


@router.get("/regressions/export")
async def export_regressions(db: DbSession, _: CurrentUser) -> list[dict]:
    rows = (await db.execute(select(models.RegressionExample).order_by(
        models.RegressionExample.created_at, models.RegressionExample.id))).scalars().all()
    return [{key: getattr(row, key) for key in (
        "source_key", "document_type", "field_name", "expected", "input_text", "field_schema"
    )} for row in rows]


@router.post("/runs", response_model=RunBatch)
async def start_run(
    payload: RunRequest,
    db: DbSession,
    _: Annotated[models.User, Depends(require_roles(Role.admin, Role.supervisor, Role.reviewer))],
) -> RunBatch:
    runs = await evaluate(db, payload.band, actor=_.full_name)
    await db.commit()
    return RunBatch(runs=[QualityRunOut.model_validate(run) for run in runs])
