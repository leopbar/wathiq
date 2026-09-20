"""M5: local record of every calibration experiment, including refused fits."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "e9f406c30d82"
down_revision = "d8e3f5b29c71"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("calibration_experiments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("tracking", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()))


def downgrade():
    op.drop_table("calibration_experiments")
