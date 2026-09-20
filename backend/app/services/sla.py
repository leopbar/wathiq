"""SLA helpers — one definition used by cases, the review queue and the dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.db.enums import TERMINAL_STATUSES, CaseStatus
from app.schemas.case import SlaState


def sla_state(
    due_at: datetime | None,
    *,
    status: CaseStatus | None = None,
    now: datetime | None = None,
) -> SlaState:
    """`at_risk` means less than `sla_at_risk_fraction` of the SLA window is left."""
    if due_at is None or (status is not None and status in TERMINAL_STATUSES):
        return "none"
    now = now or datetime.now(UTC)
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    if now >= due_at:
        return "breached"
    warn_window = timedelta(hours=settings.review_sla_hours * settings.sla_at_risk_fraction)
    return "at_risk" if due_at - now <= warn_window else "on_track"


def default_due_at(from_time: datetime | None = None) -> datetime:
    return (from_time or datetime.now(UTC)) + timedelta(hours=settings.review_sla_hours)
