"""
Best-effort query cost estimation via each engine's native EXPLAIN, run
against a real connection BEFORE the query is executed for real. This lets
the API warn ("this will scan ~4.2M rows") and gives the frontend a
cost badge, without ever executing write-shaped plans.

Every dialect surfaces cost differently, so this normalizes to a single
`estimated_rows` figure where the engine provides one, and always returns
the raw plan text for display even when it doesn't.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


@dataclass
class CostEstimate:
    supported: bool
    estimated_rows: Optional[int]
    raw_plan: str
    warning: Optional[str] = None


_EXPLAIN_PREFIX = {
    "postgresql": "EXPLAIN (FORMAT TEXT) ",
    "mysql": "EXPLAIN ",
    "sqlite": "EXPLAIN QUERY PLAN ",
    "mssql": None,  # requires SET SHOWPLAN_ALL ON in a separate batch; see below
}

_PG_ROWS_RE = re.compile(r"rows=(\d+)")
_MYSQL_ROWS_KEY = "rows"


class SQLCostEstimator:
    @staticmethod
    def estimate(engine: Engine, sql: str) -> CostEstimate:
        dialect = engine.dialect.name

        if dialect == "mssql":
            return SQLCostEstimator._estimate_mssql(engine, sql)

        prefix = _EXPLAIN_PREFIX.get(dialect)
        if prefix is None:
            return CostEstimate(supported=False, estimated_rows=None, raw_plan="", warning="Cost estimation not supported for this engine")

        try:
            with engine.connect() as conn:
                result = conn.exec_driver_sql(prefix + sql)
                # Capture both the raw tuples (for display) and the column
                # names (for MySQL's dict-shaped EXPLAIN row) in one pass -
                # calling .mappings() after .fetchall() would hit an already-
                # exhausted cursor and silently return nothing.
                columns = list(result.keys())
                rows = result.fetchall()
        except SQLAlchemyError as exc:
            return CostEstimate(supported=False, estimated_rows=None, raw_plan="", warning=f"Could not EXPLAIN query: {exc}")

        plan_text = "\n".join(str(tuple(r)) for r in rows)
        estimated_rows = None

        if dialect == "postgresql":
            match = _PG_ROWS_RE.search(plan_text)
            if match:
                estimated_rows = int(match.group(1))
        elif dialect == "mysql" and rows and _MYSQL_ROWS_KEY in columns:
            rows_index = columns.index(_MYSQL_ROWS_KEY)
            raw_value = rows[0][rows_index]
            if raw_value is not None:
                estimated_rows = int(raw_value)

        return CostEstimate(supported=True, estimated_rows=estimated_rows, raw_plan=plan_text)

    @staticmethod
    def _estimate_mssql(engine: Engine, sql: str) -> CostEstimate:
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SET SHOWPLAN_ALL ON")
                result = conn.exec_driver_sql(sql)
                rows = result.fetchall()
                conn.exec_driver_sql("SET SHOWPLAN_ALL OFF")
            plan_text = "\n".join(str(tuple(r)) for r in rows)
            return CostEstimate(supported=True, estimated_rows=None, raw_plan=plan_text)
        except SQLAlchemyError as exc:
            return CostEstimate(supported=False, estimated_rows=None, raw_plan="", warning=f"Could not SHOWPLAN query: {exc}")
