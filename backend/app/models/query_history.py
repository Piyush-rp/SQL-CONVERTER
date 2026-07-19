from __future__ import annotations

from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QueryStatus(str, PyEnum):
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"  # blocked by the security validator


class QueryHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "query_history"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey("database_connections.id"), nullable=False, index=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[QueryStatus] = mapped_column(Enum(QueryStatus), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="queries")
    connection = relationship("DatabaseConnection", back_populates="queries")
