"""Business logic for registration/login - kept separate from the router so
it's independently unit-testable without spinning up FastAPI."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.database.repository import UserRepository
from app.models.user import User, UserRole
from app.schemas import TokenPair, UserLogin, UserRegister


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def register(self, payload: UserRegister) -> User:
        if self.users.get_by_email(payload.email) is not None:
            raise ConflictError("An account with this email already exists")

        # First registered user becomes admin so a fresh deployment always
        # has one; everyone after that defaults to viewer (least privilege).
        is_first_user = self.db.query(User).count() == 0
        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=UserRole.ADMIN if is_first_user else UserRole.VIEWER,
        )
        return self.users.create(user)

    def login(self, payload: UserLogin) -> TokenPair:
        user = self.users.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password")
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        return TokenPair(
            access_token=create_access_token(user.id, role=user.role.value),
            refresh_token=create_refresh_token(user.id),
        )

    def refresh(self, refresh_token: str) -> TokenPair:
        from app.core.security import decode_token

        payload = decode_token(refresh_token, expected_type="refresh")
        user = self.users.get_by_id(payload["sub"])
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        return TokenPair(
            access_token=create_access_token(user.id, role=user.role.value),
            refresh_token=create_refresh_token(user.id),
        )
