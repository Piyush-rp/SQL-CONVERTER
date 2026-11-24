"""The core NL -> SQL endpoint, plus query history."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import LLMProvider
from app.core.exceptions import ValidationAppError
from app.core.responses import APIResponse
from app.database.session import get_db
from app.dependencies import enforce_rate_limit, get_current_user
from app.llm.llm_config import LLMConfig
from app.models.user import User
from app.schemas import AskRequest, AskResponse, QueryHistoryOut
from app.database.repository import QueryHistoryRepository
from app.services.connection_service import ConnectionService
from app.services.query_service import QueryService
from app.services.session_service import SessionService
from app.core.logger import log

router = APIRouter(tags=["Query"])


@router.post("/ask", response_model=APIResponse[AskResponse], dependencies=[Depends(enforce_rate_limit)])
def ask(payload: AskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    connection = ConnectionService(db).get_owned(payload.connection_id, user.id)

    llm_config = None
    if payload.llm_provider:
        try:
            llm_config = LLMConfig(provider=LLMProvider(payload.llm_provider))
        except ValueError:
            raise ValidationAppError(
                f"Unsupported llm_provider '{payload.llm_provider}' - the only provider is 'groq'."
            )

    result = QueryService(db).ask(
        user_id=user.id, connection=connection, question=payload.question, llm_config=llm_config,
        session_id=payload.session_id,
    )

    response = AskResponse(
        status=result.status,
        question=result.question,
        sql=result.sql,
        explanation=result.explanation,
        execution=result.execution,
        chart_spec=result.chart_spec,
        optimization_suggestions=[
            {"severity": s.severity, "message": s.message} for s in result.optimization_suggestions
        ],
        retry_count=result.retry_count,
        error_message=result.error_message,
        session_id=result.session_id,
    )

    # Save the turn to the user's chat history (the session panel). The saved
    # session's id is returned so the client keeps adding to the same session.
    try:
        saved = SessionService(db).record_turn(
            owner_id=user.id,
            session_id=result.session_id,
            connection=connection,
            question=payload.question,
            response=response.model_dump(mode="json"),
        )
        response.session_id = saved.id
    except Exception as exc:  # history is a convenience - never fail the answer over it
        db.rollback()
        log.warning(f"Could not save chat history: {exc}")

    return APIResponse.ok(response)


@router.get("/history", response_model=APIResponse[List[QueryHistoryOut]])
def get_history(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entries = QueryHistoryRepository(db).list_for_user(user.id, limit=limit, offset=offset)
    return APIResponse.ok([QueryHistoryOut.model_validate(e) for e in entries])
