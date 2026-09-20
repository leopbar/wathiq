"""Settings screen: document types, users, integration honesty, and the current mode."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.config import settings as app_settings
from app.core.deps import ADMIN_ONLY, CurrentUser, DbSession, require_roles
from app.db import models
from app.schemas.auth import UserOut
from app.schemas.settings import DocumentTypeOut, Integration, ModeInfo
from app.services.catalog import integrations

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/mode", response_model=ModeInfo)
async def mode() -> ModeInfo:
    """Public: the login screen needs to know whether to offer demo sign-in."""
    return ModeInfo(
        mode=app_settings.mode,
        version=app_settings.app_version,
        build_sha=app_settings.build_sha,
        features={
            "demo_login": app_settings.is_demo,
            "azure_services": not app_settings.is_demo,
            "arabic_ui": True,
            "conductor_process_layer": True,
        },
    )


@router.get("/document-types", response_model=list[DocumentTypeOut])
async def document_types(db: DbSession, _: CurrentUser) -> list[DocumentTypeOut]:
    rows = (
        await db.execute(select(models.DocumentType).order_by(models.DocumentType.name_en))
    ).scalars().all()
    return [
        DocumentTypeOut(
            id=row.id,
            key=row.key,
            name_en=row.name_en,
            name_ar=row.name_ar,
            description=row.description,
            version=row.version,
            prompt_key=row.prompt_key,
            rules_version=row.rules_version,
            fields=row.field_schema,
            rules_count=len(row.rules),
            is_active=row.is_active,
        )
        for row in rows
    ]


@router.get("/integrations", response_model=list[Integration])
async def integration_status(_: CurrentUser) -> list[Integration]:
    return integrations()


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: DbSession, _: Annotated[models.User, Depends(require_roles(*ADMIN_ONLY))]
) -> list[UserOut]:
    rows = (await db.execute(select(models.User).order_by(models.User.full_name))).scalars().all()
    return [UserOut.model_validate(row) for row in rows]
