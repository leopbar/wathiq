"""M5: evaluation provenance and permanent reviewer regression snapshots."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "d8e3f5b29c71"
down_revision = "c7d2e4a18b60"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quality_runs", sa.Column("provenance", postgresql.JSONB(),
                                          nullable=False, server_default="{}"))
    op.create_table(
        "regression_examples",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source_key", sa.String(160), nullable=False, unique=True),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("expected", sa.Text(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("field_schema", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("regression_examples")
    op.drop_column("quality_runs", "provenance")
