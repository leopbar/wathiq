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


class CurveOut(BaseModel):
    """The fitted mapping from a raw score to a calibrated probability."""

    a: float
    b: float
    fitted: bool
    sample_count: int
    brier_before: float
    brier_after: float
    improvement: float
    model_version: str


class Calibration(BaseModel):
    points: list[CalibrationPointOut]
    ece: float
    brier: float
    model_version: str
    # The curve itself, so the chart can say whether the numbers on it went through one.
    curve: CurveOut
    method: str = "Platt scaling (one logistic curve, two parameters)"
    ground_truth: str = (
        "Every field a reviewer looked at: accepted means the extractor was right, corrected "
        "means it was wrong. Only cases a human completed are counted."
    )


class RunRequest(BaseModel):
    # "all" runs every band; the UI offers it as the default action.
    band: QualityBand | Literal["all"] = "all"
