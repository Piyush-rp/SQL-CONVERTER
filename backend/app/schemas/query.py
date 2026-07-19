from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.models.query_history import QueryStatus


class AskRequest(BaseModel):
    connection_id: str
    question: str = Field(min_length=1, max_length=2000)
    llm_provider: Optional[str] = None  # override the deployment default for this request
    session_id: Optional[str] = None    # groups turns for conversation memory - see app.memory


class ExecutionOut(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: int
    truncated: bool


class ChartSpecOut(BaseModel):
    chart_type: str
    x_key: Optional[str] = None
    y_keys: List[str] = []
    title: str = ""
    reason: str = ""


class OptimizationSuggestionOut(BaseModel):
    severity: str
    message: str


class AskResponse(BaseModel):
    status: str
    question: str
    sql: Optional[str] = None
    explanation: str = ""
    execution: Optional[ExecutionOut] = None
    chart_spec: Optional[ChartSpecOut] = None
    optimization_suggestions: List[OptimizationSuggestionOut] = []
    retry_count: int = 0
    error_message: str = ""
    session_id: Optional[str] = None


class QueryHistoryOut(BaseModel):
    id: str
    question: str
    generated_sql: str
    status: QueryStatus
    row_count: int
    execution_time_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogEntryOut(BaseModel):
    id: str
    user_id: str
    user_email: str
    connection_id: str
    connection_name: str
    question: str
    generated_sql: str
    status: QueryStatus
    error_message: str
    row_count: int
    execution_time_ms: int
    retry_count: int
    created_at: datetime
