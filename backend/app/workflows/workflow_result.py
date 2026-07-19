"""Final, API/history-friendly shape returned by WorkflowManager - the
thing the query_service and query history persistence actually consume,
rather than every caller reaching into the raw WorkflowState dict."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from app.agents.state import ChartSpec, ExecutionResult, WorkflowState


@dataclass
class WorkflowResult:
    status: str  # "success" | "failed" | "rejected" | "clarification_needed"
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
            return cls(
                status="clarification_needed",
                question=state["question"],
                error_message=state["cannot_answer_reason"],
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
