"""Model -> schema mapping. Kept out of the routers so every endpoint answers identically."""

from __future__ import annotations

from app.core.config import settings
from app.db import models
from app.db.enums import FindingStatus
from app.schemas.case import (
    CaseDetail,
    CaseSummary,
    DocumentOut,
    ExtractedFieldOut,
    FindingOut,
    ReviewTaskOut,
    TimelineEventOut,
)
from app.schemas.common import UserRef
from app.services.catalog import DOC_TYPE_LABELS
from app.services.sla import sla_state


def user_ref(user: models.User | None) -> UserRef | None:
    return UserRef(id=user.id, full_name=user.full_name) if user else None


def document_out(doc: models.Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        case_id=doc.case_id,
        filename=doc.filename,
        doc_type=doc.doc_type,
        doc_type_label=DOC_TYPE_LABELS.get(doc.doc_type, "Unclassified"),
        language=doc.language,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        page_count=doc.page_count,
        ocr_confidence=doc.ocr_confidence,
        classification_confidence=doc.classification_confidence,
        status=doc.status,
        preview_url=f"{settings.api_prefix}/documents/{doc.id}/file",
        created_at=doc.created_at,
    )


def field_out(field: models.ExtractedField) -> ExtractedFieldOut:
    return ExtractedFieldOut.model_validate(field)


def finding_out(finding: models.Finding) -> FindingOut:
    return FindingOut.model_validate(finding)


def timeline_event_out(event: models.Event) -> TimelineEventOut:
    return TimelineEventOut.model_validate(event)


def review_task_out(
    task: models.ReviewTask,
    *,
    case: models.Case,
    field_count: int = 0,
    open_finding_count: int = 0,
) -> ReviewTaskOut:
    return ReviewTaskOut(
        id=task.id,
        case_id=task.case_id,
        case_reference=case.reference,
        customer_name=case.customer_name,
        reason=task.reason,
        reason_code=task.reason_code,
        reason_label=task.reason_label,
        status=task.status,
        assigned_role=task.assigned_role,
        assigned_to=user_ref(task.assigned_to),
        sla_due_at=task.sla_due_at,
        sla_state=sla_state(task.sla_due_at),
        escalated_at=task.escalated_at,
        decision=task.decision,
        decision_reason_code=task.decision_reason_code,
        decision_note=task.decision_note,
        created_at=task.created_at,
        completed_at=task.completed_at,
        field_count=field_count,
        open_finding_count=open_finding_count,
    )


def case_summary(
    case: models.Case,
    *,
    document_count: int,
    finding_count: int,
    open_finding_count: int,
) -> CaseSummary:
    return CaseSummary(
        id=case.id,
        reference=case.reference,
        case_type=case.case_type,
        customer_name=case.customer_name,
        customer_name_ar=case.customer_name_ar,
        status=case.status,
        risk_level=case.risk_level,
        priority=case.priority,
        confidence=case.confidence,
        document_count=document_count,
        finding_count=finding_count,
        open_finding_count=open_finding_count,
        straight_through=case.straight_through,
        assigned_to=user_ref(case.assigned_to),
        sla_due_at=case.sla_due_at,
        sla_state=sla_state(case.sla_due_at, status=case.status),
        created_at=case.created_at,
        updated_at=case.updated_at,
        completed_at=case.completed_at,
        processing_ms=case.processing_ms,
        cost_usd=case.cost_usd,
    )


def case_detail(case: models.Case, events: list[models.Event]) -> CaseDetail:
    """Expects `case` loaded with documents, fields, findings and review_tasks."""
    findings = list(case.findings)
    open_findings = [f for f in findings if f.status == FindingStatus.open]
    summary = case_summary(
        case,
        document_count=len(case.documents),
        finding_count=len(findings),
        open_finding_count=len(open_findings),
    )
    return CaseDetail(
        **summary.model_dump(),
        thread_id=case.thread_id,
        notes=case.notes,
        created_by=user_ref(case.created_by),
        documents=[document_out(d) for d in case.documents],
        fields=[field_out(f) for f in case.fields],
        findings=[finding_out(f) for f in findings],
        timeline=[timeline_event_out(e) for e in events],
        review_tasks=[
            review_task_out(
                task,
                case=case,
                field_count=len(case.fields),
                open_finding_count=len(open_findings),
            )
            for task in case.review_tasks
        ],
    )
