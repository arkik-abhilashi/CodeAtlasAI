import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (Index("ix_repositories_owner_updated", "owner_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(24), default="upload", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner: Mapped["User"] = relationship(back_populates="repositories")
    files: Mapped[list["RepositoryFile"]] = relationship(back_populates="repository", cascade="all, delete-orphan", passive_deletes=True)
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(back_populates="repository", cascade="all, delete-orphan", passive_deletes=True)
    jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="repository", cascade="all, delete-orphan", passive_deletes=True)
    saved_graphs: Mapped[list["SavedGraph"]] = relationship(back_populates="repository", cascade="all, delete-orphan", passive_deletes=True)


class RepositoryFile(Base):
    __tablename__ = "repository_files"
    __table_args__ = (UniqueConstraint("repository_id", "path", name="uq_repository_file_path"), Index("ix_repository_files_repository_language", "repository_id", "language"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    language: Mapped[str | None] = mapped_column(String(40), index=True)
    source_content: Mapped[str | None] = mapped_column(Text)
    analysis_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_entry_point: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    repository: Mapped[Repository] = relationship(back_populates="files")
    outgoing_dependencies: Mapped[list["Dependency"]] = relationship(foreign_keys="Dependency.source_file_id", back_populates="source_file", cascade="all, delete-orphan", passive_deletes=True)
    incoming_dependencies: Mapped[list["Dependency"]] = relationship(foreign_keys="Dependency.target_file_id", back_populates="target_file", passive_deletes=True)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    repository: Mapped[Repository] = relationship(back_populates="analysis_results")


class Dependency(Base):
    __tablename__ = "dependencies"
    __table_args__ = (Index("ix_dependencies_repository_resolved", "repository_id", "resolved"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    source_file_id: Mapped[str] = mapped_column(ForeignKey("repository_files.id", ondelete="CASCADE"), index=True, nullable=False)
    target_file_id: Mapped[str | None] = mapped_column(ForeignKey("repository_files.id", ondelete="CASCADE"), index=True)
    import_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    line: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source_file: Mapped[RepositoryFile] = relationship(foreign_keys=[source_file_id], back_populates="outgoing_dependencies")
    target_file: Mapped[RepositoryFile | None] = relationship(foreign_keys=[target_file_id], back_populates="incoming_dependencies")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str] = mapped_column(String(100), default="Queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    files_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    files_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skip_reasons: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository: Mapped[Repository] = relationship(back_populates="jobs")


class RepositoryImportPayload(Base):
    __tablename__ = "repository_import_payloads"

    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True)
    archive_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SavedGraph(Base):
    __tablename__ = "saved_graphs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    graph_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    repository: Mapped[Repository] = relationship(back_populates="saved_graphs")
