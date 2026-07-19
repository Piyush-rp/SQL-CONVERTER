"""Classifies parsed SQL into read/write/ddl/admin/unknown using sqlglot's AST,
rather than string matching, so keywords inside string literals or
identifiers ("update_count" the column) don't cause false positives."""
from __future__ import annotations

from enum import Enum
from typing import Optional

import sqlglot
from sqlglot import expressions as exp

from app.validators.dangerous_keywords import (
    ADMIN_STATEMENT_TYPES,
    DDL_STATEMENT_TYPES,
    WRITE_STATEMENT_TYPES,
)


class QueryKind(str, Enum):
    READ = "read"
    WRITE = "write"
    DDL = "ddl"
    ADMIN = "admin"
    UNKNOWN = "unknown"


_EXP_TO_KEYWORD = {
    exp.Select: "select",
    exp.Insert: "insert",
    exp.Update: "update",
    exp.Delete: "delete",
    exp.Merge: "merge",
    exp.Create: "create",
    exp.Drop: "drop",
    exp.Alter: "alter",
}


class QueryClassifier:
    @staticmethod
    def classify(sql: str, dialect: Optional[str] = None) -> QueryKind:
        try:
            parsed = sqlglot.parse_one(sql, read=dialect)
        except Exception:
            return QueryKind.UNKNOWN

        # UNION/INTERSECT/EXCEPT combine two-or-more SELECTs into one
        # sqlglot.expressions.SetOperation node rather than an exp.Select -
        # still exactly one read-only statement, so it must classify as
        # READ rather than falling through to UNKNOWN (which would reject
        # a common, harmless reporting pattern as if it were dangerous).
        if isinstance(parsed, exp.SetOperation):
            return QueryKind.READ

        for exp_type, keyword in _EXP_TO_KEYWORD.items():
            if isinstance(parsed, exp_type):
                if keyword in WRITE_STATEMENT_TYPES:
                    return QueryKind.WRITE
                if keyword in DDL_STATEMENT_TYPES:
                    return QueryKind.DDL
                if keyword == "select":
                    return QueryKind.READ

        sql_lower = sql.strip().lower()
        for admin_kw in ADMIN_STATEMENT_TYPES:
            if sql_lower.startswith(admin_kw):
                return QueryKind.ADMIN

        return QueryKind.UNKNOWN
