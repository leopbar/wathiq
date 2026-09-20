from __future__ import annotations

from pydantic import BaseModel

from app.db import enums


class Kpis(BaseModel):
    cases_today: int
    cases_total: int
    straight_through_rate: float
    review_rate: float
    avg_handling_ms: int
    sla_breaches: int
    avg_cost_usd: float
    open_reviews: int
    deltas: dict[str, float]


class VolumePoint(BaseModel):
    date: str
    total: int
    straight_through: int
    reviewed: int


class StatusSplit(BaseModel):
    status: enums.CaseStatus
    count: int


class HistogramBucket(BaseModel):
    bucket: str
    count: int


class HandlingPoint(BaseModel):
    date: str
    p50_ms: int
    p90_ms: int


class TopFinding(BaseModel):
    code: str
    title: str
    count: int


class Charts(BaseModel):
    volume_by_day: list[VolumePoint]
    status_split: list[StatusSplit]
    confidence_histogram: list[HistogramBucket]
    handling_time_by_day: list[HandlingPoint]
    top_findings: list[TopFinding]
