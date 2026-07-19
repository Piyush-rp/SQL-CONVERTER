"""
Bounded self-correction: decides whether a failed validation should route
back to the SQL-generator agent (with the error fed back into the prompt)
or give up. This is what makes the pipeline resilient to an LLM's first
SQL attempt having a typo'd column name or a dialect quirk - a second
attempt with the exact error message fixes the large majority of these.
"""
from __future__ import annotations

from app.agents.state import WorkflowState


class RetryAgent:
    @staticmethod
    def should_retry_validation(state: WorkflowState) -> bool:
        validation = state.get("validation")
        if validation is None or validation.is_valid:
            return False
        return RetryAgent._retries_remaining(state)

    @staticmethod
    def should_retry_execution(state: WorkflowState) -> bool:
        if state.get("execution") is not None:
            return False
        if state.get("execution_timeout"):
            return False  # timeouts are terminal, not retried
        if not state.get("last_error"):
            return False
        return RetryAgent._retries_remaining(state)

    @staticmethod
    def _retries_remaining(state: WorkflowState) -> bool:
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)
        return retry_count < max_retries

    @staticmethod
    def increment(state: WorkflowState) -> WorkflowState:
        return {**state, "retry_count": state.get("retry_count", 0) + 1}
