"""Normalizes LLM-generated SQL before it reaches the validator: strips a
trailing semicolon (sqlglot's single-statement check is stricter without
it), collapses stray whitespace, and injects a server-side row cap using
the right syntax per dialect if the model forgot one."""
from __future__ import annotations

import re

_LIMIT_KEYWORDS = re.compile(r"\b(limit|top\s*\(?\d)\b", re.IGNORECASE)


class SQLPostprocessor:
    @staticmethod
    def clean(sql: str) -> str:
        sql = sql.strip()
        sql = re.sub(r";+\s*$", "", sql)  # drop trailing semicolon(s)
        sql = re.sub(r"[ \t]+\n", "\n", sql)  # trailing whitespace per line
        return sql.strip()

    @staticmethod
    def enforce_row_cap(sql: str, engine_name: str, max_rows: int) -> str:
        if _LIMIT_KEYWORDS.search(sql):
            return sql  # model (or user) already capped rows

        if engine_name == "mssql":
            # SQL Server uses TOP right after SELECT, not a trailing LIMIT.
            return re.sub(r"(?i)^select\b", f"SELECT TOP {max_rows}", sql, count=1)

        return f"{sql}\nLIMIT {max_rows}"
