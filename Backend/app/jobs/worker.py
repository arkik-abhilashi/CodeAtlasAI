import logging
import faulthandler
import time
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AnalysisJob, AnalysisResult, Dependency, Repository, RepositoryFile, RepositoryImportPayload
from app.db.session import SessionLocal
from app.services.architecture_analysis import architecture_report
from app.services.dependency_analysis import analyze_dependencies
from app.services.language_parsers import language_for_path
from app.services.repository_ingestion import extract_repository_metadata, extract_zip_report, fetch_github_repository

logger = logging.getLogger(__name__)
faulthandler.enable(all_threads=True)


class AnalysisCancelled(Exception):
    """Raised when a user requests cancellation between analysis batches."""


def _import_progress(db: Session, job: AnalysisJob, repository: Repository, value: int, stage: str) -> None:
    db.refresh(job)
    if job.status in {"cancelled", "cancelling"}:
        raise AnalysisCancelled
    job.status = repository.status = "running"
    job.progress = repository.progress = max(job.progress, min(39, int(value)))
    job.stage = stage[:100]
    db.commit()
    logger.info("Repository import progress", extra={"repository_id": repository.id, "job_id": job.id, "stage": stage, "progress": job.progress, "files_discovered": job.files_discovered, "files_processed": job.files_processed, "files_skipped": job.files_skipped})


def process_repository_import(job_id: str) -> None:
    """Download/extract a repository into persistent rows, then analyze it."""
    db = SessionLocal()
    try:
        job = db.get(AnalysisJob, job_id)
        if job is None or job.status in {"completed", "failed", "cancelled"}:
            return
        if job.status == "running":
            logger.warning("Skipping duplicate import worker", extra={"repository_id": job.repository_id, "job_id": job.id, "stage": job.stage})
            return
        repository = db.get(Repository, job.repository_id)
        if repository is None:
            _set_terminal(db, job.id, "failed", "Repository was removed", "Repository was removed before import processing started.")
            return
        claimed_at = datetime.now(timezone.utc)
        claimed = db.execute(update(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.status == "queued").values(status="running", progress=max(job.progress, 2), stage="Preparing import", started_at=claimed_at, finished_at=None, error_message=None))
        if claimed.rowcount != 1:
            db.rollback()
            logger.info("Import job already claimed", extra={"repository_id": repository.id, "job_id": job.id, "stage": job.stage})
            return
        repository.status = "running"
        repository.progress = max(repository.progress, 2)
        db.commit()
        db.refresh(job)
        logger.info("Repository import started", extra={"repository_id": repository.id, "job_id": job.id, "stage": job.stage, "worker_id": _worker_identity()})

        if repository.source_type == "github":
            _import_progress(db, job, repository, 4, "Downloading GitHub archive")
            last_download_progress = 0
            def downloaded(received: int, total: int) -> None:
                nonlocal last_download_progress
                if total > 0:
                    value = 4 + int(12 * received / total)
                    if value > last_download_progress:
                        _import_progress(db, job, repository, value, f"Downloading GitHub archive: {received // (1024 * 1024)} MB")
                        last_download_progress = value
            files, repository_name, metadata, ingestion = fetch_github_repository(repository.source_url or "", downloaded)
            repository.name = repository_name[:255]
            repository.metadata_json = {**repository.metadata_json, **metadata}
        else:
            _import_progress(db, job, repository, 10, "Scanning uploaded ZIP archive")
            payload = db.get(RepositoryImportPayload, repository.id)
            if payload is None:
                raise RuntimeError("The uploaded archive is missing from persistent import storage.")
            files, ingestion = extract_zip_report(payload.archive_data)
            metadata = extract_repository_metadata(files)
            repository.metadata_json = {**repository.metadata_json, **metadata}

        job.files_discovered = ingestion["files_discovered"]
        job.files_skipped = ingestion["files_skipped"]
        job.skip_reasons = ingestion["skip_reasons"]
        repository.metadata_json = {**repository.metadata_json, "ingestion": ingestion}
        db.commit()
        _import_progress(db, job, repository, 20, f"Scanning complete: {len(files)} eligible files; {job.files_skipped} skipped")

        existing = db.scalar(select(RepositoryFile.id).where(RepositoryFile.repository_id == repository.id).limit(1))
        if existing:
            db.execute(delete(RepositoryFile).where(RepositoryFile.repository_id == repository.id))
        batch_size = 200
        paths = list(files.items())
        for offset in range(0, len(paths), batch_size):
            db.refresh(job)
            if job.status in {"cancelled", "cancelling"}:
                raise AnalysisCancelled
            batch = paths[offset:offset + batch_size]
            db.add_all(RepositoryFile(repository_id=repository.id, path=path, size_bytes=len(content.encode("utf-8")), source_content=content) for path, content in batch)
            db.flush()
            job.files_processed = min(offset + len(batch), len(paths))
            progress = 20 + int(18 * job.files_processed / max(1, len(paths)))
            job.progress = repository.progress = max(job.progress, progress)
            job.stage = f"Saving discovered source files: {job.files_processed}/{len(paths)}"
            repository.status = job.status = "running"
            db.commit()
            logger.info("Repository files persisted", extra={"repository_id": repository.id, "job_id": job.id, "stage": job.stage, "files_discovered": job.files_discovered, "files_processed": job.files_processed, "files_skipped": job.files_skipped, "worker_id": _worker_identity()})

        payload = db.get(RepositoryImportPayload, repository.id)
        if payload:
            db.delete(payload)
        job.status = repository.status = "queued"
        job.stage = "Import complete; waiting for analysis"
        job.progress = repository.progress = 40
        db.commit()
    except AnalysisCancelled:
        db.rollback()
        db.execute(delete(RepositoryImportPayload).where(RepositoryImportPayload.repository_id == job.repository_id))
        db.commit()
        _set_terminal(db, job_id, "cancelled", "Analysis cancelled by user")
        logger.info("Repository import cancelled", extra={"job_id": job_id})
        return
    except Exception as exc:
        db.rollback()
        logger.exception("Repository import failed", extra={"job_id": job_id})
        job = db.get(AnalysisJob, job_id)
        if job:
            db.execute(delete(RepositoryImportPayload).where(RepositoryImportPayload.repository_id == job.repository_id))
            db.commit()
        message = str(getattr(exc, "detail", None) or exc)
        _set_terminal(db, job_id, "failed", "Repository import failed", f"{type(exc).__name__}: {message}")
        raise
    finally:
        db.close()

    process_analysis(job_id)


def _worker_identity() -> str | None:
    try:
        from rq import get_current_job
        current = get_current_job()
        return current.worker_name if current else None
    except Exception:
        return None


def _set_progress(db: Session, job: AnalysisJob, repository: Repository, value: int, stage: str) -> None:
    db.refresh(job)
    if job.status in {"cancelled", "cancelling"}:
        raise AnalysisCancelled
    value = max(job.progress, min(99, int(value)))
    if value == job.progress and stage == job.stage:
        return
    job.progress = repository.progress = value
    job.stage = stage[:100]
    repository.status = job.status = "running"
    db.commit()
    logger.info("Analysis progress updated", extra={"repository_id": repository.id, "job_id": job.id, "progress": value, "stage": stage, "files_discovered": job.files_discovered, "files_processed": job.files_processed, "files_skipped": job.files_skipped, "worker_id": _worker_identity()})


def _set_terminal(db: Session, job_id: str, status: str, stage: str, error: str | None = None) -> None:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        return
    repository = db.get(Repository, job.repository_id)
    now = datetime.now(timezone.utc)
    job.status = status
    job.stage = stage[:100]
    job.error_message = error[:2000] if error else None
    job.finished_at = now
    if repository:
        repository.status = status
        if status == "completed":
            job.progress = repository.progress = 100
    db.commit()
    logger.info("Analysis entered terminal state", extra={"repository_id": repository.id if repository else None, "job_id": job.id, "stage": stage, "progress": job.progress, "files_discovered": job.files_discovered, "files_processed": job.files_processed, "files_skipped": job.files_skipped, "worker_id": _worker_identity()})


def process_analysis(job_id: str) -> None:
    """Run one repository analysis with durable, monotonic progress updates."""
    db = SessionLocal()
    started = time.monotonic()
    logger.info("Analysis worker execution started", extra={"job_id": job_id, "worker_id": _worker_identity()})
    try:
        job = db.get(AnalysisJob, job_id)
        if job is None:
            logger.error("Analysis job %s no longer exists", job_id)
            return
        if job.status in {"completed", "failed", "cancelled"}:
            logger.info("Skipping terminal analysis job=%s status=%s", job_id, job.status)
            return
        if job.status == "running":
            logger.warning("Skipping duplicate execution for running analysis job=%s", job_id)
            return
        repository = db.get(Repository, job.repository_id)
        if repository is None:
            _set_terminal(db, job_id, "failed", "Repository was removed", "Repository was removed before analysis started.")
            return
        logger.info("Analysis worker claimed repository", extra={"repository_id": repository.id, "job_id": job.id, "stage": "Preparing repository files", "files_discovered": job.files_discovered, "files_processed": job.files_processed, "files_skipped": job.files_skipped, "worker_id": _worker_identity()})

        claimed_at = datetime.now(timezone.utc)
        claimed = db.execute(update(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.status == "queued").values(status="running", stage="Preparing repository files", progress=max(job.progress, 5), started_at=claimed_at, finished_at=None, error_message=None))
        if claimed.rowcount != 1:
            db.rollback()
            logger.info("Analysis job already claimed", extra={"repository_id": repository.id, "job_id": job.id, "stage": job.stage})
            return
        repository.status = "running"
        repository.progress = max(repository.progress, 5)
        db.commit()
        db.refresh(job)

        rows = list(db.scalars(select(RepositoryFile).where(RepositoryFile.repository_id == repository.id).order_by(RepositoryFile.path)))
        source_files = {row.path: row.source_content or "" for row in rows if row.source_content is not None and language_for_path(row.path)}
        imported = job.progress >= 40
        parse_start, parse_span = (40, 30) if imported else (10, 40)
        resolve_start, resolve_span = (70, 15) if imported else (50, 20)
        architecture_progress = 85 if imported else 70
        file_save_progress = 90 if imported else 85
        dependency_save_progress = 94 if imported else 90
        _set_progress(db, job, repository, parse_start, f"Prepared {len(source_files)} supported source files")

        last_saved_progress = parse_start
        def report_progress(phase: str, current: int, total: int) -> None:
            nonlocal last_saved_progress
            start, span, label = (parse_start, parse_span, "Parsing source files") if phase == "parse" else (resolve_start, resolve_span, "Resolving imports")
            value = start + (span if total == 0 else int(span * current / total))
            stride = max(25, (total + 19) // 20)
            # Keep writes to at most about twenty checkpoints per phase, with
            # a minimum batch of twenty-five files for small repositories.
            if (current % stride == 0 or current == total) and value > last_saved_progress:
                _set_progress(db, job, repository, value, f"{label}: {current}/{total}")
                last_saved_progress = value

        result = analyze_dependencies(source_files, on_progress=report_progress)
        job.files_processed = len(result["parsed"])
        db.commit()
        _set_progress(db, job, repository, architecture_progress, "Generating architecture metrics and cycle witnesses")
        report = architecture_report(result)
        _set_progress(db, job, repository, file_save_progress, "Saving parsed file results")

        row_by_path = {row.path: row for row in rows}
        for index, row in enumerate(rows, 1):
            parsed = result["parsed"].get(row.path)
            row.language = language_for_path(row.path)
            if parsed is not None:
                row.analysis_data = parsed
                row.is_entry_point = row.path in result["entry_points"]
            file_stride = max(100, (len(rows) + 9) // 10)
            if index % file_stride == 0 or index == len(rows):
                _set_progress(db, job, repository, file_save_progress + int(4 * index / max(1, len(rows))), f"Saving file results: {index}/{len(rows)}")

        db.execute(delete(Dependency).where(Dependency.repository_id == repository.id))
        db.flush()
        dependency_total = len(result["imports"])
        for index, item in enumerate(result["imports"], 1):
            source = row_by_path.get(item["source"])
            target = row_by_path.get(item["target"]) if item["target"] else None
            if source:
                db.add(Dependency(repository_id=repository.id, source_file_id=source.id, target_file_id=target.id if target else None, import_name=item["import_name"], line=item["line"], resolved=target is not None))
            dependency_stride = max(250, (dependency_total + 9) // 10)
            if index % dependency_stride == 0 or index == dependency_total:
                _set_progress(db, job, repository, dependency_save_progress + int(4 * index / max(1, dependency_total)), f"Saving dependency results: {index}/{dependency_total}")

        _set_progress(db, job, repository, 99, "Saving architecture report and final metrics")
        stats = {
            "files": len(rows),
            "analyzedFiles": len(result["parsed"]),
            "languages": report["metrics"]["languages"],
            "modules": report["metrics"]["modules"],
            "dependencies": report["metrics"]["verified_dependencies"],
            "classes": report["metrics"]["classes"],
            "functions": report["metrics"]["functions_and_methods"],
            "imports": len(result["imports"]),
        }
        repository.stats = stats
        job.status = repository.status = "completed"
        job.progress = repository.progress = 100
        job.stage = "Analysis complete"
        job.finished_at = datetime.now(timezone.utc)
        findings = report["findings"] + [{"type": "unresolved_import", "confidence": "verified", **item} for item in report["unresolved_imports"]]
        db.add(AnalysisResult(repository_id=repository.id, summary=report["summary"], metrics=report["metrics"], findings=findings))
        db.commit()
        logger.info("Analysis worker completed", extra={"repository_id": repository.id, "job_id": job_id, "stage": job.stage, "elapsed_seconds": round(time.monotonic() - started, 2), "files_discovered": job.files_discovered or len(rows), "files_processed": job.files_processed, "files_skipped": job.files_skipped, "imports": dependency_total, "worker_id": _worker_identity()})
    except AnalysisCancelled:
        db.rollback()
        logger.info("Analysis worker cancelled job=%s", job_id)
        _set_terminal(db, job_id, "cancelled", "Analysis cancelled by user")
    except Exception as exc:
        db.rollback()
        logger.exception("Analysis worker failed", extra={"job_id": job_id, "stage": "Analysis failed", "worker_id": _worker_identity()})
        try:
            _set_terminal(db, job_id, "failed", "Analysis failed", f"{type(exc).__name__}: {exc}")
        except Exception:
            db.rollback()
            logger.exception("Could not persist failure state for job=%s", job_id)
        raise
    finally:
        db.close()
        logger.info("Analysis worker stopped job=%s elapsed=%.2fs", job_id, time.monotonic() - started)
