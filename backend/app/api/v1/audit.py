"""The audit trail: a read of the append-only event log, with CSV export."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from sqlalchemy import Select, func, or_, select

from app.core.deps import BrowserUser, CurrentUser, DbSession
from app.db import models
from app.db.enums import ActorType
from app.schemas.audit import AuditEntryOut
from app.schemas.common import Page

router = APIRouter(prefix="/audit", tags=["audit"])

EXPORT_LIMIT = 5000


def _filtered(
    q: str | None,
    actor: str | None,
    action: str | None,
    case_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select:
    stmt = (
        select(models.Event, models.Case.reference)
        .outerjoin(models.Case, models.Event.case_id == models.Case.id)
        .order_by(models.Event.seq.desc())
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                models.Event.label.ilike(like),
                models.Event.action.ilike(like),
                models.Event.actor.ilike(like),
                models.Case.reference.ilike(like),
            )
        )
    if actor:
        stmt = stmt.where(models.Event.actor.ilike(f"%{actor}%"))
    if action:
        stmt = stmt.where(models.Event.action == action)
    if case_id:
        stmt = stmt.where(models.Event.case_id == case_id)
    if date_from:
        stmt = stmt.where(models.Event.created_at >= date_from)
    if date_to:
        stmt = stmt.where(models.Event.created_at <= date_to)
    return stmt


def _to_out(event: models.Event, reference: str | None) -> AuditEntryOut:
    return AuditEntryOut(
        id=event.id,
        case_id=event.case_id,
        case_reference=reference,
        actor=event.actor,
        actor_type=event.actor_type,
        action=event.action,
        label=event.label,
        detail=event.detail,
        prompt_version=event.prompt_version,
        model_version=event.model_version,
        ip_address=event.ip_address,
        created_at=event.created_at,
    )


@router.get("", response_model=Page[AuditEntryOut])
async def list_audit(
    db: DbSession,
    _: CurrentUser,
    q: Annotated[str | None, Query(max_length=120)] = None,
    actor: Annotated[str | None, Query(max_length=160)] = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    case_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> Page[AuditEntryOut]:
    stmt = _filtered(q, actor, action, case_id, date_from, date_to)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.offset((page - 1) * size).limit(size))).all()
    items = [_to_out(row[0], row[1]) for row in rows]
    return Page.build(items, total=total, page=page, size=size)


@router.get("/actions", response_model=list[str])
async def list_actions(db: DbSession, _: CurrentUser) -> list[str]:
    rows = (
        await db.execute(select(models.Event.action).distinct().order_by(models.Event.action))
    ).scalars().all()
    return list(rows)


@router.get("/export")
async def export_audit(
    db: DbSession,
    _: BrowserUser,
    q: Annotated[str | None, Query(max_length=120)] = None,
    actor: Annotated[str | None, Query(max_length=160)] = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    case_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Response:
    stmt = _filtered(q, actor, action, case_id, date_from, date_to).limit(EXPORT_LIMIT)
    rows = (await db.execute(stmt)).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "timestamp",
            "case_reference",
            "actor",
            "actor_type",
            "action",
            "description",
            "prompt_version",
            "model_version",
            "ip_address",
        ]
    )
    for event, reference in rows:
        writer.writerow(
            [
                event.created_at.isoformat(),
                reference or "",
                event.actor,
                ActorType(event.actor_type).value,
                event.action,
                event.label,
                event.prompt_version or "",
                event.model_version or "",
                event.ip_address or "",
            ]
        )

    filename = f"wathiq-audit-{datetime.now().date().isoformat()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
