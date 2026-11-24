"""Business logic for the NL -> SQL "ask" endpoint: runs the workflow, then
persists a QueryHistory row either way (successes AND failures - failed/
rejected attempts are valuable audit trail and product-analytics signal)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.repository import QueryHistoryRepository
from app.llm.llm_config import LLMConfig
from app.models.connection import DatabaseConnection
from app.models.query_history import QueryHistory, QueryStatus
from app.telemetry.metrics import record_nl2sql_outcome
from app.workflows.workflow_manager import workflow_manager
from app.workflows.workflow_result import WorkflowResult

_STATUS_MAP = {
    "success": QueryStatus.SUCCESS,
    "failed": QueryStatus.FAILED,
    "rejected": QueryStatus.REJECTED,
    "clarification_needed": QueryStatus.FAILED,
    "wrong_database": QueryStatus.FAILED,
}


class QueryService:
    def __init__(self, db: Session):
        self.db = db
        self.history = QueryHistoryRepository(db)

    def ask(
        self,
        *,
        user_id: str,
        connection: DatabaseConnection,
        question: str,
        llm_config: LLMConfig | None = None,
        session_id: str | None = None,
    ) -> WorkflowResult:
        result = workflow_manager.run(
            question=question, connection=connection, llm_config=llm_config, session_id=session_id
        )

        entry = QueryHistory(
            user_id=user_id,
            connection_id=connection.id,
            question=question,
            generated_sql=result.sql or "",
            status=_STATUS_MAP.get(result.status, QueryStatus.FAILED),
            error_message=result.error_message,
            row_count=result.execution["row_count"] if result.execution else 0,
            execution_time_ms=result.execution["execution_time_ms"] if result.execution else 0,
            retry_count=result.retry_count,
            explanation=result.explanation,
        )
        self.history.create(entry)
        record_nl2sql_outcome(result.status, result.retry_count)

        return result
