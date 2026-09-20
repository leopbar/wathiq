from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db import enums
from app.schemas.common import Schema, UserRef

SlaState = Literal["on_track", "at_risk", "breached", "none"]


class DocumentOut(Schema):
    id: UUID
    case_id: UUID
    filename: str
    doc_type: enums.DocTypeKey
    doc_type_label: str
    language: enums.Language
    mime_type: str
    size_bytes: int
    page_count: int
    ocr_confidence: float | None
    classification_confidence: float | None
    status: enums.DocumentStatus
    preview_url: str
    created_at: datetime


class ExtractedFieldOut(Schema):
    id: UUID
    case_id: UUID
    document_id: UUID | None
    name: str
    label_en: str
    label_ar: str
    value: str | None
    corrected_value: str | None
    confidence: float
    calibrated_confidence: float
    status: enums.FieldStatus
    is_critical: bool
    page: int | None
    bbox: list[float] | None
    source_text: str | None
    # What the confidence was built from: OCR quality, grounding, label match, shape, critic.
    signals: list[dict[str, Any]] | None = None


class FindingOut(Schema):
    id: UUID
    case_id: UUID
    code: str
    severity: enums.Severity
    title: str
    description: str
    policy_citation: str | None
    policy_quote: str | None
    status: enums.FindingStatus
    created_at: datetime


class TimelineEventOut(Schema):
    id: UUID
    case_id: UUID | None
    actor: str
    actor_type: enums.ActorType
    action: str
    label: str
    detail: dict[str, Any] | None
    prompt_version: str | None
    model_version: str | None
    duration_ms: int | None
    created_at: datetime


class ReviewTaskOut(Schema):
    id: UUID
    case_id: UUID
    case_reference: str
    customer_name: str
    reason: enums.ReviewReason
    reason_code: str
    reason_label: str
    status: enums.ReviewStatus
    assigned_role: enums.Role
    assigned_to: UserRef | None
    sla_due_at: datetime | None
    sla_state: SlaState
    decision: enums.ReviewDecision | None
    decision_reason_code: str | None
    decision_note: str | None
    created_at: datetime
    completed_at: datetime | None
    field_count: int
    open_finding_count: int


class CaseSummary(Schema):
    id: UUID
    reference: str
    case_type: enums.CaseType
    customer_name: str
    customer_name_ar: str
    status: enums.CaseStatus
    risk_level: enums.RiskLevel
    priority: enums.Priority
    confidence: float | None
    document_count: int
    finding_count: int
    open_finding_count: int
    straight_through: bool
    assigned_to: UserRef | None
    sla_due_at: datetime | None
    sla_state: SlaState
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    processing_ms: int | None
    cost_usd: float | None


class CaseDetail(CaseSummary):
    thread_id: str
    notes: str
    created_by: UserRef | None
    documents: list[DocumentOut]
    fields: list[ExtractedFieldOut]
    findings: list[FindingOut]
    timeline: list[TimelineEventOut]
    review_tasks: list[ReviewTaskOut]


class CaseCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=200)
    customer_name_ar: str = Field(default="", max_length=200)
    case_type: enums.CaseType = enums.CaseType.kyc_refresh
    priority: enums.Priority = enums.Priority.normal
    notes: str = Field(default="", max_length=2000)


class CaseStartResponse(BaseModel):
    thread_id: str
    status: enums.CaseStatus


class AssuranceOut(Schema):
    """The evidence behind a case, read from the graph's own checkpoint.

    `available` is false for a seeded demo case: it was written straight into the database and
    never ran through the graph, so there is no checkpoint to read. Saying so is better than
    showing an empty panel that looks like a failure.
    """

    available: bool
    note: str = ""
    thread_id: str = ""
    guardrails: list[dict[str, Any]] = Field(default_factory=list)
    worker_results: list[dict[str, Any]] = Field(default_factory=list)
    critic_notes: list[dict[str, Any]] = Field(default_factory=list)
    investigation: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    rule_packs: dict[str, str] = Field(default_factory=dict)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    calibration: dict[str, Any] = Field(default_factory=dict)
    review_reasons: list[dict[str, str]] = Field(default_factory=list)
