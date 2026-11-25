"""Initial CodeAtlas relational schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(512), nullable=False), sa.Column("display_name", sa.String(120), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("repositories", sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("source_url", sa.String(2048)), sa.Column("source_type", sa.String(24), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("progress", sa.Integer(), nullable=False), sa.Column("stats", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_repositories_owner_id", "repositories", ["owner_id"])
    op.create_index("ix_repositories_status", "repositories", ["status"])
    op.create_index("ix_repositories_owner_updated", "repositories", ["owner_id", "updated_at"])
    op.create_table("repository_files", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("path", sa.String(1024), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("language", sa.String(40)), sa.Column("source_content", sa.Text()), sa.Column("analysis_data", sa.JSON(), nullable=False), sa.Column("is_entry_point", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("repository_id", "path", name="uq_repository_file_path"))
    op.create_index("ix_repository_files_repository_id", "repository_files", ["repository_id"])
    op.create_index("ix_repository_files_language", "repository_files", ["language"])
    op.create_index("ix_repository_files_repository_language", "repository_files", ["repository_id", "language"])
    op.create_table("analysis_results", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("metrics", sa.JSON(), nullable=False), sa.Column("findings", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_analysis_results_repository_id", "analysis_results", ["repository_id"])
    op.create_table("analysis_jobs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("progress", sa.Integer(), nullable=False), sa.Column("stage", sa.String(100), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_index("ix_analysis_jobs_repository_id", "analysis_jobs", ["repository_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_table("saved_graphs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("graph_data", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_saved_graphs_repository_id", "saved_graphs", ["repository_id"])
    op.create_table("dependencies", sa.Column("id", sa.String(36), primary_key=True), sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False), sa.Column("source_file_id", sa.String(36), sa.ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False), sa.Column("target_file_id", sa.String(36), sa.ForeignKey("repository_files.id", ondelete="CASCADE")), sa.Column("import_name", sa.String(1024), nullable=False), sa.Column("line", sa.Integer(), nullable=False), sa.Column("resolved", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_dependencies_repository_id", "dependencies", ["repository_id"])
    op.create_index("ix_dependencies_source_file_id", "dependencies", ["source_file_id"])
    op.create_index("ix_dependencies_target_file_id", "dependencies", ["target_file_id"])
    op.create_index("ix_dependencies_repository_resolved", "dependencies", ["repository_id", "resolved"])
    op.create_table("revoked_tokens", sa.Column("jti", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade():
    op.drop_table("revoked_tokens")
    op.drop_table("dependencies")
    op.drop_table("saved_graphs")
    op.drop_table("analysis_jobs")
    op.drop_table("analysis_results")
    op.drop_table("repository_files")
    op.drop_table("repositories")
    op.drop_table("users")
