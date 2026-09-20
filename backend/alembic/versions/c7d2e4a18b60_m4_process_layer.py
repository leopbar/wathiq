"""M4: postings, SLA escalation, and an append-only audit trail

Three additions for the process layer:

* `postings` — one row per attempt to hand a case to the system of record, whether it was
  posted, skipped or failed. `idempotency_key` is UNIQUE, which is the database-level guarantee
  that a redelivered task cannot post twice. A skip is recorded with its reason, because
  "nothing was posted" is an audit answer.
* `review_tasks.escalated_at` — set once, the first time the SLA timer found a review still
  open. Both process engines check it before escalating, so a redelivered timer or a repeated
  sweep cannot escalate the same review twice.
* a trigger that makes `events` genuinely append-only. Until now the table was append-only by
  convention: nothing in the code updated or deleted a row. Convention is not a control, so
  PostgreSQL now raises on any UPDATE or DELETE against it. The same statement is attached to
  the table's metadata, so a database created by `create_all` (the test database) gets it too.

Revision ID: c7d2e4a18b60
Revises: b3f1c07a91d4
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.models import EVENTS_APPEND_ONLY_SQL

revision: str = "c7d2e4a18b60"
down_revision: str | None = "b3f1c07a91d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POSTING_STATUSES = ("posted", "skipped", "failed")


def upgrade() -> None:
    op.create_table(
        "postings",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("customer_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("approval_kind", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("approved_by", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("response", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('" + "', '".join(POSTING_STATUSES) + "')",
            name="posting_status",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name="fk_postings_case_id_cases", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_postings"),
    )
    op.create_index("ix_postings_case_id", "postings", ["case_id"])
    # UNIQUE, not just indexed: this is the constraint that makes posting exactly-once even if
    # two workers try at the same moment.
    op.create_index(
        "ix_postings_idempotency_key", "postings", ["idempotency_key"], unique=True
    )

    op.add_column(
        "review_tasks",
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(EVENTS_APPEND_ONLY_SQL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS events_no_update_delete ON events")
    op.execute("DROP FUNCTION IF EXISTS events_append_only()")
    op.drop_column("review_tasks", "escalated_at")
    op.drop_index("ix_postings_idempotency_key", table_name="postings")
    op.drop_index("ix_postings_case_id", table_name="postings")
    op.drop_table("postings")
