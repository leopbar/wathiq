"""Posting an approved case to the system of record.

This is the only step in Wathiq that changes something outside Wathiq, so it is the step where
being careful matters most. Three rules, and each one is enforced rather than promised:

**1. Only after an approval.** Either a named reviewer approved the case, or the
straight-through policy did — and which of the two is recorded on the posting, not blurred into
"approved". The simulated core banking server refuses a post that names no approver.

**2. Exactly once.** Every posting carries an idempotency key derived from the workflow
instance, so the same case always produces the same key. The key is honoured in two
independent places: a UNIQUE column in our database, and the system of record's own key table.
A Conductor redelivery, a worker crash between the call and the commit, or two workers racing
all end with one posting.

**3. Never silently skipped.** A case that is not posted gets a `postings` row saying why —
rejected, no matching customer, or the server not configured. "Nothing was posted" is an
audit answer, and it has to be written down.

Everything here talks to the *simulated* core banking MCP server. Nothing reaches a real bank.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.tools import ToolBroker
from app.db import models
from app.db.enums import ActorType, CaseStatus, PostingStatus, ReviewDecision, ReviewStatus
from app.db.session import SessionLocal
from app.services.events import record_event

logger = logging.getLogger(__name__)

# Bumped only if the payload we send changes shape. It is part of the idempotency key, so a
# genuine change of contract can post again while a retry of the old contract cannot.
POSTING_CONTRACT_VERSION = "1"

HUMAN_APPROVAL = "human"
POLICY_APPROVAL = "straight_through_policy"
# The named authority for a case no person looked at. A policy, with an identifier, so the
# audit trail never says a human approved something a human never saw.
STRAIGHT_THROUGH_AUTHORITY = "Straight-through policy STP-001"


def idempotency_key(case: models.Case) -> str:
    """Derived, never random — that is the whole point.

    Tied to the workflow instance rather than the case: restarting a workflow is a deliberate
    decision to run the business process again, and should be allowed to post again. Retrying
    a step inside the same instance is not.
    """
    return f"{case.thread_id}:kyc_refresh:{POSTING_CONTRACT_VERSION}"


class Approval:
    """Who allowed this posting, and of what kind."""

    __slots__ = ("at", "by", "kind")

    def __init__(self, kind: str, by: str, at: datetime | None = None) -> None:
        self.kind = kind
        self.by = by
        self.at = at or datetime.now(UTC)


def _approval(case: models.Case) -> Approval | None:
    """The approval that allows this case to be posted, or None if there isn't one."""
    for task in case.review_tasks:
        if task.status != ReviewStatus.completed:
            continue
        if task.decision in (ReviewDecision.approve, ReviewDecision.correct):
            who = task.assigned_to.full_name if task.assigned_to else "Reviewer"
            return Approval(HUMAN_APPROVAL, who, task.completed_at)
    if case.straight_through:
        return Approval(POLICY_APPROVAL, STRAIGHT_THROUGH_AUTHORITY)
    return None


async def _existing(db: AsyncSession, key: str) -> models.Posting | None:
    return (
        await db.execute(select(models.Posting).where(models.Posting.idempotency_key == key))
    ).scalar_one_or_none()


async def _load(db: AsyncSession, case_id: UUID) -> models.Case | None:
    return (
        await db.execute(
            select(models.Case)
            .options(
                selectinload(models.Case.review_tasks).selectinload(models.ReviewTask.assigned_to),
                selectinload(models.Case.fields),
            )
            .where(models.Case.id == case_id)
        )
    ).scalar_one_or_none()


def _result(posting: models.Posting) -> dict[str, Any]:
    return {
        "status": posting.status.value,
        "reference": posting.reference,
        "duplicate": posting.duplicate,
        "customer_id": posting.customer_id,
        "approval_kind": posting.approval_kind,
        "approved_by": posting.approved_by,
        "note": posting.note,
        "simulated": True,
    }


async def _record(
    db: AsyncSession,
    case: models.Case,
    *,
    key: str,
    status: PostingStatus,
    note: str,
    approval: Approval | None = None,
    reference: str | None = None,
    customer_id: str = "",
    duplicate: bool = False,
    response: dict[str, Any] | None = None,
) -> models.Posting:
    """Insert the posting row and the matching event, and survive losing an insert race."""
    posting = models.Posting(
        case_id=case.id,
        idempotency_key=key,
        status=status,
        reference=reference,
        customer_id=customer_id,
        approval_kind=approval.kind if approval else "",
        approved_by=approval.by if approval else "",
        duplicate=duplicate,
        note=note,
        response=response,
        posted_at=datetime.now(UTC) if status == PostingStatus.posted else None,
    )
    db.add(posting)
    try:
        await db.flush()
    except IntegrityError:
        # Another worker inserted the same key between our check and our insert. The UNIQUE
        # constraint is what caught it; the winner's row is the truth.
        await db.rollback()
        logger.info("posting race for case %s resolved by the unique key", case.id)
        winner = await _existing(db, key)
        if winner is not None:
            return winner
        raise

    await record_event(
        db,
        case_id=case.id,
        action="process.posted" if status == PostingStatus.posted else "process.post.skipped",
        label=(
            f"Posted to core banking (SIMULATED): {reference}"
            if status == PostingStatus.posted
            else f"Not posted: {note}"
        ),
        actor="core-banking worker",
        actor_type=ActorType.system,
        detail={
            "reference": reference,
            "idempotency_key": key,
            "duplicate": duplicate,
            "approval_kind": posting.approval_kind,
            "approved_by": posting.approved_by,
            "customer_id": customer_id,
            "status": status.value,
            "note": note,
            "simulated": True,
        },
    )
    return posting


async def post_case(case_id: UUID) -> dict[str, Any]:
    """Post the case if it may be posted. Safe to call any number of times."""
    async with SessionLocal() as db:
        case = await _load(db, case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found")

        key = idempotency_key(case)
        already = await _existing(db, key)
        if already is not None:
            # Nothing is sent. The first attempt's outcome is the answer, whatever it was.
            logger.info("case %s already has posting %s", case.reference, already.status.value)
            return _result(already)

        if case.status == CaseStatus.rejected:
            posting = await _record(
                db,
                case,
                key=key,
                status=PostingStatus.skipped,
                note="The case was rejected, so no refresh was posted.",
            )
            await db.commit()
            return _result(posting)

        approval = _approval(case)
        if approval is None:
            posting = await _record(
                db,
                case,
                key=key,
                status=PostingStatus.skipped,
                note=(
                    "No approval on file — neither a reviewer's decision nor the "
                    "straight-through policy. Nothing was posted."
                ),
            )
            await db.commit()
            return _result(posting)

        broker = ToolBroker.for_node("post")
        if not broker.available("core_banking"):
            posting = await _record(
                db,
                case,
                key=key,
                status=PostingStatus.skipped,
                approval=approval,
                note=(
                    "The core banking tool server is not configured, so the posting did not "
                    "happen. This is recorded rather than assumed to have worked."
                ),
            )
            await db.commit()
            return _result(posting)

        # --- find the customer file the refresh belongs to ---
        lookup = await broker.call("core_banking", "get_customer", name=case.customer_name)
        customer = (lookup.result or {}).get("customer") if lookup.ok else None
        if not customer:
            posting = await _record(
                db,
                case,
                key=key,
                status=PostingStatus.skipped,
                approval=approval,
                note=(
                    f"No customer matching '{case.customer_name}' in the simulated core "
                    "banking system, so there is no file to refresh."
                ),
                response=lookup.result if lookup.ok else {"error": lookup.error},
            )
            await db.commit()
            return _result(posting)

        # --- post ---
        values = {
            field.name: (field.corrected_value or field.value or "") for field in case.fields
        }
        call = await broker.call(
            "core_banking",
            "post_kyc_refresh",
            case_id=str(case.id),
            customer_id=str(customer.get("customer_id", "")),
            idempotency_key=key,
            approved_by=approval.by,
            approval_kind=approval.kind,
            approved_at=approval.at.isoformat(),
            fields=values,
        )
        payload = call.result or {}
        if not call.ok or not payload.get("posted"):
            note = (
                payload.get("error")
                or call.error
                or "The system of record refused the posting."
            )
            posting = await _record(
                db,
                case,
                key=key,
                status=PostingStatus.failed,
                approval=approval,
                customer_id=str(customer.get("customer_id", "")),
                note=str(note),
                response=payload or {"error": call.error},
            )
            await db.commit()
            return _result(posting)

        posting = await _record(
            db,
            case,
            key=key,
            status=PostingStatus.posted,
            approval=approval,
            reference=str(payload.get("reference", "")),
            customer_id=str(customer.get("customer_id", "")),
            duplicate=bool(payload.get("duplicate")),
            note=(
                "The system of record recognised the idempotency key and returned the "
                "original reference."
                if payload.get("duplicate")
                else f"{len(values)} field(s) posted against the customer file."
            ),
            response=payload,
        )
        await db.commit()
        return _result(posting)


async def for_case(db: AsyncSession, case_id: UUID) -> models.Posting | None:
    """The posting attempt for a case, for the UI and the API."""
    return (
        await db.execute(
            select(models.Posting)
            .where(models.Posting.case_id == case_id)
            .order_by(models.Posting.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
