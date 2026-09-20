from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.db.enums import DocTypeKey, IntegrationStatus


class DocumentTypeOut(BaseModel):
    id: UUID
    key: DocTypeKey
    name_en: str
    name_ar: str
    description: str
    version: str
    prompt_key: str
    rules_version: str
    fields: list[dict[str, Any]]
    rules_count: int
    is_active: bool


class Integration(BaseModel):
    key: str
    name: str
    category: str
    status: IntegrationStatus
    detail: str
    docs_url: str | None = None


class ModeInfo(BaseModel):
    mode: Literal["demo", "azure"]
    version: str
    build_sha: str
    features: dict[str, bool]
