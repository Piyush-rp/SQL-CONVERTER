"""Runs the generated SQL through the syntax + security gate before it is
ever allowed near a real connection."""
from __future__ import annotations

from app.agents.state import WorkflowState
from app.validators.sql_validator import SQLValidator


class ValidatorAgent:
    def run(self, state: WorkflowState) -> WorkflowState:
        sql = state.get("sql")
        if not sql:
            return state

        result = SQLValidator.validate(
            sql,
            engine_name=state["engine_name"],
            allow_write=state.get("allow_write", False),
        )
        last_error = None if result.is_valid else result.message
        return {**state, "validation": result, "last_error": last_error}
