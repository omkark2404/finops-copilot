"""Baseline metadata schema, compatible with the pre-migration prototype tables."""

from alembic import op
from app import models  # noqa: F401
from app.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Existing prototype tables are retained; future schema changes need separate revisions.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Destructive baseline downgrade is disabled; restore a tested backup")
