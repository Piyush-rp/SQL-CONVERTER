"""
Executes the validated, read-only SQL against the target database with a
hard row cap and a wall-clock timeout, and shapes the result set for the
API/frontend. This is the only agent that touches customer data - it never
runs unless ValidatorAgent has already returned is_valid=True.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.agents.state import ExecutionResult, WorkflowState
from app.core.config import settings
from app.core.exceptions import QueryExecutionError, QueryTimeoutError
from app.database.connection_manager import connection_manager
from app.models.connection import DatabaseConnection

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
                    rows.append(list(row))

                return ExecutionResult(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                )
        except SQLAlchemyError as exc:
            raise QueryExecutionError(f"Query execution failed: {exc}") from exc
