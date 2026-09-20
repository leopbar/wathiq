"""M3: confidence signals, calibration curves, policy RAG index

Three additions, all of them for the AI-depth milestone:

* `extracted_fields.signals` — the evidence a confidence score was built from, so the case
  screen can show why a number is what it is instead of only what it is.
* `calibration_curves` — the fitted mapping from a raw score to a calibrated probability. One
  row per fit; old rows are kept so a closed case can be read with the curve of its time.
* `policy_chunks` — the RAG index over the synthetic policy pack, using pgvector. The `vector`
  extension is already created by the initial migration.

No ANN index is created on the embedding column. The corpus is a few dozen sections, so an
exact scan is faster than an approximate index, and an ivfflat index built on this little data
would return worse results. When the corpus grows past a few thousand chunks, an HNSW index is
one migration away.

Revision ID: b3f1c07a91d4
Revises: 87c6c95ba42a
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "b3f1c07a91d4"
down_revision: str | None = "87c6c95ba42a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "extracted_fields",
        sa.Column("signals", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "calibration_curves",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("a", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("b", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brier_before", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("brier_after", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("model_version", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("method", sa.String(length=40), nullable=False, server_default="platt"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "fitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_curves"),
    )
    op.create_index(
        "ix_calibration_curves_is_active", "calibration_curves", ["is_active"], unique=False
    )
    op.create_index(
        "ix_calibration_curves_fitted_at", "calibration_curves", ["fitted_at"], unique=False
    )

    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", sa.String(length=40), nullable=False),
        sa.Column("policy_title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("section", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("citation", sa.String(length=80), nullable=False),
        sa.Column("heading", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", Vector(256), nullable=False),
        sa.Column("embedder_version", sa.String(length=80), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_chunks"),
        sa.UniqueConstraint("citation", name="uq_policy_chunks_citation"),
    )
    op.create_index("ix_policy_chunks_policy_id", "policy_chunks", ["policy_id"], unique=False)
    op.create_index("ix_policy_chunks_citation", "policy_chunks", ["citation"], unique=False)
    op.create_index("ix_policy_chunks_created_at", "policy_chunks", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_policy_chunks_created_at", table_name="policy_chunks")
    op.drop_index("ix_policy_chunks_citation", table_name="policy_chunks")
    op.drop_index("ix_policy_chunks_policy_id", table_name="policy_chunks")
    op.drop_table("policy_chunks")
    op.drop_index("ix_calibration_curves_fitted_at", table_name="calibration_curves")
    op.drop_index("ix_calibration_curves_is_active", table_name="calibration_curves")
    op.drop_table("calibration_curves")
    op.drop_column("extracted_fields", "signals")
