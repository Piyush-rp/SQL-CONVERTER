"""
Session/engine for Copilot's OWN metadata database (users, saved connections,
query history) - NOT the customer databases users query in natural language.
Those are handled by app.database.connector / connection_manager instead.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a metadata-DB session, always closed after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """For use outside request context (scripts, background jobs)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_metadata_db() -> None:
    """Create metadata tables if they don't exist. Real deployments should use
    Alembic migrations instead - this is a convenience for local/dev/demo."""
    from app.models import Base  # noqa: local import avoids circular import
    Base.metadata.create_all(bind=engine)
