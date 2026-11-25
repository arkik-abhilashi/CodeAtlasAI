import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, Repository, RepositoryFile, RepositoryImportPayload
from app.jobs.queue import enqueue_analysis, enqueue_import

logger = logging.getLogger(__name__)


def create_repository(db: Session, owner_id: str, name: str, files: dict[str, str], source_type: str, source_url: str | None = None, metadata: dict | None = None) -> tuple[Repository, AnalysisJob]:
    repository = Repository(owner_id=owner_id, name=name[:255], source_url=source_url, source_type=source_type, metadata_json=metadata or {}, status="queued", progress=0)
    db.add(repository)
    db.flush()
    for path, content in files.items():
        db.add(RepositoryFile(repository_id=repository.id, path=path, size_bytes=len(content.encode("utf-8")), source_content=content))
    job = AnalysisJob(repository_id=repository.id, status="queued", progress=0, stage="Waiting for analysis worker")
    db.add(job)
    db.commit()
    db.refresh(repository)
    db.refresh(job)
    try:
        enqueue_analysis(job.id)
    except Exception as exc:
        logger.exception("Failed to enqueue analysis job %s", job.id)
        job.status = repository.status = "failed"
        job.stage = "Analysis queue unavailable"
        job.error_message = "The analysis queue is unavailable. Start Redis and an RQ worker, then retry the import."
        db.commit()
        raise HTTPException(503, job.error_message) from exc
    return repository, job


def create_import_job(db: Session, owner_id: str, name: str, source_type: str, source_url: str | None = None, metadata: dict | None = None, archive: bytes | None = None, idempotency_key: str | None = None) -> tuple[Repository, AnalysisJob]:
    if idempotency_key:
        existing = db.scalar(select(AnalysisJob).where(AnalysisJob.idempotency_key == idempotency_key))
        if existing:
            repository = db.get(Repository, existing.repository_id)
            if repository and repository.owner_id == owner_id:
                return repository, existing
            raise HTTPException(409, "That import request key is already in use")

    repository = Repository(owner_id=owner_id, name=name[:255], source_url=source_url, source_type=source_type, metadata_json=metadata or {}, status="queued", progress=0)
    db.add(repository)
    db.flush()
    job = AnalysisJob(repository_id=repository.id, status="queued", progress=0, stage="Queued for import processing", idempotency_key=idempotency_key)
    db.add(job)
    if archive is not None:
        db.add(RepositoryImportPayload(repository_id=repository.id, archive_data=archive))
    db.commit()
    db.refresh(repository)
    db.refresh(job)
    try:
        enqueue_import(job.id)
    except Exception as exc:
        logger.exception("Could not queue repository import repository=%s job=%s", repository.id, job.id)
        db.execute(delete(RepositoryImportPayload).where(RepositoryImportPayload.repository_id == repository.id))
        job.status = repository.status = "failed"
        job.stage = "Import could not be queued"
        job.error_message = str(exc)[:2000]
        from datetime import datetime, timezone
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
    return repository, job


def owned_repository(db: Session, owner_id: str, repository_id: str) -> Repository:
    repository = db.scalar(select(Repository).where(Repository.id == repository_id, Repository.owner_id == owner_id))
    if repository is None:
        raise HTTPException(404, "Repository not found")
    return repository


def public_repository(repository: Repository) -> dict:
    return {"id": repository.id, "name": repository.name, "source_url": repository.source_url, "source_type": repository.source_type, "status": repository.status, "progress": repository.progress, "stats": repository.stats, "metadata": repository.metadata_json, "created_at": repository.created_at.isoformat() if repository.created_at else None}
