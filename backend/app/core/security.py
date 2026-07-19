"""
Password hashing and JWT issuance/verification.

Used by the auth router and by `dependencies.get_current_user` to protect
every non-public endpoint.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional

from jose import JWTError, jwt

import bcrypt

from app.core.config import settings
from app.core.exceptions import AuthenticationError

TokenType = Literal["access", "refresh"]

# bcrypt only uses the first 72 bytes of the input - anything past that is
# silently ignored by the algorithm itself, but newer bcrypt releases raise
# instead of truncating, so we truncate explicitly and deterministically.
_BCRYPT_MAX_BYTES = 72


def _prepare_password(plain_password: str) -> bytes:
    return plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain_password: str) -> str:
    hashed = bcrypt.hashpw(_prepare_password(plain_password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare_password(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # malformed/legacy hash - never let this crash the login endpoint
        return False


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, *, role: str = "user") -> str:
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={"role": role},
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(user_id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str, *, expected_type: Optional[TokenType] = None) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    if expected_type and payload.get("type") != expected_type:
        raise AuthenticationError(f"Expected a {expected_type} token")
    return payload
