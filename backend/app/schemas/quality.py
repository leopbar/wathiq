from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.db.enums import QualityBand
from app.schemas.common import Schema


class BandSummary(BaseModel):
    band: QualityBand
    label: str
    description: str
    passed: int
    failed: int
    total: int
    score: float
    last_run_at: datetime | None


class QualitySummary(BaseModel):
    bands: list[BandSummary]
    overall_score: float
    total_cases: int
    regression_cases: int


class QualityRunOut(Schema):
    id: UUID
    band: QualityBand
    started_at: datetime
    finished_at: datetime | None
    passed: int
    failed: int
    score: float
    triggered_by: str
    commit_sha: str


class QualityCaseOut(Schema):
    id: UUID
    name: str
    band: QualityBand
    passed: bool
    expected: str
    actual: str
    note: str
    is_regression: bool


class QualityRunDetail(BaseModel):
    run: QualityRunOut
    cases: list[QualityCaseOut]


class CalibrationPointOut(Schema):
    predicted: float
    observed: float
    n: int


class Calibration(BaseModel):
    points: list[CalibrationPointOut]
    ece: float
    brier: float
    model_version: str


class RunRequest(BaseModel):
    # "all" runs every band; the UI offers it as the default action.
    band: QualityBand | Literal["all"] = "all"
