"""The About screen: diagrams, stack rationale and honest service status."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.deps import DbSession
from app.db.enums import IntegrationStatus
from app.schemas.system import GraphDiagram, ServiceStatus, SystemInfo
from app.services.catalog import diagrams, integrations, stack

router = APIRouter(prefix="/system", tags=["system"])

STARTED_AT = datetime.now(UTC)

_STATUS_MAP = {
    IntegrationStatus.connected: "healthy",
    IntegrationStatus.simulated: "healthy",
    IntegrationStatus.demo: "healthy",
    IntegrationStatus.disabled: "disabled",
}


@router.get("/info", response_model=SystemInfo)
async def system_info(db: DbSession) -> SystemInfo:
    try:
        await db.execute(text("SELECT 1"))
        db_status: str = "healthy"
        db_detail = "PostgreSQL responding"
    except Exception as exc:
        db_status = "down"
        db_detail = f"Database not reachable: {type(exc).__name__}"

    services = [ServiceStatus(name="Database", status=db_status, detail=db_detail)]
    services += [
        ServiceStatus(
            name=item.name,
            status=_STATUS_MAP[item.status],
            detail=(
                f"{item.status.value.upper()} — {item.detail}"
                if item.status == IntegrationStatus.simulated
                else item.detail
            ),
        )
        for item in integrations()
    ]

    return SystemInfo(
        mode=settings.mode,
        version=settings.app_version,
        build_sha=settings.build_sha,
        started_at=STARTED_AT,
        stack=stack(),
        services=services,
        diagrams=diagrams(),
    )


@router.get("/graph", response_model=GraphDiagram)
async def graph_diagram() -> GraphDiagram:
    """The agent graph.

    M2 replaces this with LangGraph's own `draw_mermaid()` output so the picture can never
    drift from the code. Until then it is the planned design, labelled as such.
    """
    planned = next(d for d in diagrams() if d.key == "graph")
    return GraphDiagram(mermaid=planned.mermaid, source="planned")
