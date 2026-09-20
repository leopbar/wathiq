"""Writing to the append-only event log.

Every meaningful action goes through `record_event`. The case timeline and the audit trail are
both reads of this table, so they can never drift apart.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ActorType
from app.db.models import Event, User


async def record_event(
    db: AsyncSession,
    *,
    action: str,
    label: str,
    actor: str,
    actor_type: ActorType,
    case_id: UUID | None = None,
    detail: dict[str, Any] | None = None,
    prompt_version: str | None = None,
    model_version: str | None = None,
    duration_ms: int | None = None,
    ip_address: str | None = None,
) -> Event:
    event = Event(
        case_id=case_id,
        actor=actor,
        actor_type=actor_type,
        action=action,
        label=label,
        detail=detail,
        prompt_version=prompt_version,
        model_version=model_version,
        duration_ms=duration_ms,
        ip_address=ip_address,
    )
    db.add(event)
    await db.flush()
    return event


async def record_user_event(
    db: AsyncSession,
    *,
    user: User,
    action: str,
    label: str,
    case_id: UUID | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> Event:
    return await record_event(
        db,
        action=action,
        label=label,
        actor=user.full_name,
        actor_type=ActorType.user,
        case_id=case_id,
        detail={"user_id": str(user.id), "role": user.role.value, **(detail or {})},
        ip_address=ip_address,
    )
