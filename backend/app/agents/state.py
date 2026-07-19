"""
Shared state threaded through the LangGraph pipeline. Using a TypedDict (not
a class with methods) is the LangGraph convention - each node returns a
partial dict that gets merged into this state by the graph runtime.
"""
from __future__ import annotations

from typing import Any, List, Optional, TypedDict

from app.database.introspector import DatabaseSchema
from app.llm.llm_config import LLMConfig
from app.validators.sql_cost_estimator import CostEstimate
from app.validators.sql_optimizer import OptimizationSuggestion
from app.validators.validation_result import ValidationResult


class ExecutionResult(TypedDict, total=False):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: int
    truncated: bool


class ChartSpec(TypedDict, total=False):
    chart_type: str  # "bar" | "line" | "pie" | "table" | "none"
    x_key: Optional[str]
    y_keys: List[str]
    title: str
    reason: str


class WorkflowState(TypedDict, total=False):
    # --- inputs ---
    question: str
    connection_id: str
    engine_name: str
    allow_write: bool
    llm_config: LLMConfig
    max_retries: int
    session_id: str

    # --- conversation memory (app.memory) ---
    conversation_turns: list  # List[ConversationTurn], most-recent-last

    # --- schema stage ---
    full_schema: DatabaseSchema
    schema_text: str

    # --- generation stage ---
    sql: Optional[str]
    cannot_answer_reason: Optional[str]
    raw_llm_response: str

    # --- validation stage ---
    validation: Optional[ValidationResult]
    retry_count: int

    # Feedback fed back into the next generation attempt - set by whichever
    # stage most recently failed (validator OR execution), so retries work
    # uniformly for "invalid SQL" and "valid SQL that failed against real
    # data" (e.g. a hallucinated column name that only surfaces at runtime).
    last_error: Optional[str]
    execution_timeout: bool

    # --- cost / optimization ---
    cost_estimate: Optional[CostEstimate]
    optimization_suggestions: List[OptimizationSuggestion]

    # --- execution ---
    execution: Optional[ExecutionResult]

    # --- explanation / visualization ---
    explanation: str
    chart_spec: Optional[ChartSpec]

    # --- bookkeeping ---
    status: str  # "success" | "failed" | "rejected" | "clarification_needed"
    errors: List[str]
