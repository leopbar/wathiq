"""Serving the stored document bytes back to the viewer."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.core.deps import BrowserUser, DbSession
from app.core.errors import NotFoundError
from app.db import models
from app.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/file")
async def get_document_file(document_id: UUID, db: DbSession, _: BrowserUser) -> Response:
    document = (
        await db.execute(select(models.Document).where(models.Document.id == document_id))
    ).scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document")

    storage = get_storage()
    if not document.storage_path or not storage.exists(document.storage_path):
        raise NotFoundError("Stored file")

    data = storage.read(document.storage_path)
    return Response(
        content=data,
        media_type=document.mime_type or "application/octet-stream",
        headers={
            # inline so the viewer can embed it; filename kept for downloads
            "Content-Disposition": f'inline; filename="{document.filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )
