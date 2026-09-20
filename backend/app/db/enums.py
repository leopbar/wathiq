"""Domain enums.

These are stored as short strings (not native PostgreSQL enums) so that adding a value is a
code change plus a CHECK-constraint migration, never a blocking `ALTER TYPE` on a live table.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ops_officer = "ops_officer"
    reviewer = "reviewer"
    supervisor = "supervisor"
    admin = "admin"
    auditor = "auditor"


class CaseStatus(StrEnum):
    intake = "intake"
    processing = "processing"
    needs_review = "needs_review"
    in_review = "in_review"
    approved = "approved"
    posting = "posting"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"


TERMINAL_STATUSES = {CaseStatus.completed, CaseStatus.rejected, CaseStatus.failed}


class CaseType(StrEnum):
    kyc_refresh = "kyc_refresh"
    salary_certificate = "salary_certificate"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Priority(StrEnum):
    normal = "normal"
    high = "high"
    urgent = "urgent"


class DocTypeKey(StrEnum):
    trade_license = "trade_license"
    emirates_id = "emirates_id"
    passport = "passport"
    moa = "moa"
    salary_certificate = "salary_certificate"
    unknown = "unknown"


class DocumentStatus(StrEnum):
    uploaded = "uploaded"
    ocr = "ocr"
    classified = "classified"
    extracted = "extracted"
    failed = "failed"


class Language(StrEnum):
    en = "en"
    ar = "ar"
    mixed = "mixed"


class FieldStatus(StrEnum):
    auto_accepted = "auto_accepted"
    needs_review = "needs_review"
    corrected = "corrected"
    rejected = "rejected"


class Severity(StrEnum):
    info = "info"
    warning = "warning"
    critical = "critical"


class FindingStatus(StrEnum):
    open = "open"
    resolved = "resolved"
    waived = "waived"


class ActorType(StrEnum):
    user = "user"
    agent = "agent"
    system = "system"


class ReviewReason(StrEnum):
    mandatory = "mandatory"
    dynamic = "dynamic"


class ReviewStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class ReviewDecision(StrEnum):
    approve = "approve"
    correct = "correct"
    reject = "reject"
    escalate = "escalate"


class PromptStatus(StrEnum):
    draft = "draft"
    approved = "approved"
    retired = "retired"


class QualityBand(StrEnum):
    model = "model"
    prompt = "prompt"
    agent = "agent"
    ai_security = "ai_security"
    adversarial = "adversarial"


class IntegrationStatus(StrEnum):
    connected = "connected"
    simulated = "simulated"
    demo = "demo"
    disabled = "disabled"
