"""Case endpoints: list, detail, create, upload, start, live progress."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.agent import runner
from app.core.config import settings
from app.core.deps import (
    WRITE_ROLES,
    BrowserUser,
    CurrentUser,
    DbSession,
    client_ip,
    require_roles,
)
from app.core.errors import NotFoundError, ServiceUnavailableError, ValidationError
from app.db import models
from app.db.enums import (
    ActorType,
    CaseStatus,
    CaseType,
    DocumentStatus,
    FindingStatus,
    Language,
)
from app.process import engine_for_case, engine_for_new_case
from app.process.conductor_client import ConductorError
from app.schemas.case import (
    AssuranceOut,
    CaseCreate,
    CaseDetail,
    CaseStartResponse,
    CaseSummary,
    DocumentOut,
)
from app.schemas.common import Page
from app.schemas.process import PostingOut, ProcessStatusOut
from app.services import mappers, posting, progress
from app.services.events import record_event, record_user_event
from app.services.sla import default_due_at
from app.services.storage import get_storage

router = APIRouter(prefix="/cases", tags=["cases"])

# The SSE stream polls the event log. 1s is fast enough to look live and cheap enough to hold
# open; 300 polls caps one connection at five minutes so a forgotten tab cannot leak a session.
SSE_POLL_SECONDS = 1.0
SSE_MAX_POLLS = 300

ALLOWED_UPLOAD_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tif",
}

SortKey = Literal[
    "-created_at", "created_at", "-updated_at", "updated_at", "-sla_due_at", "sla_due_at"
]


def _count_subquery(model: type, extra=None):
    stmt = (
        select(func.count(model.id))
        .where(model.case_id == models.Case.id)
        .correlate(models.Case)
    )
    if extra is not None:
        stmt = stmt.where(extra)
    return stmt.scalar_subquery()


def _list_statement() -> Select:
    return select(
        models.Case,
        _count_subquery(models.Document).label("document_count"),
        _count_subquery(models.Finding).label("finding_count"),
        _count_subquery(
            models.Finding, models.Finding.status == FindingStatus.open
        ).label("open_finding_count"),
    )


async def _load_case(db: DbSession, case_id: UUID) -> models.Case:
    result = await db.execute(
        select(models.Case)
        .where(models.Case.id == case_id)
        .options(
            selectinload(models.Case.documents),
            selectinload(models.Case.fields),
            selectinload(models.Case.findings),
            selectinload(models.Case.review_tasks).selectinload(models.ReviewTask.assigned_to),
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise NotFoundError("Case")
    return case


async def _case_detail(db: DbSession, case: models.Case) -> CaseDetail:
    events = (
        await db.execute(
            select(models.Event)
            .where(models.Event.case_id == case.id)
            .order_by(models.Event.seq.asc())
        )
    ).scalars().all()
    return mappers.case_detail(case, list(events))


async def _next_reference(db: DbSession) -> str:
    year = datetime.now(UTC).year
    prefix = f"WTQ-{year}-"
    last = (
        await db.execute(
            select(models.Case.reference)
            .where(models.Case.reference.startswith(prefix))
            .order_by(models.Case.reference.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    nxt = int(last.removeprefix(prefix)) + 1 if last else 1
    return f"{prefix}{nxt:04d}"


@router.get("", response_model=Page[CaseSummary])
async def list_cases(
    db: DbSession,
    user: CurrentUser,
    status_filter: Annotated[list[CaseStatus] | None, Query(alias="status")] = None,
    case_type: CaseType | None = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    assigned_to_me: bool = False,
    sla_state: Annotated[Literal["on_track", "at_risk", "breached", "none"] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 20,
    sort: SortKey = "-created_at",
) -> Page[CaseSummary]:
    stmt = _list_statement()

    if status_filter:
        stmt = stmt.where(models.Case.status.in_(status_filter))
    if case_type:
        stmt = stmt.where(models.Case.case_type == case_type)
    if assigned_to_me:
        stmt = stmt.where(models.Case.assigned_to_id == user.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                models.Case.reference.ilike(like),
                models.Case.customer_name.ilike(like),
                models.Case.customer_name_ar.ilike(like),
            )
        )
    if sla_state:
        now = datetime.now(UTC)
        if sla_state == "breached":
            stmt = stmt.where(models.Case.sla_due_at < now)
        elif sla_state == "none":
            stmt = stmt.where(models.Case.sla_due_at.is_(None))
        else:
            stmt = stmt.where(models.Case.sla_due_at >= now)

    column = getattr(models.Case, sort.lstrip("-"))
    stmt = stmt.order_by(column.desc() if sort.startswith("-") else column.asc())

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await db.execute(stmt.offset((page - 1) * size).limit(size))).all()

    items = [
        mappers.case_summary(
            row.Case,
            document_count=row.document_count,
            finding_count=row.finding_count,
            open_finding_count=row.open_finding_count,
        )
        for row in rows
    ]
    return Page.build(items, total=total, page=page, size=size)


@router.get("/{case_id}", response_model=CaseDetail)
async def get_case(case_id: UUID, db: DbSession, _: CurrentUser) -> CaseDetail:
    case = await _load_case(db, case_id)
    return await _case_detail(db, case)


@router.post("", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    request: Request,
    db: DbSession,
    user: Annotated[models.User, Depends(require_roles(*WRITE_ROLES))],
) -> CaseDetail:
    case = models.Case(
        reference=await _next_reference(db),
        case_type=payload.case_type,
        customer_name=payload.customer_name.strip(),
        customer_name_ar=payload.customer_name_ar.strip(),
        status=CaseStatus.intake,
        priority=payload.priority,
        notes=payload.notes,
        thread_id=uuid4().hex,
        created_by_id=user.id,
        sla_due_at=default_due_at(),
    )
    db.add(case)
    await db.flush()

    await record_user_event(
        db,
        user=user,
        action="case.created",
        label=f"Case {case.reference} created for {case.customer_name}",
        case_id=case.id,
        detail={"case_type": case.case_type.value, "priority": case.priority.value},
        ip_address=client_ip(request),
    )
    await db.commit()

    case = await _load_case(db, case.id)
    return await _case_detail(db, case)


@router.post(
    "/{case_id}/documents",
    response_model=list[DocumentOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    case_id: UUID,
    request: Request,
    db: DbSession,
    user: Annotated[models.User, Depends(require_roles(*WRITE_ROLES))],
    files: Annotated[list[UploadFile], File(description="PDF, PNG, JPEG or TIFF")],
) -> list[DocumentOut]:
    case = await _load_case(db, case_id)
    if not files:
        raise ValidationError("Attach at least one document", "NO_FILES")

    storage = get_storage()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    created: list[models.Document] = []

    for upload in files:
        content_type = (upload.content_type or "").split(";")[0].strip().lower()
        if content_type not in ALLOWED_UPLOAD_TYPES:
            raise ValidationError(
                f"{upload.filename}: only PDF, PNG, JPEG or TIFF files are accepted",
                "UNSUPPORTED_FILE_TYPE",
            )
        data = await upload.read()
        if len(data) == 0:
            raise ValidationError(f"{upload.filename}: the file is empty", "EMPTY_FILE")
        if len(data) > max_bytes:
            raise ValidationError(
                f"{upload.filename}: larger than the {settings.max_upload_mb} MB limit",
                "FILE_TOO_LARGE",
            )

        storage_path = storage.save(case.id, upload.filename or "document", data)
        document = models.Document(
            case_id=case.id,
            filename=upload.filename or "document",
            mime_type=content_type,
            size_bytes=len(data),
            storage_path=storage_path,
            status=DocumentStatus.uploaded,
            language=Language.en,
        )
        db.add(document)
        created.append(document)

    await db.flush()
    await record_user_event(
        db,
        user=user,
        action="documents.uploaded",
        label=f"{len(created)} document(s) uploaded to {case.reference}",
        case_id=case.id,
        detail={"filenames": [d.filename for d in created]},
        ip_address=client_ip(request),
    )
    await db.commit()
    return [mappers.document_out(d) for d in created]


@router.post("/{case_id}/start", response_model=CaseStartResponse)
async def start_case(
    case_id: UUID,
    request: Request,
    db: DbSession,
    user: Annotated[models.User, Depends(require_roles(*WRITE_ROLES))],
) -> CaseStartResponse:
    """Hand the case to the LangGraph pipeline.

    Returns as soon as the run is queued; the browser follows progress on the SSE stream.
    """
    case = await _load_case(db, case_id)
    if not case.documents:
        raise ValidationError("Upload at least one document before starting", "NO_DOCUMENTS")

    case.status = CaseStatus.processing
    case.sla_due_at = case.sla_due_at or default_due_at()

    await record_user_event(
        db,
        user=user,
        action="case.started",
        label=f"{case.reference} handed to the pipeline",
        case_id=case.id,
        detail={"thread_id": case.thread_id, "documents": len(case.documents)},
        ip_address=client_ip(request),
    )
    await record_event(
        db,
        case_id=case.id,
        action="pipeline.queued",
        label="Queued for the agent pipeline",
        actor="system",
        actor_type=ActorType.system,
        detail={"thread_id": case.thread_id, "documents": len(case.documents)},
    )
    await db.commit()

    # Commit first, then hand the case to the process layer: the engine opens its own sessions
    # and must not race the transaction that set the case to `processing`.
    engine = await engine_for_new_case()
    try:
        workflow_id = await engine.start_case(case.id)
    except ConductorError as exc:
        # Only reachable with WATHIQ_PROCESS_ENGINE=conductor, which is a deliberate choice to
        # fail rather than quietly run the process somewhere else.
        raise ServiceUnavailableError(
            "The process orchestrator is not available, so the case was not started. "
            f"({exc})",
            "CONDUCTOR_UNAVAILABLE",
        ) from exc

    return CaseStartResponse(thread_id=workflow_id, status=case.status)


@router.get("/{case_id}/assurance", response_model=AssuranceOut)
async def case_assurance(case_id: UUID, db: DbSession, _: CurrentUser) -> AssuranceOut:
    """The evidence behind this case: guardrails, workers, critic, investigation, tools.

    Read from the LangGraph checkpoint rather than from a second set of tables. The checkpoint
    is what the graph resumes from, so the panel shows exactly what the run knew.
    """
    case = await _load_case(db, case_id)
    state = await runner.get_state(case.thread_id)
    if state is None:
        return AssuranceOut(
            available=False,
            thread_id=case.thread_id,
            note=(
                "This case has no agent checkpoint. Seeded demo cases are written straight to "
                "the database and never run through the graph — upload a document on the New "
                "case screen to see a real run."
            ),
        )

    return AssuranceOut(
        available=True,
        thread_id=case.thread_id,
        guardrails=list(state.get("guardrails") or []),
        worker_results=list(state.get("worker_results") or []),
        critic_notes=list(state.get("critic_notes") or []),
        investigation=list(state.get("investigation") or []),
        tool_calls=list(state.get("tool_calls") or []),
        plan=[
            # The full field schema is in the plan for the workers' benefit; the UI does not
            # need it and it would be the largest thing on the page.
            {key: value for key, value in item.items() if key != "field_schema"}
            for item in (state.get("plan") or [])
        ],
        rule_packs=dict(state.get("rule_packs") or {}),
        prompt_versions=dict(state.get("prompt_versions") or {}),
        calibration=dict(state.get("calibration") or {}),
        review_reasons=list(state.get("review_reasons") or []),
    )


@router.get("/{case_id}/process", response_model=ProcessStatusOut)
async def case_process(case_id: UUID, db: DbSession, _: CurrentUser) -> ProcessStatusOut:
    """Where this case is in the business process, and what was posted.

    The steps come from the case's own append-only event log, so this view and the audit trail
    cannot disagree. When Conductor ran the case and is reachable, its own view of the workflow
    instance is included alongside — two independent records of the same run.
    """
    case = await _load_case(db, case_id)
    engine = await engine_for_case(db, case)
    status_out = await engine.status(case)
    payload = status_out.as_dict()

    record = await posting.for_case(db, case_id)
    if record is not None:
        payload["posting"] = PostingOut(
            status=record.status.value,
            reference=record.reference,
            customer_id=record.customer_id,
            approval_kind=record.approval_kind,
            approved_by=record.approved_by,
            duplicate=record.duplicate,
            idempotency_key=record.idempotency_key,
            note=record.note,
            posted_at=record.posted_at.isoformat() if record.posted_at else None,
        )
    return ProcessStatusOut(**payload)


@router.get("/{case_id}/events")
async def case_events(
    case_id: UUID, request: Request, db: DbSession, _: BrowserUser
) -> EventSourceResponse:
    """Server-Sent Events stream of pipeline progress.

    `EventSource` cannot set an Authorization header, so this endpoint also accepts `?token=`
    (see `get_current_user_browser`). Each new row in the append-only event log becomes a
    stepper frame, translated by `services.progress` so the UI's steps and the audit trail's
    vocabulary stay in step.

    The stream closes when the case stops moving — finished, failed, or parked at the review
    gate waiting for a person. A parked case can wait hours, so holding the connection open
    for it would be a leak, not a feature.
    """
    case = await _load_case(db, case_id)
    known_seq = 0
    # Anything other than these means the case is no longer advancing on its own. `approved`
    # and `posting` are in the list because the process layer still has work to do after the
    # graph finishes — closing the stream at `pipeline.completed` would cut the browser off
    # just before the posting and audit steps it is waiting to see.
    moving = {
        CaseStatus.intake,
        CaseStatus.processing,
        CaseStatus.approved,
        CaseStatus.posting,
    }

    async def stream() -> AsyncIterator[dict[str, str]]:
        nonlocal known_seq
        yield {
            "event": "hello",
            "data": json.dumps({"case_id": str(case.id), "thread_id": case.thread_id}),
        }
        for _ in range(SSE_MAX_POLLS):
            if await request.is_disconnected():
                break
            rows = (
                (
                    await db.execute(
                        select(models.Event)
                        .where(models.Event.case_id == case.id, models.Event.seq > known_seq)
                        .order_by(models.Event.seq.asc())
                    )
                )
                .scalars()
                .all()
            )
            for event in rows:
                known_seq = event.seq
                frame = progress.frame_for(event.action)
                if frame is None:
                    continue  # a timeline entry that is not a pipeline step
                yield {
                    "event": "progress",
                    "data": json.dumps(
                        {
                            "node": frame.node,
                            "status": frame.status,
                            "percent": frame.percent,
                            "message": event.label,
                            "at": event.created_at.isoformat(),
                        }
                    ),
                }

            # Re-read the status rather than trusting the object loaded before the loop: the
            # pipeline runs in a different session and this one would never see its writes.
            status = (
                await db.execute(select(models.Case.status).where(models.Case.id == case.id))
            ).scalar_one()
            await db.commit()  # release the snapshot so new rows become visible
            if status not in moving:
                break
            await asyncio.sleep(SSE_POLL_SECONDS)

        yield {"event": "done", "data": json.dumps({"case_id": str(case.id)})}

    return EventSourceResponse(stream(), ping=15000)
