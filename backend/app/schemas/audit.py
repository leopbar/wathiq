from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.db.enums import ActorType


class AuditEntryOut(BaseModel):
    id: UUID
    case_id: UUID | None
    case_reference: str | None
    actor: str
    actor_type: ActorType
    action: str
    label: str
    detail: dict[str, Any] | None
    prompt_version: str | None
    model_version: str | None
    ip_address: str | None
    created_at: datetime
