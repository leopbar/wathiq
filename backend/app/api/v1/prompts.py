"""Prompt Studio: versions, diffs, approval.

Semantic versioning: MAJOR = output schema change, MINOR = new fields, PATCH = wording.
The engine only ever loads a pinned, approved version.
"""

from __future__ import annotations

import difflib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import ADMIN_ONLY, CurrentUser, DbSession, client_ip, require_roles
from app.core.errors import ConflictError, NotFoundError
from app.db import models
from app.db.enums import PromptStatus
from app.schemas.prompt import PromptDiff, PromptOut, PromptVersionOut
from app.services.events import record_user_event

router = APIRouter(prefix="/prompts", tags=["prompts"])

AdminUser = Annotated[models.User, Depends(require_roles(*ADMIN_ONLY))]


def _sort_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return (0,)


async def _load_prompt(db: DbSession, key: str) -> models.Prompt:
    prompt = (
        await db.execute(
            select(models.Prompt)
            .where(models.Prompt.key == key)
            .options(selectinload(models.Prompt.versions))
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise NotFoundError("Prompt")
    return prompt


def _latest(prompt: models.Prompt) -> models.PromptVersion | None:
    if not prompt.versions:
        return None
    return max(prompt.versions, key=lambda v: _sort_key(v.version))


@router.get("", response_model=list[PromptOut])
async def list_prompts(db: DbSession, _: CurrentUser) -> list[PromptOut]:
    prompts = (
        await db.execute(
            select(models.Prompt)
            .options(selectinload(models.Prompt.versions))
            .order_by(models.Prompt.name)
        )
    ).scalars().all()

    out: list[PromptOut] = []
    for prompt in prompts:
        latest = _latest(prompt)
        out.append(
            PromptOut(
                id=prompt.id,
                key=prompt.key,
                name=prompt.name,
                description=prompt.description,
                document_type=prompt.document_type,
                latest_version=latest.version if latest else "—",
                status=latest.status if latest else PromptStatus.draft,
                versions_count=len(prompt.versions),
                updated_at=prompt.updated_at,
            )
        )
    return out


@router.get("/{key}/versions", response_model=list[PromptVersionOut])
async def list_versions(key: str, db: DbSession, _: CurrentUser) -> list[PromptVersionOut]:
    prompt = await _load_prompt(db, key)
    versions = sorted(prompt.versions, key=lambda v: _sort_key(v.version), reverse=True)
    return [PromptVersionOut.model_validate(v) for v in versions]


@router.get("/{key}/diff", response_model=PromptDiff)
async def diff_versions(
    key: str,
    db: DbSession,
    _: CurrentUser,
    from_version: Annotated[str, Query(alias="from")],
    to_version: Annotated[str, Query(alias="to")],
) -> PromptDiff:
    prompt = await _load_prompt(db, key)
    by_version = {v.version: v for v in prompt.versions}
    if from_version not in by_version or to_version not in by_version:
        raise NotFoundError("Prompt version")

    diff = difflib.unified_diff(
        by_version[from_version].body.splitlines(),
        by_version[to_version].body.splitlines(),
        fromfile=f"{key}@{from_version}",
        tofile=f"{key}@{to_version}",
        lineterm="",
        n=3,
    )
    return PromptDiff(
        key=key,
        from_version=from_version,
        to_version=to_version,
        unified_diff="\n".join(diff),
    )


@router.post("/{key}/versions/{version}/approve", response_model=PromptVersionOut)
async def approve_version(
    key: str, version: str, request: Request, db: DbSession, user: AdminUser
) -> PromptVersionOut:
    prompt = await _load_prompt(db, key)
    target = next((v for v in prompt.versions if v.version == version), None)
    if target is None:
        raise NotFoundError("Prompt version")
    if target.status == PromptStatus.retired:
        raise ConflictError("A retired version cannot be approved again", "VERSION_RETIRED")

    # Only one approved version at a time: the engine must never have to choose.
    for other in prompt.versions:
        if other.status == PromptStatus.approved and other.id != target.id:
            other.status = PromptStatus.retired

    target.status = PromptStatus.approved
    target.approved_by = user.full_name
    target.approved_at = datetime.now(UTC)

    await record_user_event(
        db,
        user=user,
        action="prompt.approved",
        label=f"{user.full_name} approved {key}@{version}",
        detail={"prompt": key, "version": version},
        ip_address=client_ip(request),
    )
    await db.commit()
    await db.refresh(target)
    return PromptVersionOut.model_validate(target)


@router.post("/{key}/versions/{version}/retire", response_model=PromptVersionOut)
async def retire_version(
    key: str, version: str, request: Request, db: DbSession, user: AdminUser
) -> PromptVersionOut:
    prompt = await _load_prompt(db, key)
    target = next((v for v in prompt.versions if v.version == version), None)
    if target is None:
        raise NotFoundError("Prompt version")

    target.status = PromptStatus.retired
    await record_user_event(
        db,
        user=user,
        action="prompt.retired",
        label=f"{user.full_name} retired {key}@{version}",
        detail={"prompt": key, "version": version},
        ip_address=client_ip(request),
    )
    await db.commit()
    await db.refresh(target)
    return PromptVersionOut.model_validate(target)
