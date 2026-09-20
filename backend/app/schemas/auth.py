from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.db.enums import Role
from app.schemas.common import Schema


class UserOut(Schema):
    id: UUID
    email: str
    full_name: str
    full_name_ar: str
    role: Role
    is_active: bool


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class DemoLoginRequest(BaseModel):
    role: Role


class DemoUser(BaseModel):
    role: Role
    email: str
    full_name: str
    title: str
    description: str
