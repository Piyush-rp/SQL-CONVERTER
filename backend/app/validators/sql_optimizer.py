"""
Rule-based SQL optimization advice.

Deliberately rule-based rather than another LLM round-trip: it's instant,
deterministic, free, and covers the mistakes that actually matter for
NL-generated SQL (missing LIMIT, SELECT *, functions on indexed columns
in WHERE, cartesian joins). An LLM explanation of *why* is layered on top
in explanation_agent, but the detection itself doesn't depend on a model call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

import sqlglot
from sqlglot import expressions as exp


@dataclass
class OptimizationSuggestion:
    severity: str  # "info" | "warning"
    message: str


class SQLOptimizer:
    @staticmethod
    def analyze(sql: str, dialect: str = None) -> List[OptimizationSuggestion]:
        suggestions: List[OptimizationSuggestion] = []
        try:
            parsed = sqlglot.parse_one(sql, read=dialect)
        except Exception:
            return suggestions

        if not isinstance(parsed, exp.Select):
            return suggestions

        # SELECT *
        for star in parsed.find_all(exp.Star):
            suggestions.append(
                OptimizationSuggestion("info", "SELECT * fetches every column - naming only the columns you need reduces I/O and network transfer.")
            )
            break

        # Missing LIMIT/TOP on an unfiltered SELECT
        has_limit = parsed.args.get("limit") is not None
        has_where = parsed.args.get("where") is not None
        if not has_limit and not has_where:
            suggestions.append(
                OptimizationSuggestion("warning", "No WHERE clause and no LIMIT - this will scan and return the entire table.")
            )

        # Functions wrapped around a WHERE column (defeats index usage), e.g. WHERE LOWER(email) = ...
        where = parsed.args.get("where")
        if where is not None:
            for func in where.find_all(exp.Func):
                col = func.find(exp.Column)
                if col is not None:
                    suggestions.append(
                        OptimizationSuggestion(
                            "info",
                            f"Applying {func.key.upper()}() to '{col.name}' in WHERE can prevent index use - "
                            f"consider a functional index or filtering on the raw column.",
                        )
                    )
                    break

        # Implicit (comma-join) cartesian joins
        froms = parsed.args.get("from")
        joins = parsed.args.get("joins") or []
        if froms and hasattr(froms.this, "expressions") and len(getattr(froms.this, "expressions", [])) > 1 and not joins:
            suggestions.append(
                OptimizationSuggestion("warning", "Comma-separated tables with no explicit JOIN condition risk a cartesian product.")
            )

        # DISTINCT often masks an unnecessary join fan-out
        if parsed.args.get("distinct") and joins:
            suggestions.append(
                OptimizationSuggestion("info", "DISTINCT combined with JOINs can mask row duplication from a fan-out join - verify the join cardinality is intended.")
            )

        return suggestions
