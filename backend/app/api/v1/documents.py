"""Serving the stored document bytes back to the viewer."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response
from fastapi.responses import RedirectResponse
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

    # When the backend can hand the browser a short-lived URL of its own (ADLS Gen2 SAS, M6),
    # redirect to it: the file then travels from storage to the browser directly instead of
    # through this process. Authorisation has already happened — `BrowserUser` above — and the
    # SAS is read-only and expires in minutes. A backend that cannot sign a URL returns None
    # and the bytes are streamed as they have been since M1.
    signed = storage.signed_url(
        document.storage_path,
        content_type=document.mime_type or "application/octet-stream",
        filename=document.filename,
    )
    if signed is not None:
        return RedirectResponse(signed, status_code=307)

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
