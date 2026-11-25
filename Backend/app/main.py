import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import auth, repositories, users, workers
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.models import AnalysisJob, AnalysisResult, Dependency, Repository, RepositoryFile, RepositoryImportPayload, RevokedToken, SavedGraph, User  # noqa: F401
from app.db.session import engine

configure_logging()
logger = logging.getLogger(__name__)


async def _recovery_loop():
    from app.jobs.recovery import recover_stale_jobs
    while True:
        try:
            result = await asyncio.to_thread(recover_stale_jobs)
            if result.get("recovered") or result.get("failed"):
                logger.warning("Analysis recovery sweep completed: %s", result)
        except Exception:
            logger.exception("Analysis recovery sweep failed")
        await asyncio.sleep(settings.analysis_recovery_interval_seconds)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = None
    if not settings.database_url.startswith("sqlite"):
        task = asyncio.create_task(_recovery_loop())
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.app_name, version="2.0.0", description="Persistent, authenticated source repository analysis API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(repositories.router)
app.include_router(workers.router)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=503, content={"detail": "Database is temporarily unavailable"})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred"})


@app.get("/api/health", tags=["system"])
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
