"""
The security gate every piece of SQL - LLM-generated or user-submitted -
must pass before it is allowed to run against a customer database.

Layered defense:
  1. Must parse as exactly one statement (blocks stacked-query injection).
  2. Statement type must be allowed for this connection (read-only by default).
  3. Regex screen for known dangerous functions/filesystem escape hatches
     that AST classification alone wouldn't catch (e.g. xp_cmdshell calls
     inside an otherwise well-formed SELECT).
"""
from __future__ import annotations

import re
from typing import List, Tuple

import sqlglot

from app.validators.dangerous_keywords import SUSPICIOUS_PATTERNS
from app.validators.query_classifier import QueryClassifier, QueryKind

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in SUSPICIOUS_PATTERNS]


class SQLSecurity:
    @staticmethod
    def is_single_statement(sql: str, dialect: str = None) -> bool:
        try:
            statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
        except Exception:
            return False
        return len(statements) == 1

    @staticmethod
    def scan_suspicious_patterns(sql: str) -> List[str]:
        hits = []
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(sql):
                hits.append(pattern.pattern)
        return hits

    @staticmethod
    def is_safe(sql: str, *, allow_write: bool = False, dialect: str = None) -> Tuple[bool, str]:
        if not sql or not sql.strip():
            return False, "empty query"

        if not SQLSecurity.is_single_statement(sql, dialect):
            return False, "multiple statements are not allowed in a single request"

        suspicious = SQLSecurity.scan_suspicious_patterns(sql)
        if suspicious:
            return False, f"blocked pattern: {suspicious[0]}"

        kind = QueryClassifier.classify(sql, dialect)
        if kind == QueryKind.ADMIN:
            return False, "administrative statements (GRANT/REVOKE/user management) are never allowed"
        if kind == QueryKind.DDL:
            return False, "schema-modifying statements (CREATE/DROP/ALTER/TRUNCATE) are not allowed"
        if kind == QueryKind.WRITE and not allow_write:
            return False, "write queries (INSERT/UPDATE/DELETE) are disabled for this connection"
        if kind == QueryKind.UNKNOWN:
            return False, "could not classify statement type"

        return True, "ok"
