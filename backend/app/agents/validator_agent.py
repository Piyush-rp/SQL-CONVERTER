"""Runs the generated SQL through the syntax + security gate before it is
ever allowed near a real connection."""
from __future__ import annotations

from app.agents.state import WorkflowState
from app.validators.sql_validator import SQLValidator
from app.validators.validation_result import ValidationResult


class ValidatorAgent:
    def run(self, state: WorkflowState) -> WorkflowState:
        sql = state.get("sql")
        if not sql:
            # The model replied without any SQL. Mark it invalid so the
            # workflow retries, telling the model exactly what was wrong.
            result = ValidationResult(
                is_valid=False,
                message="The AI didn't produce a SQL query for this question. Try rephrasing it more specifically.",
                sql="",
                error_code="no_sql",
            )
            return {
                **state,
                "validation": result,
                "last_error": "Your previous reply did not contain a SQL query. Reply with exactly one ```sql "
                "fenced block containing a single SELECT, or a single line starting with CANNOT_ANSWER:.",
            }

        result = SQLValidator.validate(
            sql,
            engine_name=state["engine_name"],
            allow_write=state.get("allow_write", False),
        )
        last_error = None if result.is_valid else result.message
        return {**state, "validation": result, "last_error": last_error}
