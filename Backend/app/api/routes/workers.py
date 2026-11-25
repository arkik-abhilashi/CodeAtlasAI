from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.jobs.queue import worker_status
from app.schemas.repositories import WorkerStatusResponse

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.get("/status", response_model=WorkerStatusResponse)
def get_worker_status(_user: CurrentUser):
    """Expose queue availability based on RQ's live worker registrations."""
    return worker_status()
