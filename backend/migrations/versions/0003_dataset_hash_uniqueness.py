"""Enforce owner/file uniqueness without deleting pre-existing billing records."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None
INDEX = "uq_datasets_owner_content_hash"


def upgrade():
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text("""
        SELECT 1 FROM datasets
        WHERE created_by IS NOT NULL AND content_hash IS NOT NULL
        GROUP BY created_by, content_hash HAVING COUNT(*) > 1 LIMIT 1
    """)
    ).first()
    if duplicate:
        raise RuntimeError(
            "Duplicate owner/file hashes exist. Back up metadata and Parquet, review the duplicate "
            "datasets and remove only owner-confirmed duplicates before retrying migration 0003. "
            "No billing records have been deleted by this migration."
        )
    if INDEX not in {item["name"] for item in sa.inspect(connection).get_indexes("datasets")}:
        op.create_index(INDEX, "datasets", ["created_by", "content_hash"], unique=True)


def downgrade():
    op.drop_index(INDEX, table_name="datasets")
