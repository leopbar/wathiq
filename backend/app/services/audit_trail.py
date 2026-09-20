"""Checking that the audit trail really is append-only.

"Append-only" is easy to claim and easy to get wrong. In Wathiq the guarantee is a database
trigger on `events` that raises on any UPDATE or DELETE (see `EVENTS_APPEND_ONLY_SQL` in
`db/models.py`), so the application cannot rewrite history even by accident.

This module reports on that guarantee instead of asserting it. `verify` looks for the trigger
in PostgreSQL's own catalogue and says what it found. It is deliberately honest about the
limit: a database superuser can drop a trigger, so this proves the application cannot tamper
with the log, not that nobody on earth can. A tamper-evident hash chain would be the next step,
and it is listed as future work rather than implied here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models

TRIGGER_NAME = "events_no_update_delete"

_TRIGGER_SQL = text(
    """
    SELECT tgname
    FROM pg_trigger
    WHERE tgrelid = 'events'::regclass
      AND NOT tgisinternal
      AND tgname = :name
    """
)


async def verify(db: AsyncSession, *, case_id: Any | None = None) -> dict[str, Any]:
    """What the audit trail contains, and whether the database is enforcing append-only."""
    try:
        enforced = bool((await db.execute(_TRIGGER_SQL, {"name": TRIGGER_NAME})).scalar())
        detail = (
            "PostgreSQL rejects every UPDATE and DELETE on the events table."
            if enforced
            else (
                "The append-only trigger is MISSING. The log can still only be appended to by "
                "the application, but the database is not enforcing it — investigate before "
                "relying on this trail."
            )
        )
    except Exception as exc:  # a database that cannot answer must not look like a pass
        enforced = False
        detail = f"Could not check the append-only trigger: {type(exc).__name__}"

    stmt = select(
        func.count(models.Event.id),
        func.min(models.Event.seq),
        func.max(models.Event.seq),
        func.min(models.Event.created_at),
        func.max(models.Event.created_at),
    )
    if case_id is not None:
        stmt = stmt.where(models.Event.case_id == case_id)
    rows, first_seq, last_seq, oldest, newest = (await db.execute(stmt)).one()

    return {
        "append_only_enforced": enforced,
        "trigger": TRIGGER_NAME,
        "detail": detail,
        "rows": int(rows or 0),
        "first_seq": int(first_seq) if first_seq is not None else None,
        "last_seq": int(last_seq) if last_seq is not None else None,
        "oldest": oldest.isoformat() if oldest else None,
        "newest": newest.isoformat() if newest else None,
        # Said out loud so nobody reads more into the check than it proves. Sequence gaps are
        # normal (a rolled-back transaction consumes a number), so they are not evidence of
        # anything and are not reported as if they were.
        "limits": (
            "A database superuser could drop the trigger. This check proves the application "
            "cannot alter the log; it is not cryptographic proof. A hash chain per row is the "
            "next step if an auditor needs tamper evidence."
        ),
    }
