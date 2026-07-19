from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DBEngine(str, PyEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MSSQL = "mssql"
    SQLITE = "sqlite"


class DatabaseConnection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A saved connection to a *target* database that the user wants to query
    in natural language. Credentials are encrypted at rest (see
    app.core.security / Fernet in connection_manager) - never stored plaintext.
    """
    __tablename__ = "database_connections"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    engine: Mapped[DBEngine] = mapped_column(Enum(DBEngine), nullable=False)

    host: Mapped[str] = mapped_column(String(255), default="")
    port: Mapped[int] = mapped_column(Integer, default=0)
    database: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str] = mapped_column(String(255), default="")
    encrypted_password: Mapped[str] = mapped_column(String(1024), default="")
    file_path: Mapped[str] = mapped_column(String(1024), default="")  # for sqlite
    extra_params: Mapped[str] = mapped_column(String(1024), default="")  # e.g. sslmode=require

    read_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    owner = relationship("User", back_populates="connections")
    queries = relationship("QueryHistory", back_populates="connection", cascade="all, delete-orphan")
