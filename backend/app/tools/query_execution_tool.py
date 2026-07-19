"""
A real LangChain tool letting the model run small, exploratory read-only
queries mid-reasoning (e.g. "what distinct values are in the status
column?" before writing the final aggregate query) - rather than only
being able to reason about the schema in the abstract.

Security note: this tool enforces the FULL SQLValidator security gate
itself, independently of the outer pipeline's validation step - a
tool-calling model must never be trusted to only call this with safe SQL
just because the system prompt asked it to. Row cap and timeout here are
deliberately much smaller than the main execution path's (settings.
MAX_ROWS_RETURNED / QUERY_TIMEOUT_SECONDS) since this is for a quick
peek, not the final result set.
"""
from __future__ import annotations

from langchain_core.tools import tool
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.connector import DatabaseConnector
from app.validators.sql_validator import SQLValidator

_EXPLORATION_ROW_CAP = 20
_EXPLORATION_TIMEOUT_SECONDS = 5


def make_query_execution_tool(connector: DatabaseConnector, engine_name: str, allow_write: bool = False):
    @tool
    def run_exploratory_query(sql: str) -> str:
        """Run a small, read-only exploratory SQL query against the real
        database and see its results - useful for checking what distinct
        values exist in a column, confirming a join produces the rows you
        expect, or sanity-checking a filter before finalizing your answer.
        Results are capped to a small number of rows since this is for
        exploration, not the final answer."""
        validation = SQLValidator.validate(sql, engine_name=engine_name, allow_write=allow_write)
        if not validation.is_valid:
            return f"Query rejected: {validation.message}"

        try:
            with connector.engine.connect() as conn:
                conn = conn.execution_options(stream_results=False)
                result = conn.execute(text(validation.sql))
                columns = list(result.keys())
                rows = []
                for i, row in enumerate(result):
                    if i >= _EXPLORATION_ROW_CAP:
                        break
                    rows.append(list(row))
        except SQLAlchemyError as exc:
            return f"Query failed: {exc}"

        if not rows:
            return "Query ran successfully but returned no rows."

        lines = [", ".join(columns)]
        for row in rows:
            lines.append(", ".join(str(v) for v in row))
        suffix = f"\n(showing up to {_EXPLORATION_ROW_CAP} rows)" if len(rows) == _EXPLORATION_ROW_CAP else ""
        return "\n".join(lines) + suffix

    return run_exploratory_query
