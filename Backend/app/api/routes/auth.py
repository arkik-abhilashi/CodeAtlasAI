from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.db.models.revoked_token import RevokedToken
from app.db.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.users import UpdateProfileRequest
from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password
from app.api.deps import bearer

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def token_response(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id), user=UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at.isoformat() if user.created_at else ""))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbSession):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email, password_hash=hash_password(body.password), display_name=body.display_name.strip())
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from exc
    db.refresh(user)
    return token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    if not user.is_active:
        raise HTTPException(403, "This account is disabled")
    return token_response(user)


@router.post("/logout")
def logout(user: CurrentUser, db: DbSession, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    payload = decode_access_token(credentials.credentials) if credentials else None
    if payload and payload.get("jti"):
        expiry = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        db.add(RevokedToken(jti=payload["jti"], user_id=user.id, expires_at=expiry))
        db.commit()
    return {"message": "Signed out"}


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser):
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at.isoformat() if user.created_at else "")


@router.patch("/me", response_model=UserResponse)
def update_me(body: UpdateProfileRequest, user: CurrentUser, db: DbSession):
    user.display_name = body.display_name.strip()
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at.isoformat() if user.created_at else "")
