from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Worker

from app.core.config import settings

ANALYSIS_QUEUE_NAME = "codeatlas-analysis"
RQ_HEARTBEAT_EXPIRY_GRACE_SECONDS = 60


def analysis_queue(connection=None) -> Queue:
    connection = connection or Redis.from_url(settings.redis_url)
    return Queue(ANALYSIS_QUEUE_NAME, connection=connection, default_timeout=settings.analysis_job_timeout_seconds)


def heartbeat_is_live(last_heartbeat: datetime | None, max_age_seconds: int, now: datetime | None = None) -> bool:
    if last_heartbeat is None:
        return False
    now = now or datetime.now(timezone.utc)
    heartbeat = last_heartbeat.replace(tzinfo=timezone.utc) if last_heartbeat.tzinfo is None else last_heartbeat.astimezone(timezone.utc)
    age = (now.astimezone(timezone.utc) - heartbeat).total_seconds()
    return 0 <= age <= max_age_seconds


def _ready_workers(connection, now: datetime) -> list[Worker]:
    queue = analysis_queue(connection)
    workers = Worker.all(connection=connection, queue=queue)
    live = []
    for worker in workers:
        queue_names = [item.name for item in worker.queues]
        if ANALYSIS_QUEUE_NAME not in queue_names:
            continue
        state = worker.get_state()
        state = getattr(state, "value", state)
        if state not in {"idle", "busy"}:
            continue
        if not worker.hostname or not isinstance(worker.pid, int) or worker.pid <= 0:
            continue
        # RQ 2.12 writes a heartbeat with an expiry of worker_ttl + 60s.
        # The live Redis key is authoritative while the worker is idle; its
        # last_heartbeat timestamp is not expected to meet an arbitrary 90s SLA.
        ttl = connection.ttl(worker.key)
        if not isinstance(ttl, int) or ttl <= 0:
            continue
        max_age = worker.worker_ttl + RQ_HEARTBEAT_EXPIRY_GRACE_SECONDS
        if heartbeat_is_live(worker.last_heartbeat, max_age, now):
            live.append(worker)
    return live


def worker_status(connection=None, now: datetime | None = None) -> dict:
    """Report healthy workers according to RQ registration and ready state."""
    connection = connection or Redis.from_url(settings.redis_url)
    now = now or datetime.now(timezone.utc)
    try:
        connection.ping()
        workers = _ready_workers(connection, now)
    except RedisError:
        return {"queue": ANALYSIS_QUEUE_NAME, "available": False, "worker_count": 0, "workers": [], "reason": "redis_unavailable"}

    details = []
    for worker in workers:
        state = worker.get_state()
        details.append({
            "name": worker.name,
            "hostname": worker.hostname,
            "pid": worker.pid,
            "state": getattr(state, "value", state),
            "queues": [item.name for item in worker.queues],
            "version": getattr(worker, "version", None),
            "last_heartbeat": worker.last_heartbeat.isoformat() if worker.last_heartbeat else None,
            "registration_ttl_seconds": connection.ttl(worker.key),
        })
    return {
        "queue": ANALYSIS_QUEUE_NAME,
        "available": bool(details),
        "worker_count": len(details),
        "workers": details,
        "reason": None if details else "no_workers",
    }


def live_analysis_workers(connection=None, now: datetime | None = None) -> list[Worker]:
    connection = connection or Redis.from_url(settings.redis_url)
    now = now or datetime.now(timezone.utc)
    try:
        connection.ping()
        return _ready_workers(connection, now)
    except RedisError:
        return []


def enqueue_analysis(job_id: str, execution_id: str | None = None):
    return analysis_queue().enqueue(
        "app.jobs.worker.process_analysis",
        job_id,
        job_id=execution_id or job_id,
        job_timeout=settings.analysis_job_timeout_seconds,
        result_ttl=3600,
        failure_ttl=86400,
    )


def enqueue_import(job_id: str, execution_id: str | None = None):
    connection = Redis.from_url(settings.redis_url)
    status = worker_status(connection)
    if status["reason"] == "redis_unavailable":
        raise RuntimeError("Redis is unavailable. Start Redis and retry the import.")
    if not status["available"]:
        raise RuntimeError("No analysis worker is connected to Redis. Start the CodeAtlas analysis worker and retry.")
    return analysis_queue(connection).enqueue(
        "app.jobs.worker.process_repository_import",
        job_id,
        job_id=execution_id or job_id,
        job_timeout=settings.analysis_job_timeout_seconds,
        result_ttl=3600,
        failure_ttl=86400,
    )
