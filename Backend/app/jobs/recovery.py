"""Recover only RQ-started jobs whose owning worker is no longer alive.

Run periodically with: python -m app.jobs.recovery
"""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from redis import Redis
from rq import Queue
from sqlalchemy import select

from app.core.config import settings
from app.db.models import AnalysisJob, Repository, RepositoryImportPayload
from app.db.session import SessionLocal
from app.jobs.queue import enqueue_analysis, enqueue_import, live_analysis_workers

logger = logging.getLogger(__name__)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def should_recover(job_id: str, status: str, started_at: datetime | None, active_job_ids: set[str], now: datetime, stale_after_seconds: int) -> bool:
    if status != "running" or started_at is None or job_id in active_job_ids:
        return False
    return (now - _utc(started_at)).total_seconds() >= stale_after_seconds


def recover_stale_jobs() -> dict[str, int]:
    """Repair jobs abandoned by a dead worker and fail queue jobs with no worker."""
    connection = Redis.from_url(settings.redis_url)
    queue_name = "codeatlas-analysis"
    queue = Queue(queue_name, connection=connection)
    now = datetime.now(timezone.utc)
    workers = live_analysis_workers(connection, now)
    active_job_ids = {worker.get_current_job_id() for worker in workers if worker.get_current_job_id()}
    recovered = 0
    skipped = 0
    failed = 0
    db = SessionLocal()
    try:
        stale_before = now.timestamp() - settings.analysis_stale_job_seconds
        candidates = db.scalars(select(AnalysisJob).where(AnalysisJob.status.in_(["queued", "running"]))).all()
        for job in candidates:
            timestamp = job.started_at if job.status == "running" else job.created_at
            if timestamp is None or _utc(timestamp).timestamp() > stale_before or job.id in active_job_ids:
                skipped += 1
                continue
            age = (now - _utc(timestamp)).total_seconds()
            repository = db.get(Repository, job.repository_id)
            if repository is None:
                job.status = "failed"
                job.stage = "Repository was removed"
                job.error_message = "The repository was removed while its worker was unavailable."
                job.finished_at = now
                db.commit()
                continue

            queue_job = queue.fetch_job(job.id)
            if job.status == "queued" and queue_job is not None:
                if workers:
                    skipped += 1
                    continue
                job.status = repository.status = "failed"
                job.stage = "No analysis worker available"
                job.error_message = "This job remained queued without a live analysis worker. Start the CodeAtlas worker, then retry the import."
                job.finished_at = now
                db.commit()
                failed += 1
                logger.error("Failed abandoned queued job=%s age_seconds=%s", job.id, int(age))
                continue
            if not workers:
                job.status = repository.status = "failed"
                job.stage = "Analysis worker unavailable after interruption"
                job.error_message = "The worker stopped during this analysis and no worker is available to retry it. Start the worker, then retry the import."
                job.finished_at = now
                db.commit()
                failed += 1
                logger.error("Failed stale job without worker job=%s age_seconds=%s", job.id, int(age))
                continue

            # Commit a state transition before enqueueing; process_analysis also
            # refuses duplicate executions while this database job is running.
            job.status = repository.status = "queued"
            job.stage = "Recovered after worker loss; waiting for a worker"
            job.error_message = None
            job.finished_at = None
            db.commit()
            try:
                execution_id = f"{job.id}-recovery-{uuid4().hex[:12]}"
                has_pending_import = repository.source_type == "github" and job.progress < 40 or db.get(RepositoryImportPayload, repository.id) is not None
                if has_pending_import:
                    enqueue_import(job.id, execution_id=execution_id)
                else:
                    enqueue_analysis(job.id, execution_id=execution_id)
                recovered += 1
                logger.warning("Requeued stale analysis job=%s age_seconds=%s", job.id, int(age))
            except Exception as exc:
                db.rollback()
                job = db.get(AnalysisJob, job_id)
                repository = db.get(Repository, job.repository_id) if job else None
                if job:
                    job.status = "failed"
                    job.stage = "Recovery enqueue failed"
                    job.error_message = f"{type(exc).__name__}: {exc}"[:2000]
                    job.finished_at = datetime.now(timezone.utc)
                if repository:
                    repository.status = "failed"
                db.commit()
                logger.exception("Could not requeue stale analysis job=%s", job_id)
        return {"recovered": recovered, "skipped": skipped, "failed": failed}
    finally:
        db.close()
        connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("Stale job recovery result: %s", recover_stale_jobs())
