from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import ReviewDecision
from app.schemas.case import CaseDetail, ReviewTaskOut


class FieldCorrection(BaseModel):
    field_id: UUID
    value: str = Field(max_length=2000)


class ReviewDecisionRequest(BaseModel):
    decision: ReviewDecision
    reason_code: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=2000)
    field_corrections: list[FieldCorrection] = Field(default_factory=list)


class ReasonCode(BaseModel):
    code: str
    label: str
    applies_to: list[ReviewDecision]


class ReviewTaskDetail(BaseModel):
    task: ReviewTaskOut
    case: CaseDetail
