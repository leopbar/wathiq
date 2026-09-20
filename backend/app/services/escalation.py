"""SLA escalation: what happens when a review is late.

The SLA timer runs *beside* the human review, not after it, so a late review is noticed while
it is still open. What escalation does is deliberately modest:

* the review moves into the **supervisor** queue and the case priority is raised;
* the case is **not** decided, cancelled or failed — a late case still needs a human answer;
* if a reviewer already has the task open, they keep it. Taking a half-made decision away from
  someone produces a worse outcome than a late case, so the supervisor is told and the
  reviewer is left to finish.

`escalated_at` is set once. Both engines check it before acting, so a Conductor timer that is
redelivered, or a sweeper that runs every minute, cannot escalate the same review twice.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import models
from app.db.enums import ActorType, Priority, ReviewStatus, Role
from app.db.session import SessionLocal
from app.services.events import record_event

logger = logging.getLogger(__name__)

OPEN_STATUSES = (ReviewStatus.pending, ReviewStatus.in_progress)


async def _escalate(db: AsyncSession, task: models.ReviewTask, *, now: datetime) -> bool:
    """Escalate one task. Returns False if there was nothing to do."""
    if task.escalated_at is not None or task.status not in OPEN_STATUSES:
        return False
    if task.sla_due_at is None or task.sla_due_at.replace(tzinfo=UTC) > now:
        return False

    task.escalated_at = now
    task.assigned_role = Role.supervisor
    # Only an unclaimed task changes hands. See the module docstring.
    handed_over = task.status == ReviewStatus.pending
    if handed_over:
        task.assigned_to_id = None

    case = task.case
    if case.priority == Priority.normal:
        case.priority = Priority.high

    overdue_minutes = int((now - task.sla_due_at.replace(tzinfo=UTC)).total_seconds() // 60)
    await record_event(
        db,
        case_id=case.id,
        action="process.escalated",
        label=(
            f"Review SLA missed by {overdue_minutes} min — escalated to a supervisor"
            if handed_over
            else (
                f"Review SLA missed by {overdue_minutes} min — a supervisor was notified; "
                "the reviewer already working on it keeps the task"
            )
        ),
        actor="sla timer",
        actor_type=ActorType.system,
        detail={
            "review_task_id": str(task.id),
            "reason_code": task.reason_code,
            "sla_due_at": task.sla_due_at.isoformat(),
            "overdue_minutes": overdue_minutes,
            "handed_over": handed_over,
            "assigned_role": Role.supervisor.value,
        },
    )
    logger.info(
        "escalated review %s for case %s (%d min overdue)", task.id, case.reference, overdue_minutes
    )
    return True


async def escalate_case(case_id: UUID) -> dict[str, object]:
    """Escalate whatever is overdue on one case. Called by the SLA timer branch."""
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        tasks = (
            await db.execute(
                select(models.ReviewTask)
                .options(selectinload(models.ReviewTask.case))
                .where(
                    models.ReviewTask.case_id == case_id,
                    models.ReviewTask.status.in_(OPEN_STATUSES),
                )
            )
        ).scalars().all()

        escalated = 0
        for task in tasks:
            if await _escalate(db, task, now=now):
                escalated += 1
        await db.commit()

    return {
        "escalated": escalated,
        "note": (
            "The review was answered before the SLA expired, so there was nothing to escalate."
            if not escalated
            else f"{escalated} review(s) escalated to a supervisor."
        ),
    }


async def escalate_overdue(limit: int = 50) -> int:
    """Escalate every overdue review in the system. The in-process engine's SLA service.

    Conductor has a timer per case; without it, one sweep over the queue does the same job.
    The behaviour a reviewer sees is identical, which is the point of having both.
    """
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        tasks = (
            await db.execute(
                select(models.ReviewTask)
                .options(selectinload(models.ReviewTask.case))
                .where(
                    models.ReviewTask.status.in_(OPEN_STATUSES),
                    models.ReviewTask.escalated_at.is_(None),
                    models.ReviewTask.sla_due_at.is_not(None),
                    models.ReviewTask.sla_due_at < now,
                )
                .order_by(models.ReviewTask.sla_due_at.asc())
                .limit(limit)
            )
        ).scalars().all()

        count = 0
        for task in tasks:
            if await _escalate(db, task, now=now):
                count += 1
        await db.commit()
    return count
