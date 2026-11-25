from datetime import datetime, timedelta, timezone

from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Worker

from app.jobs.queue import ANALYSIS_QUEUE_NAME, worker_status


class FakeConnection:
    def __init__(self, ttls=None, fails=False):
        self.ttls = ttls or {}
        self.fails = fails

    def ping(self):
        if self.fails:
            raise RedisConnectionError("Redis unavailable")
        return True

    def ttl(self, key):
        return self.ttls.get(key, -2)


class FakeQueue:
    def __init__(self, name):
        self.name = name


class FakeWorker:
    def __init__(self, *, name="worker-1", state="idle", queue=ANALYSIS_QUEUE_NAME, heartbeat_age=300, ttl=420, pid=1234, hostname="test-host"):
        now = datetime.now(timezone.utc)
        self.name = name
        self.key = f"rq:worker:{name}"
        self.hostname = hostname
        self.pid = pid
        self.queues = [FakeQueue(queue)]
        self.state = state
        self.last_heartbeat = now - timedelta(seconds=heartbeat_age)
        self.worker_ttl = ttl
        self.version = "2.12.0"

    def get_state(self):
        return self.state


def install_workers(monkeypatch, workers):
    monkeypatch.setattr(Worker, "all", classmethod(lambda cls, connection=None, queue=None: workers))


def test_healthy_idle_worker_is_available_despite_long_idle_heartbeat(monkeypatch):
    worker = FakeWorker(state="idle", heartbeat_age=300)
    install_workers(monkeypatch, [worker])
    status = worker_status(FakeConnection({worker.key: 120}))
    assert status["available"] is True
    assert status["workers"][0]["state"] == "idle"
    assert status["workers"][0]["queues"] == [ANALYSIS_QUEUE_NAME]


def test_healthy_busy_worker_is_available(monkeypatch):
    worker = FakeWorker(state="busy", heartbeat_age=20)
    install_workers(monkeypatch, [worker])
    status = worker_status(FakeConnection({worker.key: 400}))
    assert status["available"] is True
    assert status["workers"][0]["state"] == "busy"


def test_no_registered_workers_is_unavailable(monkeypatch):
    install_workers(monkeypatch, [])
    status = worker_status(FakeConnection())
    assert status["available"] is False
    assert status["reason"] == "no_workers"


def test_stale_worker_is_rejected_even_if_registry_ttl_remains(monkeypatch):
    worker = FakeWorker(state="idle", heartbeat_age=481)
    install_workers(monkeypatch, [worker])
    status = worker_status(FakeConnection({worker.key: 20}))
    assert status["available"] is False


def test_worker_registered_to_another_queue_is_rejected(monkeypatch):
    worker = FakeWorker(queue="default")
    install_workers(monkeypatch, [worker])
    status = worker_status(FakeConnection({worker.key: 300}))
    assert status["available"] is False


def test_redis_connection_failure_is_reported_separately(monkeypatch):
    install_workers(monkeypatch, [])
    status = worker_status(FakeConnection(fails=True))
    assert status["available"] is False
    assert status["reason"] == "redis_unavailable"
