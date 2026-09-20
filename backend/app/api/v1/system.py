"""The About screen: diagrams, stack rationale and honest service status."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.agent import graph
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
    """The agent graph that actually runs.

    Drawn from the graph module that the pipeline compiles, so the picture cannot describe a
    graph we are not running. M3 adds the workers, the critic and the investigator to it.
    """
    return GraphDiagram(mermaid=graph.mermaid(), source="live")
