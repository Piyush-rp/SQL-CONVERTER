from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    bookmarked: bool
    connection_id: Optional[str] = None
    connection_name: str = ""
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionMessage(BaseModel):
    question: str
    connection_name: str = ""
    response: Any
    created_at: datetime


class ChatSessionDetail(ChatSessionSummary):
    messages: List[ChatSessionMessage] = []


class ChatSessionUpdate(BaseModel):
    bookmarked: Optional[bool] = None
    title: Optional[str] = None
