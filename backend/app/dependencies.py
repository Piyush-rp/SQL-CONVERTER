"""FastAPI dependency-injection helpers: current user, role-based access,
and rate limiting (backed by app.cache - in-process or Redis depending on
config, see docs/scaling.md)."""
from __future__ import annotations

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.cache.rate_limiter import build_rate_limiter
from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_token
from app.database.repository import UserRepository
from app.database.session import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise AuthenticationError("Not authenticated")

    payload = decode_token(token, expected_type="access")
    user = UserRepository(db).get_by_id(payload["sub"])
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


def require_role(*allowed_roles: UserRole):
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise AuthorizationError(f"Requires one of roles: {[r.value for r in allowed_roles]}")
        return user
    return _check


_rate_limiter = build_rate_limiter(settings)


def enforce_rate_limit(user: User = Depends(get_current_user)) -> None:
    _rate_limiter.check(user.id)
