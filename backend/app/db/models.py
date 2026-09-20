"""Database models.

Design notes worth being able to explain:
- One append-only `events` table backs BOTH the per-case timeline and the audit log. The audit log
  is simply the unfiltered view. Nothing in the codebase updates or deletes a row here.
- A case carries `thread_id`: the Conductor workflow id, which is also the LangGraph thread id.
  One identifier ties the business process, the AI reasoning and the audit trail together.
- Enums are stored as short strings with a CHECK constraint (see db/enums.py for why).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import event as sa_event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import enums
from app.db.base import Base, created_at_col, updated_at_col, uuid_pk


def _enum(enum_cls: type, name: str) -> SAEnum:
    """Store enums as VARCHAR + CHECK rather than a native PostgreSQL type."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda e: [member.value for member in e],
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    full_name_ar: Mapped[str] = mapped_column(String(160), default="")
    role: Mapped[enums.Role] = mapped_column(_enum(enums.Role, "role"), index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at_col()


class DocumentType(Base):
    """A document type is configuration: schema, prompt key and rule set.

    Onboarding a new document type (use case 2) must only add rows here — never engine code.
    """

    __tablename__ = "document_types"

    id: Mapped[UUID] = uuid_pk()
    key: Mapped[enums.DocTypeKey] = mapped_column(
        _enum(enums.DocTypeKey, "doc_type_key"), unique=True, index=True
    )
    name_en: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    prompt_key: Mapped[str] = mapped_column(String(80), default="")
    rules_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    # JSON schema of the fields to extract: [{name,label_en,label_ar,type,required,is_critical}]
    field_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[UUID] = uuid_pk()
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    case_type: Mapped[enums.CaseType] = mapped_column(_enum(enums.CaseType, "case_type"))
    customer_name: Mapped[str] = mapped_column(String(200), index=True)
    customer_name_ar: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[enums.CaseStatus] = mapped_column(
        _enum(enums.CaseStatus, "case_status"), index=True
    )
    risk_level: Mapped[enums.RiskLevel] = mapped_column(
        _enum(enums.RiskLevel, "risk_level"), default=enums.RiskLevel.low
    )
    priority: Mapped[enums.Priority] = mapped_column(
        _enum(enums.Priority, "priority"), default=enums.Priority.normal
    )
    notes: Mapped[str] = mapped_column(Text, default="")

    # Conductor workflow id == LangGraph thread id.
    thread_id: Mapped[str] = mapped_column(String(64), index=True)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    straight_through: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="selectin")
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="selectin")
    documents: Mapped[list[Document]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Document.created_at"
    )
    fields: Mapped[list[ExtractedField]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="ExtractedField.order_index"
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Finding.created_at"
    )
    review_tasks: Mapped[list[ReviewTask]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="ReviewTask.created_at"
    )

    __table_args__ = (Index("ix_cases_status_created", "status", "created_at"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = uuid_pk()
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[enums.DocTypeKey] = mapped_column(
        _enum(enums.DocTypeKey, "document_doc_type"), default=enums.DocTypeKey.unknown
    )
    language: Mapped[enums.Language] = mapped_column(
        _enum(enums.Language, "language"), default=enums.Language.en
    )
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    storage_path: Mapped[str] = mapped_column(String(512), default="")
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[enums.DocumentStatus] = mapped_column(
        _enum(enums.DocumentStatus, "document_status"), default=enums.DocumentStatus.uploaded
    )
    created_at: Mapped[datetime] = created_at_col()

    case: Mapped[Case] = relationship(back_populates="documents")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[UUID] = uuid_pk()
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    label_en: Mapped[str] = mapped_column(String(120))
    label_ar: Mapped[str] = mapped_column(String(120), default="")
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    calibrated_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[enums.FieldStatus] = mapped_column(
        _enum(enums.FieldStatus, "field_status"), default=enums.FieldStatus.auto_accepted
    )
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Normalised [x, y, w, h] in 0..1 so the UI can overlay it on any render size.
    bbox: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The signals the confidence was built from: OCR quality, grounding, label match, shape,
    # critic agreement. Stored so the case screen can show WHY a number is what it is.
    signals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = created_at_col()

    case: Mapped[Case] = relationship(back_populates="fields")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = uuid_pk()
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[enums.Severity] = mapped_column(_enum(enums.Severity, "severity"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    policy_citation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    policy_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[enums.FindingStatus] = mapped_column(
        _enum(enums.FindingStatus, "finding_status"), default=enums.FindingStatus.open
    )
    created_at: Mapped[datetime] = created_at_col()

    case: Mapped[Case] = relationship(back_populates="findings")


class Event(Base):
    """Append-only event log: the case timeline and the audit trail are views over this table.

    Never updated, never deleted. `seq` gives a stable global order even when timestamps tie.
    """

    __tablename__ = "events"

    _seq = Sequence("events_seq", metadata=Base.metadata)

    id: Mapped[UUID] = uuid_pk()
    seq: Mapped[int] = mapped_column(
        BigInteger, _seq, server_default=_seq.next_value(), unique=True, index=True
    )
    case_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    actor: Mapped[str] = mapped_column(String(160))
    actor_type: Mapped[enums.ActorType] = mapped_column(_enum(enums.ActorType, "actor_type"))
    action: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(300))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (Index("ix_events_case_seq", "case_id", "seq"),)


# "Append-only" is a claim, so the database enforces it rather than the application promising
# it. Without this, a bug — or anyone with the application's own credentials — could quietly
# rewrite history through the same connection the API uses. With it, the attempt fails loudly.
# The audit trail is the one table where that guarantee has to be real.
EVENTS_APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION events_append_only() RETURNS trigger AS $$
BEGIN
    -- The message is built by concatenation rather than with a format placeholder: this
    -- statement is also handed to SQLAlchemy's DDL construct, which treats a per-cent sign as
    -- its own substitution and would fail to compile it.
    RAISE EXCEPTION USING
        MESSAGE = 'events is append-only: ' || TG_OP || ' is not allowed',
        ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS events_no_update_delete ON events;
CREATE TRIGGER events_no_update_delete
    BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION events_append_only();
"""

# Attached to metadata, so the guarantee exists both after an Alembic migration and after
# `create_all` in the test database. A rule that only holds in production is not a rule.
sa_event.listen(
    Event.__table__,
    "after_create",
    DDL(EVENTS_APPEND_ONLY_SQL).execute_if(dialect="postgresql"),
)


class Posting(Base):
    """One attempt to hand an approved case to the system of record.

    The row exists whatever the outcome — posted, skipped or failed — because "we did not post
    this, and here is why" is exactly the kind of thing an auditor asks about.

    `idempotency_key` is UNIQUE. That is the real guarantee: two workers racing after a
    Conductor redelivery cannot both insert, whatever the application code does. The simulated
    core banking server honours the same key independently, so the protection holds even if
    this table were empty.
    """

    __tablename__ = "postings"

    id: Mapped[UUID] = uuid_pk()
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    # Derived from the case, never random: the same case always produces the same key, which
    # is what makes a retry a retry instead of a second posting.
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[enums.PostingStatus] = mapped_column(
        _enum(enums.PostingStatus, "posting_status")
    )
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_id: Mapped[str] = mapped_column(String(64), default="")
    # "human" or "straight_through_policy" — which authority allowed this posting.
    approval_kind: Mapped[str] = mapped_column(String(40), default="")
    approved_by: Mapped[str] = mapped_column(String(160), default="")
    # True when the system of record recognised the key and returned the original reference.
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[UUID] = uuid_pk()
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    reason: Mapped[enums.ReviewReason] = mapped_column(_enum(enums.ReviewReason, "review_reason"))
    reason_code: Mapped[str] = mapped_column(String(80))
    reason_label: Mapped[str] = mapped_column(String(200))
    status: Mapped[enums.ReviewStatus] = mapped_column(
        _enum(enums.ReviewStatus, "review_status"), default=enums.ReviewStatus.pending, index=True
    )
    assigned_role: Mapped[enums.Role] = mapped_column(
        _enum(enums.Role, "review_assigned_role"), default=enums.Role.reviewer
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set once, the first time the SLA timer found this review still open. Both engines check
    # it before escalating, so a re-delivered timer cannot escalate the same review twice.
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[enums.ReviewDecision | None] = mapped_column(
        _enum(enums.ReviewDecision, "review_decision"), nullable=True
    )
    decision_reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    case: Mapped[Case] = relationship(back_populates="review_tasks")
    assigned_to: Mapped[User | None] = relationship(lazy="selectin")


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    document_type: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    versions: Mapped[list[PromptVersion]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan", order_by="PromptVersion.created_at"
    )


class PromptVersion(Base):
    """Semantic versioning: MAJOR = output schema change, MINOR = new fields, PATCH = wording."""

    __tablename__ = "prompt_versions"

    id: Mapped[UUID] = uuid_pk()
    prompt_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompts.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(20))
    status: Mapped[enums.PromptStatus] = mapped_column(
        _enum(enums.PromptStatus, "prompt_status"), default=enums.PromptStatus.draft
    )
    body: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), default="")
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    prompt: Mapped[Prompt] = relationship(back_populates="versions")

    __table_args__ = (UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),)


class QualityRun(Base):
    __tablename__ = "quality_runs"

    id: Mapped[UUID] = uuid_pk()
    band: Mapped[enums.QualityBand] = mapped_column(
        _enum(enums.QualityBand, "quality_band"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    triggered_by: Mapped[str] = mapped_column(String(120), default="ci")
    commit_sha: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = created_at_col()

    cases: Mapped[list[QualityCase]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class QualityCase(Base):
    __tablename__ = "quality_cases"

    id: Mapped[UUID] = uuid_pk()
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("quality_runs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    band: Mapped[enums.QualityBand] = mapped_column(_enum(enums.QualityBand, "case_quality_band"))
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
    expected: Mapped[str] = mapped_column(Text, default="")
    actual: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    is_regression: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped[QualityRun] = relationship(back_populates="cases")


class CalibrationPoint(Base):
    """Reliability curve: how often a stated confidence was actually right."""

    __tablename__ = "calibration_points"

    id: Mapped[UUID] = uuid_pk()
    predicted: Mapped[float] = mapped_column(Float)
    observed: Mapped[float] = mapped_column(Float)
    n: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        CheckConstraint("predicted >= 0 AND predicted <= 1", name="predicted_range"),
        CheckConstraint("observed >= 0 AND observed <= 1", name="observed_range"),
    )


class CalibrationCurve(Base):
    """The fitted confidence curve: raw score in, calibrated probability out.

    One row per fit, with only the newest marked active. Keeping the old rows means a case
    closed last month can be read with the curve that was in force when it closed.
    """

    __tablename__ = "calibration_curves"

    id: Mapped[UUID] = uuid_pk()
    # Platt scaling: calibrated = sigmoid(a * raw + b). Two parameters, nothing hidden.
    a: Mapped[float] = mapped_column(Float, default=1.0)
    b: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    brier_before: Mapped[float] = mapped_column(Float, default=0.0)
    brier_after: Mapped[float] = mapped_column(Float, default=0.0)
    model_version: Mapped[str] = mapped_column(String(80), default="")
    method: Mapped[str] = mapped_column(String(40), default="platt")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    fitted_at: Mapped[datetime] = created_at_col()


class PolicyChunk(Base):
    """One section of one synthetic policy document, with its embedding.

    This is the RAG index. It lives in the same PostgreSQL database as everything else, using
    the pgvector extension, so there is no separate vector service to run or explain.
    """

    __tablename__ = "policy_chunks"

    id: Mapped[UUID] = uuid_pk()
    policy_id: Mapped[str] = mapped_column(String(40), index=True)
    policy_title: Mapped[str] = mapped_column(String(200), default="")
    section: Mapped[str] = mapped_column(String(20), default="")
    # "KYC-POL-004 §3.2" — exactly the string a rule pack cites, so most look-ups are direct.
    citation: Mapped[str] = mapped_column(String(80), index=True)
    heading: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list[float]] = mapped_column(Vector(256))
    embedder_version: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (UniqueConstraint("citation", name="uq_policy_chunks_citation"),)
