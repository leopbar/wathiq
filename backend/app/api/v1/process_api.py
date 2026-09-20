"""The process layer over HTTP: which engine is running, and the SLA check.

Read endpoints are open to any signed-in user, because "which engine ran this?" is exactly the
kind of question the UI has to be able to answer honestly.

The one action here — running the SLA check now — is restricted to a supervisor or an admin. It
is the same sweep the timer runs on its own; triggering it by hand only removes the wait, which
is what makes escalation demonstrable in a ten-minute demo rather than a four-hour one.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.deps import CurrentUser, DbSession, client_ip, require_roles
from app.db import models
from app.db.enums import Role
from app.process import definition, health
from app.schemas.process import (
    AuditIntegrityOut,
    ProcessDefinitionOut,
    ProcessHealthOut,
    SlaSweepOut,
)
from app.services import audit_trail, escalation
from app.services.events import record_user_event

router = APIRouter(prefix="/process", tags=["process"])

SupervisorUser = Annotated[models.User, Depends(require_roles(Role.supervisor, Role.admin))]


@router.get("/health", response_model=ProcessHealthOut)
async def process_health(_: CurrentUser) -> ProcessHealthOut:
    """Which engine the process layer is using, and whether Conductor is reachable."""
    return ProcessHealthOut(**await health())


@router.get("/definition", response_model=ProcessDefinitionOut)
async def process_definition(_: CurrentUser) -> ProcessDefinitionOut:
    """The workflow as the code defines it — the same data both engines execute."""
    return ProcessDefinitionOut(**definition.describe())


@router.post("/sla/sweep", response_model=SlaSweepOut)
async def run_sla_sweep(
    request: Request, db: DbSession, user: SupervisorUser
) -> SlaSweepOut:
    """Run the SLA check now instead of waiting for the timer.

    Escalates every review that is already past its SLA and has not been escalated before. A
    review that is not overdue is untouched — this cannot manufacture an escalation.
    """
    escalated = await escalation.escalate_overdue()
    await record_user_event(
        db,
        user=user,
        action="process.sla.sweep",
        label=(
            f"{user.full_name} ran the SLA check — {escalated} review(s) escalated"
            if escalated
            else f"{user.full_name} ran the SLA check — nothing was overdue"
        ),
        detail={"escalated": escalated},
        ip_address=client_ip(request),
    )
    await db.commit()
    return SlaSweepOut(
        escalated=escalated,
        note=(
            f"{escalated} overdue review(s) escalated to a supervisor."
            if escalated
            else "No review is past its SLA, so nothing was escalated."
        ),
    )


@router.get("/audit-integrity", response_model=AuditIntegrityOut)
async def audit_integrity(db: DbSession, _: CurrentUser) -> AuditIntegrityOut:
    """Whether the database is enforcing the append-only rule on the audit trail."""
    return AuditIntegrityOut(**await audit_trail.verify(db))
