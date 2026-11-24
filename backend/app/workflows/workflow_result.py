"""Final, API/history-friendly shape returned by WorkflowManager - the
thing the query_service and query history persistence actually consume,
rather than every caller reaching into the raw WorkflowState dict."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from app.agents.state import ChartSpec, ExecutionResult, WorkflowState


def _wrong_database_message(state: WorkflowState, reason: str) -> str:
    """Tells the user the question belongs to a different database: names the
    selected connection, says what it actually contains, and what to do."""
    # The model's own note is not shown: it only sees the few tables picked as
    # relevant to the question, so it can wrongly claim the database "only
    # contains" those. The real table list below comes from the full schema.
    name = state.get("connection_name") or "the selected database"
    schema = state.get("full_schema")
    tables = schema.table_names()[:8] if schema is not None else []
    parts = [f'This question doesn\'t seem to match the selected database "{name}".']
    if tables:
        more = " and more" if schema is not None and len(schema.tables) > len(tables) else ""
        parts.append(f"It contains tables like: {', '.join(tables)}{more}.")
    parts.append("Select the right connection in the sidebar (or type / and its name), then ask again.")
    return " ".join(parts)


@dataclass
class WorkflowResult:
    status: str  # "success" | "failed" | "rejected" | "clarification_needed" | "wrong_database"
    question: str
    sql: Optional[str] = None
    explanation: str = ""
    execution: Optional[ExecutionResult] = None
    chart_spec: Optional[ChartSpec] = None
    optimization_suggestions: List[Any] = field(default_factory=list)
    retry_count: int = 0
    error_message: str = ""
    session_id: str = ""

    @classmethod
    def from_state(cls, state: WorkflowState) -> "WorkflowResult":
        if state.get("cannot_answer_reason"):
            reason = state["cannot_answer_reason"]
            if reason.upper().startswith("WRONG_DATABASE"):
                return cls(
                    status="wrong_database",
                    question=state["question"],
                    error_message=_wrong_database_message(state, reason),
                    retry_count=state.get("retry_count", 0),
                    session_id=state.get("session_id", ""),
                )
            return cls(
                status="clarification_needed",
                question=state["question"],
                error_message=reason,
                retry_count=state.get("retry_count", 0),
                session_id=state.get("session_id", ""),
            )

        validation = state.get("validation")
        if validation is None or not validation.is_valid:
            is_unsafe = validation is not None and validation.error_code == "unsafe_sql"
            status = "rejected" if is_unsafe else "failed"
            return cls(
                status=status,
                question=state["question"],
                sql=state.get("sql"),
                error_message=validation.message if validation is not None else "SQL generation failed",
                retry_count=state.get("retry_count", 0),
                session_id=state.get("session_id", ""),
            )

        # SQL passed validation but execution never produced a result set -
        # it failed (or timed out) and retries, if any, are exhausted.
        if state.get("execution") is None:
            return cls(
                status="failed",
                question=state["question"],
                sql=validation.sql,
                error_message=state.get("last_error") or "Query execution failed",
                retry_count=state.get("retry_count", 0),
                session_id=state.get("session_id", ""),
            )

        return cls(
            status="success",
            question=state["question"],
            sql=validation.sql,
            explanation=state.get("explanation", ""),
            execution=state.get("execution"),
            chart_spec=state.get("chart_spec"),
            optimization_suggestions=state.get("optimization_suggestions", []),
            retry_count=state.get("retry_count", 0),
            session_id=state.get("session_id", ""),
        )
