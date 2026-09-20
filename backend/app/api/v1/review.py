"""Review queue and reviewer decisions.

In M2 a decision resumes the LangGraph checkpoint. Here it records the outcome and moves the
case forward, keeping the same request/response shape so the UI does not change later.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import REVIEW_ROLES, CurrentUser, DbSession, client_ip, require_roles
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db import models
from app.db.enums import (
    CaseStatus,
    FieldStatus,
    FindingStatus,
    ReviewDecision,
    ReviewStatus,
    Role,
)
from app.schemas.case import ReviewTaskOut
from app.schemas.common import Page
from app.schemas.review import ReasonCode, ReviewDecisionRequest, ReviewTaskDetail
from app.services import mappers, pipeline
from app.services.catalog import DECISION_REASON_CODES
from app.services.events import record_user_event

router = APIRouter(prefix="/review", tags=["review"])

ReviewUser = Annotated[models.User, Depends(require_roles(*REVIEW_ROLES))]


async def _task_with_case(db: DbSession, task_id: UUID) -> models.ReviewTask:
    task = (
        await db.execute(
            select(models.ReviewTask)
            .where(models.ReviewTask.id == task_id)
            .options(
                selectinload(models.ReviewTask.assigned_to),
                selectinload(models.ReviewTask.case).selectinload(models.Case.documents),
                selectinload(models.ReviewTask.case).selectinload(models.Case.fields),
                selectinload(models.ReviewTask.case).selectinload(models.Case.findings),
                selectinload(models.ReviewTask.case).selectinload(models.Case.review_tasks),
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError("Review task")
    return task


@router.get("/reason-codes", response_model=list[ReasonCode])
async def reason_codes(_: CurrentUser) -> list[ReasonCode]:
    return DECISION_REASON_CODES


@router.get("/queue", response_model=Page[ReviewTaskOut])
async def review_queue(
    db: DbSession,
    user: ReviewUser,
    mine: bool = False,
    status_filter: Annotated[ReviewStatus | None, Query(alias="status")] = None,
    sla: Annotated[Literal["on_track", "at_risk", "breached"] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ReviewTaskOut]:
    field_count = (
        select(func.count(models.ExtractedField.id))
        .where(models.ExtractedField.case_id == models.Case.id)
        .correlate(models.Case)
        .scalar_subquery()
    )
    open_findings = (
        select(func.count(models.Finding.id))
        .where(
            models.Finding.case_id == models.Case.id,
            models.Finding.status == FindingStatus.open,
        )
        .correlate(models.Case)
        .scalar_subquery()
    )

    stmt = (
        select(models.ReviewTask, models.Case, field_count.label("fc"), open_findings.label("of"))
        .join(models.Case, models.ReviewTask.case_id == models.Case.id)
        .options(selectinload(models.ReviewTask.assigned_to))
    )

    if mine:
        stmt = stmt.where(models.ReviewTask.assigned_to_id == user.id)
    elif user.role == Role.reviewer:
        # A reviewer sees unassigned work plus their own.
        stmt = stmt.where(
            (models.ReviewTask.assigned_to_id.is_(None))
            | (models.ReviewTask.assigned_to_id == user.id)
        )
    if status_filter:
        stmt = stmt.where(models.ReviewTask.status == status_filter)
    else:
        stmt = stmt.where(models.ReviewTask.status != ReviewStatus.completed)
    if sla == "breached":
        stmt = stmt.where(models.ReviewTask.sla_due_at < datetime.now(UTC))
    elif sla in ("on_track", "at_risk"):
        stmt = stmt.where(models.ReviewTask.sla_due_at >= datetime.now(UTC))

    stmt = stmt.order_by(
        models.ReviewTask.sla_due_at.asc().nullslast(), models.ReviewTask.created_at.asc()
    )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.offset((page - 1) * size).limit(size))).all()

    items = [
        mappers.review_task_out(
            row.ReviewTask, case=row.Case, field_count=row.fc, open_finding_count=row.of
        )
        for row in rows
    ]
    if sla in ("on_track", "at_risk"):
        items = [i for i in items if i.sla_state == sla]
    return Page.build(items, total=total, page=page, size=size)


@router.get("/tasks/{task_id}", response_model=ReviewTaskDetail)
async def get_review_task(task_id: UUID, db: DbSession, _: ReviewUser) -> ReviewTaskDetail:
    task = await _task_with_case(db, task_id)
    events = (
        await db.execute(
            select(models.Event)
            .where(models.Event.case_id == task.case_id)
            .order_by(models.Event.seq.asc())
        )
    ).scalars().all()
    case = task.case
    open_findings = sum(1 for f in case.findings if f.status == FindingStatus.open)
    return ReviewTaskDetail(
        task=mappers.review_task_out(
            task, case=case, field_count=len(case.fields), open_finding_count=open_findings
        ),
        case=mappers.case_detail(case, list(events)),
    )


@router.post("/tasks/{task_id}/claim", response_model=ReviewTaskOut)
async def claim_task(
    task_id: UUID, request: Request, db: DbSession, user: ReviewUser
) -> ReviewTaskOut:
    task = await _task_with_case(db, task_id)
    if task.status == ReviewStatus.completed:
        raise ConflictError("This review is already finished", "TASK_COMPLETED")
    if task.assigned_to_id not in (None, user.id):
        raise ConflictError("Someone else is already working on this review", "TASK_TAKEN")

    task.assigned_to_id = user.id
    task.status = ReviewStatus.in_progress
    task.case.status = CaseStatus.in_review
    task.case.assigned_to_id = user.id

    await record_user_event(
        db,
        user=user,
        action="review.claimed",
        label=f"{user.full_name} claimed the review for {task.case.reference}",
        case_id=task.case_id,
        ip_address=client_ip(request),
    )
    await db.commit()
    task = await _task_with_case(db, task_id)
    return mappers.review_task_out(task, case=task.case, field_count=len(task.case.fields))


@router.post("/tasks/{task_id}/decision", response_model=ReviewTaskOut)
async def submit_decision(
    task_id: UUID,
    payload: ReviewDecisionRequest,
    request: Request,
    db: DbSession,
    user: ReviewUser,
) -> ReviewTaskOut:
    task = await _task_with_case(db, task_id)
    if task.status == ReviewStatus.completed:
        raise ConflictError("This review is already finished", "TASK_COMPLETED")

    case = task.case
    fields_by_id = {field.id: field for field in case.fields}

    if payload.decision == ReviewDecision.correct and not payload.field_corrections:
        raise ValidationError("A correction needs at least one changed field", "NO_CORRECTIONS")

    corrections: list[dict[str, str]] = []
    for correction in payload.field_corrections:
        field = fields_by_id.get(correction.field_id)
        if field is None:
            raise ValidationError("A corrected field does not belong to this case", "BAD_FIELD")
        corrections.append(
            {"field": field.name, "from": field.value or "", "to": correction.value}
        )
        field.corrected_value = correction.value
        field.status = FieldStatus.corrected

    task.decision = payload.decision
    task.decision_reason_code = payload.reason_code
    task.decision_note = payload.note
    task.status = ReviewStatus.completed
    task.completed_at = datetime.now(UTC)
    task.assigned_to_id = task.assigned_to_id or user.id

    if payload.decision == ReviewDecision.reject:
        case.status = CaseStatus.rejected
        case.completed_at = datetime.now(UTC)
    elif payload.decision == ReviewDecision.escalate:
        case.status = CaseStatus.needs_review
        task.status = ReviewStatus.pending
        task.completed_at = None
        task.assigned_role = Role.supervisor
        task.assigned_to_id = None
    else:
        case.status = CaseStatus.approved
        for finding in case.findings:
            if finding.status == FindingStatus.open:
                finding.status = FindingStatus.resolved

    await record_user_event(
        db,
        user=user,
        action=f"review.{payload.decision.value}",
        label=(
            f"{user.full_name} {payload.decision.value}d the review for {case.reference}"
            if payload.decision != ReviewDecision.escalate
            else f"{user.full_name} escalated {case.reference} to a supervisor"
        ),
        case_id=case.id,
        detail={
            "reason_code": payload.reason_code,
            "note": payload.note,
            "corrections": corrections,
        },
        ip_address=client_ip(request),
    )
    await db.commit()

    # Escalation keeps the graph parked at the review gate — a supervisor still has to answer.
    # Every other decision resumes the graph from its checkpoint, applying the corrections.
    if payload.decision != ReviewDecision.escalate:
        pipeline.resume(
            case.id,
            payload.decision.value,
            {c["field"]: c["to"] for c in corrections},
        )

    task = await _task_with_case(db, task_id)
    open_findings = sum(1 for f in task.case.findings if f.status == FindingStatus.open)
    return mappers.review_task_out(
        task,
        case=task.case,
        field_count=len(task.case.fields),
        open_finding_count=open_findings,
    )
