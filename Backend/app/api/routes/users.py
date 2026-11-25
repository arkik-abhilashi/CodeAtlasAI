from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import UserResponse
from app.schemas.users import UpdateProfileRequest

router = APIRouter(prefix="/api/users", tags=["account"])


@router.get("/me", response_model=UserResponse)
def get_profile(user: CurrentUser):
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at.isoformat() if user.created_at else "")


@router.patch("/me", response_model=UserResponse)
def update_profile(body: UpdateProfileRequest, user: CurrentUser, db: DbSession):
    user.display_name = body.display_name.strip()
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at.isoformat() if user.created_at else "")
