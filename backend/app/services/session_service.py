"""Saving and managing chat sessions (the history panel)."""
from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.chat_session import ChatMessage, ChatSession
from app.models.connection import DatabaseConnection

# Rows kept per saved answer. Results can hold up to MAX_ROWS_RETURNED rows;
# history only needs enough to show the table/chart again.
MAX_SAVED_ROWS = 200
TITLE_LENGTH = 80


def _title_from(question: str) -> str:
    text = " ".join(question.split())
    return text if len(text) <= TITLE_LENGTH else text[: TITLE_LENGTH - 1].rstrip() + "…"


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    # --- recording -------------------------------------------------------------

    def record_turn(
        self,
        *,
        owner_id: str,
        session_id: Optional[str],
        connection: DatabaseConnection,
        question: str,
        response: dict,
    ) -> ChatSession:
        """Appends one question+answer to the session, creating the session on
        its first question. A session id belonging to another user is never
        reused - a fresh session is started instead."""
        session = self.db.get(ChatSession, session_id) if session_id else None
        if session is not None and session.owner_id != owner_id:
            session = None
        if session is None:
            session = ChatSession(owner_id=owner_id, title=_title_from(question))
            if session_id and self.db.get(ChatSession, session_id) is None:
                session.id = session_id  # keep the id the conversation memory uses
            self.db.add(session)
            self.db.flush()

        session.connection_id = connection.id
        session.connection_name = connection.name

        saved = dict(response)
        execution = saved.get("execution")
        if isinstance(execution, dict) and isinstance(execution.get("rows"), list):
            rows = execution["rows"]
            if len(rows) > MAX_SAVED_ROWS:
                saved["execution"] = {**execution, "rows": rows[:MAX_SAVED_ROWS], "truncated": True}

        position = self.db.scalar(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session.id)
        ) or 0
        self.db.add(
            ChatMessage(
                session_id=session.id,
                position=position,
                connection_name=connection.name,
                question=question,
                response_json=json.dumps(saved, default=str),
            )
        )
        session.updated_at = func.now()
        self.db.commit()
        self.db.refresh(session)
        return session

    # --- reading / managing -------------------------------------------------------

    def list_for_user(self, owner_id: str, limit: int = 100) -> List[dict]:
        counts = (
            select(ChatMessage.session_id, func.count().label("n"))
            .group_by(ChatMessage.session_id)
            .subquery()
        )
        rows = self.db.execute(
            select(ChatSession, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.session_id == ChatSession.id)
            .where(ChatSession.owner_id == owner_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        ).all()
        return [self._summary(s, n) for s, n in rows]

    def get_owned(self, session_id: str, owner_id: str) -> ChatSession:
        session = self.db.get(ChatSession, session_id)
        if session is None or session.owner_id != owner_id:
            raise NotFoundError("Chat session not found")
        return session

    def detail(self, session: ChatSession) -> dict:
        return {
            **self._summary(session, len(session.messages)),
            "messages": [
                {
                    "question": m.question,
                    "connection_name": m.connection_name,
                    "response": json.loads(m.response_json or "{}"),
                    "created_at": m.created_at,
                }
                for m in session.messages
            ],
        }

    def update(self, session: ChatSession, *, bookmarked: Optional[bool], title: Optional[str]) -> dict:
        if bookmarked is not None:
            session.bookmarked = bookmarked
        if title is not None and title.strip():
            session.title = _title_from(title)
        self.db.commit()
        self.db.refresh(session)
        return self._summary(session, len(session.messages))

    def delete(self, session: ChatSession) -> None:
        self.db.delete(session)
        self.db.commit()

    @staticmethod
    def _summary(session: ChatSession, message_count: int) -> dict:
        return {
            "id": session.id,
            "title": session.title,
            "bookmarked": session.bookmarked,
            "connection_id": session.connection_id,
            "connection_name": session.connection_name,
            "message_count": int(message_count),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }
