"""
Picks a chart type and axis mapping from the shape of the result set - no
LLM call needed. This runs entirely on column count/types/cardinality
heuristics so it's instant and deterministic; the frontend's ChartRenderer
consumes `chart_spec` directly to pick a recharts component.
"""
from __future__ import annotations

import re
from numbers import Number
from typing import Any, List, Optional

from app.agents.state import ChartSpec, WorkflowState

_DATE_NAME_RE = re.compile(r"(date|month|year|day|time|period|quarter)", re.IGNORECASE)
_MAX_CATEGORICAL_CARDINALITY = 25
_PIE_MAX_SLICES = 8


def _is_numeric(value: Any) -> bool:
    return isinstance(value, Number) and not isinstance(value, bool)


class ChartAgent:
    def run(self, state: WorkflowState) -> WorkflowState:
        execution = state.get("execution")
        if not execution or not execution.get("rows"):
            return {**state, "chart_spec": ChartSpec(chart_type="none", x_key=None, y_keys=[], title="", reason="No rows returned")}

        columns: List[str] = execution["columns"]
        rows = execution["rows"]
        sample = rows[0]

        numeric_cols = [c for c, v in zip(columns, sample) if _is_numeric(v)]
        non_numeric_cols = [c for c in columns if c not in numeric_cols]

        spec = self._pick(columns, numeric_cols, non_numeric_cols, rows)
        return {**state, "chart_spec": spec}

    def _pick(self, columns, numeric_cols, non_numeric_cols, rows) -> ChartSpec:
        if len(columns) == 1:
            return ChartSpec(chart_type="table", x_key=None, y_keys=[], title=columns[0], reason="Single column - a table is clearest")

        # exactly one categorical/date + one-or-more numeric -> bar/line/pie
        if len(non_numeric_cols) == 1 and numeric_cols:
            category_col = non_numeric_cols[0]
            distinct = len({tuple(r) for r in rows})

            if _DATE_NAME_RE.search(category_col):
                return ChartSpec(
                    chart_type="line", x_key=category_col, y_keys=numeric_cols,
                    title=f"{', '.join(numeric_cols)} over {category_col}",
                    reason="Category column looks like a date/time axis",
                )

            if len(numeric_cols) == 1 and distinct <= _PIE_MAX_SLICES:
                return ChartSpec(
                    chart_type="pie", x_key=category_col, y_keys=numeric_cols,
                    title=f"{numeric_cols[0]} by {category_col}",
                    reason=f"Single metric across {distinct} categories fits a pie chart",
                )

            if distinct <= _MAX_CATEGORICAL_CARDINALITY:
                return ChartSpec(
                    chart_type="bar", x_key=category_col, y_keys=numeric_cols,
                    title=f"{', '.join(numeric_cols)} by {category_col}",
                    reason=f"{distinct} categories - a bar chart compares them clearly",
                )

        return ChartSpec(
            chart_type="table", x_key=None, y_keys=numeric_cols, title="",
            reason="Result shape doesn't map cleanly to a simple chart - showing a table",
        )
