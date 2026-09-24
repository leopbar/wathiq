"""M7: store an English reading beside an Arabic value.

The value column keeps what the document says — it is the evidence, it is what the audit trail
holds and what the posting step sends. The translation is a separate column so the two can
never be confused, and `translation_source` records whether a glossary or the model produced
it, because "the model said so" and "a dictionary said so" are different claims.

Revision ID: f0b517d41e93
Revises: e9f406c30d82
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f0b517d41e93"
down_revision = "e9f406c30d82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extracted_fields",
        sa.Column("value_translated", sa.Text(), nullable=True),
    )
    op.add_column(
        "extracted_fields",
        sa.Column("translation_source", sa.String(length=16), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("extracted_fields", "translation_source")
    op.drop_column("extracted_fields", "value_translated")
