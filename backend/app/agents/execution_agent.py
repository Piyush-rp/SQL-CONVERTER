"""
Executes the validated, read-only SQL against the target database with a
hard row cap and a wall-clock timeout, and shapes the result set for the
API/frontend. This is the only agent that touches customer data - it never
runs unless ValidatorAgent has already returned is_valid=True.
"""
from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.agents.state import ExecutionResult, WorkflowState
from app.core.config import settings
from app.core.exceptions import QueryExecutionError, QueryTimeoutError
from app.database.connection_manager import connection_manager
from app.models.connection import DatabaseConnection

MAX_CELL_CHARS = 2000  # very long text values are cut so responses stay small


def _human_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} bytes"


def _json_safe(value):
    """Makes one result cell safe to send as JSON. Binary columns (files,
    images, compressed blobs) become a short placeholder - raw bytes can't be
    JSON-encoded and would also blow past response size limits. Decimals become
    numbers so charts can plot them; dates become ISO strings."""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
            return value[:MAX_CELL_CHARS] + f"… ({len(value)} characters)"
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return str(value)
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        try:
            text_value = raw.decode("utf-8")
            if text_value.isprintable() or all(c.isprintable() or c in "\r\n\t" for c in text_value):
                return _json_safe(text_value)
        except UnicodeDecodeError:
            pass
        return f"<binary, {_human_size(len(raw))}>"
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else str(value)
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


# Server-side statement timeouts (set via _DIALECT_SESSION_TIMEOUT) surface as
# ordinary driver errors; these fragments identify them.
_DB_TIMEOUT_MARKERS = (
    "maximum statement execution time exceeded",  # MySQL
    "canceling statement due to statement timeout",  # PostgreSQL
    "query timeout",
    "execution timeout expired",  # SQL Server
)

_DIALECT_SESSION_TIMEOUT = {
    "postgresql": "SET statement_timeout = {ms}",
    "mysql": "SET SESSION MAX_EXECUTION_TIME = {ms}",
}


class ExecutionAgent:
    def __init__(self, executor: ThreadPoolExecutor | None = None):
        # A dedicated small pool means one runaway query can't starve the
        # rest of the app's threads while we wait out the timeout below.
        self._executor = executor or ThreadPoolExecutor(max_workers=8, thread_name_prefix="sql-exec")

    def run(self, state: WorkflowState, connection: DatabaseConnection) -> WorkflowState:
        validation = state.get("validation")
        if validation is None or not validation.is_valid:
            return state

        sql = validation.sql
        connector = connection_manager.get_connector(connection)
        timeout_s = settings.QUERY_TIMEOUT_SECONDS

        future = self._executor.submit(self._execute, connector.engine, sql, connector.engine.dialect.name, timeout_s)
        start = time.monotonic()
        try:
            result = future.result(timeout=timeout_s + 1)
        except FutureTimeoutError:
            # Not retried: re-running the same query shape against the same
            # slow data won't get faster. Surfaced as a terminal failure.
            return {
                **state,
                "execution": None,
                "last_error": f"Query exceeded {timeout_s}s timeout",
                "execution_timeout": True,
            }
        except QueryExecutionError as exc:
            # Retryable: often a hallucinated column/table name that passed
            # syntax validation but doesn't exist - feeding the DB error back
            # to the generator fixes this a large fraction of the time.
            return {**state, "execution": None, "last_error": str(exc)}

        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["execution_time_ms"] = elapsed_ms
        return {**state, "execution": result, "last_error": None}

    @staticmethod
    def _execute(engine, sql: str, dialect_name: str, timeout_s: int) -> ExecutionResult:
        max_rows = settings.MAX_ROWS_RETURNED
        try:
            with engine.connect() as conn:
                timeout_stmt = _DIALECT_SESSION_TIMEOUT.get(dialect_name)
                if timeout_stmt:
                    try:
                        conn.exec_driver_sql(timeout_stmt.format(ms=timeout_s * 1000))
                    except SQLAlchemyError:
                        pass  # best-effort - lack of permission to set this shouldn't block the query

                cursor_result = conn.execute(text(sql))
                columns = list(cursor_result.keys())
                rows = []
                truncated = False
                for i, row in enumerate(cursor_result):
                    if i >= max_rows:
                        truncated = True
                        break
                    rows.append([_json_safe(v) for v in row])

                return ExecutionResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                )
        except SQLAlchemyError as exc:
            detail = str(getattr(exc, "orig", None) or exc).lower()
            if any(s in detail for s in _DB_TIMEOUT_MARKERS):
                raise QueryTimeoutError(
                    f"The query took longer than {timeout_s} seconds and the database stopped it. "
                    "This table is probably very large - try a narrower question (add a filter, "
                    "a date range, or ask for fewer rows)."
                ) from exc
            raise QueryExecutionError(f"Query execution failed: {exc}") from exc
