"""Add durable pipeline evidence to existing prototype databases."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    if "payload" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("pipeline_runs")}:
        op.add_column("pipeline_runs", sa.Column("payload", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("pipeline_runs", "payload")
