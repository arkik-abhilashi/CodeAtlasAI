from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.revoked_token import RevokedToken
from app.db.session import get_db
from app.services.auth import decode_access_token

bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: DbSession) -> User:
    if credentials is None:
        raise HTTPException(401, "Sign in to access this resource", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_access_token(credentials.credentials)
    if payload and db.get(RevokedToken, payload.get("jti")) is not None:
        payload = None
    user = db.get(User, payload.get("sub")) if payload else None
    if user is None or not user.is_active:
        raise HTTPException(401, "Your session is invalid or expired", headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
