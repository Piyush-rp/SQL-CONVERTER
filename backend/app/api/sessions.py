"""Chat session history: list, open, bookmark/rename, delete."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse
from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.sessions import ChatSessionDetail, ChatSessionSummary, ChatSessionUpdate
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=APIResponse[List[ChatSessionSummary]])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return APIResponse.ok(SessionService(db).list_for_user(user.id))


@router.get("/{session_id}", response_model=APIResponse[ChatSessionDetail])
def get_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = SessionService(db)
    return APIResponse.ok(service.detail(service.get_owned(session_id, user.id)))


@router.patch("/{session_id}", response_model=APIResponse[ChatSessionSummary])
def update_session(
    session_id: str,
    payload: ChatSessionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = SessionService(db)
    session = service.get_owned(session_id, user.id)
    return APIResponse.ok(service.update(session, bookmarked=payload.bookmarked, title=payload.title))


@router.delete("/{session_id}", response_model=APIResponse[None])
def delete_session(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = SessionService(db)
    service.delete(service.get_owned(session_id, user.id))
    return APIResponse.ok()
