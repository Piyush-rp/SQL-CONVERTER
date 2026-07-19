"""
A real LangChain tool exposing SQLValidator so a tool-calling model can
self-check a candidate SQL statement mid-reasoning, before committing to
a final answer - rather than only finding out it's invalid after the
whole response is parsed (the original generate-then-validate-then-retry
loop in app.workflows.sql_workflow, which still runs as the outer safety
net regardless of whether the model used this tool).
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.validators.sql_validator import SQLValidator


def make_sql_validation_tool(engine_name: str, allow_write: bool = False):
    @tool
    def validate_sql(sql: str) -> str:
        """Check whether a candidate SQL statement is syntactically valid
        and passes the security policy (single statement, read-only unless
        writes are explicitly enabled, no admin/DDL statements). Use this
        to check your SQL before giving a final answer, especially after
        writing a complex query with joins or subqueries."""
        result = SQLValidator.validate(sql, engine_name=engine_name, allow_write=allow_write)
        if result.is_valid:
            warning_text = f" Warnings: {'; '.join(result.warnings)}" if result.warnings else ""
            return f"Valid.{warning_text}"
        return f"Invalid: {result.message}"

    return validate_sql
