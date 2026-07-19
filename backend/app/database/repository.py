"""
Repository layer: thin CRUD wrappers around SQLAlchemy for Copilot's own
metadata models (users, connections, history). Keeps API routers free of
raw ORM query construction and gives one place to add e.g. soft-deletes
or row-level authorization later.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connection import DatabaseConnection
from app.models.query_history import QueryHistory
from app.models.user import User
from app.utils.pagination import PageParams


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


class ConnectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: str) -> List[DatabaseConnection]:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.owner_id == user_id, DatabaseConnection.is_active.is_(True)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get(self, connection_id: str, user_id: str) -> Optional[DatabaseConnection]:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id, DatabaseConnection.owner_id == user_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, connection: DatabaseConnection) -> DatabaseConnection:
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def soft_delete(self, connection: DatabaseConnection) -> None:
        connection.is_active = False
        self.db.commit()


class QueryHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, entry: QueryHistory) -> QueryHistory:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_for_user(self, user_id: str, *, limit: int = 50, offset: int = 0) -> List[QueryHistory]:
        page = PageParams.clamp(limit, offset, max_limit=200)
        stmt = (
            select(QueryHistory)
            .where(QueryHistory.user_id == user_id)
            .order_by(QueryHistory.created_at.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_all_for_audit(self, *, limit: int = 1000, offset: int = 0) -> List[tuple]:
        """Admin-only: every query across every user, joined with the
        user's email and connection name - the shape an audit/compliance
        export actually needs. Returns raw (QueryHistory, email, conn_name)
        tuples rather than ORM objects with lazy-loaded relationships, so
        one query does the whole join instead of N+1 lookups."""
        page = PageParams.clamp(limit, offset, max_limit=50000)
        stmt = (
            select(QueryHistory, User.email, DatabaseConnection.name)
            .join(User, QueryHistory.user_id == User.id)
            .join(DatabaseConnection, QueryHistory.connection_id == DatabaseConnection.id)
            .order_by(QueryHistory.created_at.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
        return list(self.db.execute(stmt).all())
