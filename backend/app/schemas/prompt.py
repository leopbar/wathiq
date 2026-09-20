from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.enums import PromptStatus
from app.schemas.common import Schema


class PromptOut(BaseModel):
    id: UUID
    key: str
    name: str
    description: str
    document_type: str
    latest_version: str
    status: PromptStatus
    versions_count: int
    updated_at: datetime


class PromptVersionOut(Schema):
    id: UUID
    version: str
    status: PromptStatus
    body: str
    notes: str
    eval_score: float | None
    created_by: str
    created_at: datetime
    approved_by: str | None
    approved_at: datetime | None


class PromptDiff(BaseModel):
    key: str
    from_version: str
    to_version: str
    unified_diff: str
