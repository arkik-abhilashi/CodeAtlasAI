"""Store new import archives as shared filesystem paths.

Revision ID: 0003_streamed_import_archives
Revises: 0002_persistent_import_jobs
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_streamed_import_archives"
down_revision = "0002_persistent_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "repository_import_payloads",
        sa.Column("archive_path", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repository_import_payloads", "archive_path")
