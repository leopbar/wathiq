"""Shared response shapes."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRef(Schema):
    id: UUID
    full_name: str


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, size: int) -> Page[T]:
        pages = max(1, -(-total // size)) if size else 1
        return cls(items=items, total=total, page=page, size=size, pages=pages)


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Message(BaseModel):
    detail: str
    code: str = "OK"
