"""v1 API router."""

from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    cases,
    dashboard,
    documents,
    gallery,
    process_api,
    prompts,
    quality,
    review,
    settings_api,
    system,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(documents.router)
api_router.include_router(review.router)
api_router.include_router(dashboard.router)
api_router.include_router(quality.router)
api_router.include_router(prompts.router)
api_router.include_router(settings_api.router)
api_router.include_router(process_api.router)
api_router.include_router(audit.router)
api_router.include_router(system.router)
api_router.include_router(gallery.router)

__all__ = ["api_router"]
