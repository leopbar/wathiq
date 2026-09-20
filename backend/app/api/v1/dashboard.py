"""Dashboard KPIs and charts, computed from the real tables (no pre-baked numbers)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import Float, cast, func, select
from sqlalchemy import case as sql_case

from app.core.deps import CurrentUser, DbSession
from app.db import models
from app.db.enums import CaseStatus, FindingStatus, ReviewStatus
from app.schemas.dashboard import (
    Charts,
    HandlingPoint,
    HistogramBucket,
    Kpis,
    StatusSplit,
    TopFinding,
    VolumePoint,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

CLOSED = (CaseStatus.completed, CaseStatus.rejected)
CHART_DAYS = 14


@router.get("/kpis", response_model=Kpis)
async def kpis(db: DbSession, _: CurrentUser) -> Kpis:
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    prev_week_start = now - timedelta(days=14)

    cases_today = (
        await db.execute(
            select(func.count(models.Case.id)).where(models.Case.created_at >= today_start)
        )
    ).scalar_one()
    cases_total = (await db.execute(select(func.count(models.Case.id)))).scalar_one()

    closed_total, straight_through = (
        await db.execute(
            select(
                func.count(models.Case.id),
                func.count(models.Case.id).filter(models.Case.straight_through.is_(True)),
            ).where(models.Case.status.in_(CLOSED))
        )
    ).one()

    reviewed_cases = (
        await db.execute(select(func.count(func.distinct(models.ReviewTask.case_id))))
    ).scalar_one()

    avg_handling = (
        await db.execute(
            select(func.avg(models.Case.processing_ms)).where(
                models.Case.processing_ms.is_not(None)
            )
        )
    ).scalar_one() or 0

    sla_breaches = (
        await db.execute(
            select(func.count(models.Case.id)).where(
                models.Case.sla_due_at < now,
                models.Case.status.not_in(
                    (CaseStatus.completed, CaseStatus.rejected, CaseStatus.failed)
                ),
            )
        )
    ).scalar_one()

    avg_cost = (
        await db.execute(
            select(func.avg(models.Case.cost_usd)).where(models.Case.cost_usd.is_not(None))
        )
    ).scalar_one() or 0.0

    open_reviews = (
        await db.execute(
            select(func.count(models.ReviewTask.id)).where(
                models.ReviewTask.status != ReviewStatus.completed
            )
        )
    ).scalar_one()

    async def _window_rate(start: datetime, end: datetime) -> float:
        total, stp = (
            await db.execute(
                select(
                    func.count(models.Case.id),
                    func.count(models.Case.id).filter(models.Case.straight_through.is_(True)),
                ).where(
                    models.Case.status.in_(CLOSED),
                    models.Case.created_at >= start,
                    models.Case.created_at < end,
                )
            )
        ).one()
        return (stp / total) if total else 0.0

    this_week = await _window_rate(week_start, now)
    last_week = await _window_rate(prev_week_start, week_start)

    return Kpis(
        cases_today=cases_today,
        cases_total=cases_total,
        straight_through_rate=(straight_through / closed_total) if closed_total else 0.0,
        review_rate=(reviewed_cases / cases_total) if cases_total else 0.0,
        avg_handling_ms=int(avg_handling),
        sla_breaches=sla_breaches,
        avg_cost_usd=round(float(avg_cost), 4),
        open_reviews=open_reviews,
        deltas={"straight_through_rate": round(this_week - last_week, 4)},
    )


@router.get("/charts", response_model=Charts)
async def charts(db: DbSession, _: CurrentUser) -> Charts:
    since = datetime.now(UTC) - timedelta(days=CHART_DAYS)
    day = func.date_trunc("day", models.Case.created_at)

    volume_rows = (
        await db.execute(
            select(
                day.label("day"),
                func.count(models.Case.id).label("total"),
                func.count(models.Case.id)
                .filter(models.Case.straight_through.is_(True))
                .label("stp"),
            )
            .where(models.Case.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
    ).all()
    volume = [
        VolumePoint(
            date=row.day.date().isoformat(),
            total=row.total,
            straight_through=row.stp,
            reviewed=row.total - row.stp,
        )
        for row in volume_rows
    ]

    status_rows = (
        await db.execute(
            select(models.Case.status, func.count(models.Case.id))
            .group_by(models.Case.status)
            .order_by(func.count(models.Case.id).desc())
        )
    ).all()
    status_split = [StatusSplit(status=row[0], count=row[1]) for row in status_rows]

    bucket_expr = sql_case(
        (models.Case.confidence < 0.5, "<50%"),
        (models.Case.confidence < 0.7, "50-70%"),
        (models.Case.confidence < 0.8, "70-80%"),
        (models.Case.confidence < 0.9, "80-90%"),
        (models.Case.confidence < 0.95, "90-95%"),
        else_="95-100%",
    )
    hist_rows = (
        await db.execute(
            select(bucket_expr.label("bucket"), func.count(models.Case.id))
            .where(models.Case.confidence.is_not(None))
            .group_by(bucket_expr)
        )
    ).all()
    order = ["<50%", "50-70%", "70-80%", "80-90%", "90-95%", "95-100%"]
    counts = {row.bucket: row[1] for row in hist_rows}
    histogram = [HistogramBucket(bucket=b, count=counts.get(b, 0)) for b in order]

    handling_rows = (
        await db.execute(
            select(
                day.label("day"),
                func.percentile_cont(0.5)
                .within_group(cast(models.Case.processing_ms, Float))
                .label("p50"),
                func.percentile_cont(0.9)
                .within_group(cast(models.Case.processing_ms, Float))
                .label("p90"),
            )
            .where(models.Case.created_at >= since, models.Case.processing_ms.is_not(None))
            .group_by(day)
            .order_by(day)
        )
    ).all()
    handling = [
        HandlingPoint(
            date=row.day.date().isoformat(),
            p50_ms=int(row.p50 or 0),
            p90_ms=int(row.p90 or 0),
        )
        for row in handling_rows
    ]

    finding_rows = (
        await db.execute(
            select(
                models.Finding.code,
                func.min(models.Finding.title).label("title"),
                func.count(models.Finding.id).label("count"),
            )
            .where(models.Finding.status == FindingStatus.open)
            .group_by(models.Finding.code)
            .order_by(func.count(models.Finding.id).desc())
            .limit(6)
        )
    ).all()
    top_findings = [
        TopFinding(code=row.code, title=row.title, count=row.count) for row in finding_rows
    ]

    return Charts(
        volume_by_day=volume,
        status_split=status_split,
        confidence_histogram=histogram,
        handling_time_by_day=handling,
        top_findings=top_findings,
    )
