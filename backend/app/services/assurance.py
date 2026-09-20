"""Database-facing work for calibration and the policy index.

`app/agent/calibration.py` is pure arithmetic with no imports from the database, so it can be
tested on its own and reasoned about on a whiteboard. This module is the part that talks to
PostgreSQL: where the training examples come from, where the fitted curve is stored, and how
the index is kept warm.

Ground truth, stated plainly: a field is **right** if a reviewer looked at the case and did not
change it, and **wrong** if they corrected it. Only cases a human actually completed count.
Fields from cases that went straight through are excluded — nobody checked them, so they are
not evidence either way, and counting them as "right" would teach the curve to be
over-confident about exactly the cases nobody verified.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import calibration
from app.db import models
from app.db.enums import FieldStatus, ReviewDecision, ReviewStatus
from app.quality.tracking import track_fit
from app.rag import index as policy_index

logger = logging.getLogger(__name__)


async def collect_samples(db: AsyncSession) -> list[tuple[float, bool]]:
    """(raw confidence, was it right) for every field a human verified."""
    reviewed_cases = select(models.ReviewTask.case_id).where(
        models.ReviewTask.status == ReviewStatus.completed,
        models.ReviewTask.decision.in_([ReviewDecision.approve, ReviewDecision.correct]),
    )
    rows = (
        await db.execute(
            select(models.ExtractedField.confidence, models.ExtractedField.status).where(
                models.ExtractedField.case_id.in_(reviewed_cases)
            )
        )
    ).all()
    return [
        (float(confidence), status != FieldStatus.corrected) for confidence, status in rows
    ]


async def load_active(db: AsyncSession) -> calibration.CalibrationCurve:
    """Read the active curve into the process. Falls back to the identity curve."""
    row = (
        await db.execute(
            select(models.CalibrationCurve)
            .where(models.CalibrationCurve.is_active.is_(True))
            .order_by(models.CalibrationCurve.fitted_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if row is None:
        curve = calibration.CalibrationCurve()
        attempt = (await db.execute(select(models.CalibrationExperiment).order_by(
            models.CalibrationExperiment.created_at.desc()).limit(1))).scalar_one_or_none()
        if attempt and not attempt.result.get("fitted"):
            curve.sample_count = attempt.result.get("sample_count", 0)
            curve.model_version = attempt.result.get("model_version", "")
    else:
        curve = calibration.CalibrationCurve(
            a=row.a,
            b=row.b,
            fitted=True,
            sample_count=row.sample_count,
            brier_before=row.brier_before,
            brier_after=row.brier_after,
            model_version=row.model_version,
        )
    calibration.set_active(curve)
    return curve


async def refit(
    db: AsyncSession, *, model_version: str = "demo-extractor-1.0.0"
) -> calibration.CalibrationCurve:
    """Fit a new curve on the reviewer outcomes and make it the active one.

    Also rewrites the reliability bins that the Quality Lab chart reads, so the chart and the
    curve can never describe different data.
    """
    samples = await collect_samples(db)
    curve = calibration.fit(samples, model_version=model_version)

    # A refused refit must not leave a previous curve active in the database while this
    # process and its chart say raw. Persist every attempt, including refusals.
    await db.execute(update(models.CalibrationCurve).values(is_active=False))
    db.add(models.CalibrationExperiment(result=curve.as_dict(),
                                        tracking=await track_fit(curve.as_dict())))

    if curve.fitted:
        db.add(
            models.CalibrationCurve(
                a=curve.a,
                b=curve.b,
                sample_count=curve.sample_count,
                brier_before=curve.brier_before,
                brier_after=curve.brier_after,
                model_version=curve.model_version,
                method="platt",
                is_active=True,
            )
        )

    # The chart shows what the *active* curve produces, so bin with the same curve.
    bins = calibration.reliability(samples, curve if curve.fitted else None)
    await db.execute(
        delete(models.CalibrationPoint).where(
            models.CalibrationPoint.model_version == model_version
        )
    )
    for point in bins:
        db.add(
            models.CalibrationPoint(
                predicted=point.predicted,
                observed=point.observed,
                n=point.n,
                model_version=model_version,
            )
        )

    await db.flush()
    calibration.set_active(curve)
    logger.info(
        "calibration refit: fitted=%s samples=%d improvement=%s",
        curve.fitted,
        curve.sample_count,
        curve.improvement,
    )
    return curve


async def ensure_policy_index(db: AsyncSession) -> int:
    """Build the policy index if it is empty. Cheap enough to check at every startup."""
    if await policy_index.is_indexed(db):
        return 0
    count = await policy_index.rebuild(db)
    await db.commit()
    return count
