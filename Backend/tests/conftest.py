import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-entropy-for-tests")

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
import app.jobs.worker as worker
import app.services.repository_service as repository_service


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def get_test_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(worker, "SessionLocal", TestingSession)
    monkeypatch.setattr(repository_service, "enqueue_analysis", lambda job_id: worker.process_analysis(job_id))
    monkeypatch.setattr(repository_service, "enqueue_import", lambda job_id: worker.process_repository_import(job_id))
    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_zip(files: dict[str, str]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for path, content in files.items():
            archive.writestr(f"sample/{path}", content)
    return stream.getvalue()


@pytest.fixture
def register_user(client):
    def register(email="developer@example.com"):
        response = client.post("/api/auth/register", json={"email": email, "password": "safe-password-123", "display_name": "Dev"})
        assert response.status_code == 201, response.text
        return response.json()["access_token"]
    return register
