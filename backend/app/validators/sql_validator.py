"""
Top-level validator combining syntax + security checks. This is the single
entry point agents and API routes call - `SQLValidator.validate(...)`.
"""
from __future__ import annotations

from typing import Optional

import sqlglot
from sqlglot.errors import ParseError

from app.validators.sql_security import SQLSecurity
from app.validators.validation_result import ValidationResult

_DIALECT_MAP = {
    "postgresql": "postgres",
    "mysql": "mysql",
    "mssql": "tsql",
    "sqlite": "sqlite",
}


class SQLValidator:
    @staticmethod
    def validate(sql: str, *, engine_name: str = "postgresql", allow_write: bool = False) -> ValidationResult:
        dialect = _DIALECT_MAP.get(engine_name, None)

        try:
            sqlglot.parse_one(sql, read=dialect)
        except ParseError as e:
            return ValidationResult(False, f"Syntax error: {e}", sql, error_code="syntax_error")
        except Exception as e:  # sqlglot can raise other errors for exotic dialect features
            return ValidationResult(False, f"Could not parse SQL: {e}", sql, error_code="parse_error")

        safe, reason = SQLSecurity.is_safe(sql, allow_write=allow_write, dialect=dialect)
        if not safe:
            return ValidationResult(False, reason, sql, error_code="unsafe_sql")

        warnings = []
        if "select *" in sql.lower():
            warnings.append("SELECT * returns all columns - consider naming columns explicitly")
        if "limit" not in sql.lower() and "top " not in sql.lower():
            warnings.append("No row limit in query - a server-side cap will still be enforced")

        return ValidationResult(True, "SQL is valid", sql, warnings=warnings)
