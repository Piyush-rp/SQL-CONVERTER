"""Chat sessions: one conversation (a series of questions and the answers the
app gave) that the user can reopen later from the history panel and bookmark."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChatSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "chat_sessions"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # The connection used most recently in this session. A copy of its name is
    # kept so the history still reads well if the connection is later deleted.
    connection_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    connection_name: Mapped[str] = mapped_column(String(255), default="")
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.position",
    )


class ChatMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "chat_messages"

    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    connection_name: Mapped[str] = mapped_column(String(255), default="")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # The full /ask response (SQL, rows, chart, explanation...) as JSON, so a
    # reopened session renders exactly what the user saw.
    response_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    session: Mapped[ChatSession] = relationship(back_populates="messages")
