"""Persist import payloads and detailed ingestion progress.

Revision ID: 0002_persistent_import_jobs
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_persistent_import_jobs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_jobs", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("analysis_jobs", sa.Column("files_discovered", sa.Integer(), server_default="0", nullable=False))
    op.add_column("analysis_jobs", sa.Column("files_processed", sa.Integer(), server_default="0", nullable=False))
    op.add_column("analysis_jobs", sa.Column("files_skipped", sa.Integer(), server_default="0", nullable=False))
    op.add_column("analysis_jobs", sa.Column("skip_reasons", sa.JSON(), server_default="{}", nullable=False))
    op.create_index("ix_analysis_jobs_idempotency_key", "analysis_jobs", ["idempotency_key"], unique=True)
    op.create_table(
        "repository_import_payloads",
        sa.Column("repository_id", sa.String(length=36), nullable=False),
        sa.Column("archive_data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("repository_id"),
    )


def downgrade() -> None:
    op.drop_table("repository_import_payloads")
    op.drop_index("ix_analysis_jobs_idempotency_key", table_name="analysis_jobs")
    op.drop_column("analysis_jobs", "skip_reasons")
    op.drop_column("analysis_jobs", "files_skipped")
    op.drop_column("analysis_jobs", "files_processed")
    op.drop_column("analysis_jobs", "files_discovered")
    op.drop_column("analysis_jobs", "idempotency_key")
