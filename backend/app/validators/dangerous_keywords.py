"""
Statement-type classification used by the security gate.

Rather than a flat "bad word" blocklist (which is easy to build wrong and
easy to bypass with comments/whitespace), this classifies SQL by parsed
statement type via sqlglot and only allows DML the deployment has opted into.
"""
from __future__ import annotations

# Statement types that mutate data or schema. Blocked unless
# settings.ALLOW_WRITE_QUERIES is True for that connection.
WRITE_STATEMENT_TYPES = {
    "insert", "update", "delete", "merge",
}

DDL_STATEMENT_TYPES = {
    "create", "drop", "alter", "truncate",
}

# Administrative/permission statements: always blocked regardless of
# ALLOW_WRITE_QUERIES - Copilot is never allowed to manage grants/roles/users.
ADMIN_STATEMENT_TYPES = {
    "grant", "revoke", "createuser", "alteruser", "dropuser",
}

# Multi-statement separators and system-catalog escape hatches that are
# common SQL-injection vectors even inside an otherwise-valid single query.
SUSPICIOUS_PATTERNS = [
    r";\s*\S",           # a second statement after a semicolon
    r"--",                # inline comment (can hide a truncated statement)
    r"/\*.*\*/",           # block comment
    r"\bxp_cmdshell\b",    # SQL Server command execution
    r"\bpg_read_file\b",   # Postgres filesystem read
    r"\bload_file\s*\(",    # MySQL filesystem read
    r"\binto\s+outfile\b",  # MySQL filesystem write
]
