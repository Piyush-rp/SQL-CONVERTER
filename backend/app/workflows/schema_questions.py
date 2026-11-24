"""
Answers questions about the database's STRUCTURE ("give me the schema",
"list the tables", "details of the family file table", "columns of orders")
straight from the introspected schema - no LLM call, instant and always
accurate. The SQL generator only writes SELECTs over data, so these used to
come back as "needs clarification" or "wrong database".
"""
from __future__ import annotations

import re
from typing import List, Optional

from app.agents.state import ExecutionResult
from app.database.introspector import DatabaseSchema, TableInfo

_STRUCTURE_INTENT = re.compile(
    r"\b("
    r"schema|structure|"
    r"(list|show|display|give|get)( me)?( all| the)? tables|"
    r"(what|which) tables|tables (are|does|do|in|exist)|how many tables|"
    r"describe|"
    r"(columns?|fields?|attributes?) (of|in|for)|what (columns|fields)|"
    r"details?\b.*\btables?|table details|"
    r"tables? (details|definition|layout)"
    r")\b",
    re.IGNORECASE,
)

# Questions about the DATA (counts of rows, top-N, totals...) still go to the
# SQL generator even if they mention a table or column.
_DATA_INTENT = re.compile(
    r"\b(rows?|records?|entries|most|least|top \d+|average|avg|sum|total|revenue|count of|"
    r"group|where|between|greater|less|latest|oldest|newest|values?)\b",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_structure_question(question: str) -> bool:
    return bool(_STRUCTURE_INTENT.search(question)) and not _DATA_INTENT.search(question)


def _mentioned_tables(question: str, schema: DatabaseSchema) -> List[TableInfo]:
    """Tables named in the question, matched loosely ("family file" finds
    `_family_file`). When names overlap ("family" and "family file"), the
    longer, more specific match wins."""
    q = _norm(question)
    hits = [t for t in schema.tables if len(_norm(t.name)) >= 3 and _norm(t.name) in q]
    hits.sort(key=lambda t: len(_norm(t.name)), reverse=True)
    chosen: List[TableInfo] = []
    for t in hits:
        if not any(_norm(t.name) in _norm(c.name) for c in chosen):
            chosen.append(t)
    return chosen


def answer_structure_question(question: str, schema: DatabaseSchema) -> Optional[dict]:
    """Returns {"explanation", "execution"} for a structure question, else None."""
    if not is_structure_question(question) or not schema.tables:
        return None

    tables = _mentioned_tables(question, schema)
    if tables:
        rows = []
        for t in tables:
            refs = {fk.column: f"{fk.references_table}.{fk.references_column}" for fk in t.foreign_keys}
            for c in t.columns:
                row = [c.name, c.type, "yes" if c.nullable else "no", "yes" if c.is_primary_key else "", refs.get(c.name, "")]
                rows.append([t.name] + row if len(tables) > 1 else row)
        columns = ["column", "type", "nullable", "primary key", "references"]
        if len(tables) > 1:
            columns = ["table"] + columns
        if len(tables) == 1:
            t = tables[0]
            pk = f" Its primary key is {', '.join(t.primary_key)}." if t.primary_key else ""
            links = (
                f" It links to {', '.join(sorted({fk.references_table for fk in t.foreign_keys}))}."
                if t.foreign_keys else ""
            )
            explanation = f"Table `{t.name}` has {len(t.columns)} columns.{pk}{links}"
        else:
            explanation = f"Structure of {len(tables)} tables: {', '.join(t.name for t in tables)}."
    else:
        columns = ["table", "columns", "primary key", "links to"]
        rows = [
            [
                t.name,
                len(t.columns),
                ", ".join(t.primary_key),
                ", ".join(sorted({fk.references_table for fk in t.foreign_keys})),
            ]
            for t in schema.tables
        ]
        explanation = (
            f"This database has {len(schema.tables)} tables"
            f"{' (the first 200 are loaded)' if len(schema.tables) >= 200 else ''}. "
            "Ask about a specific one - e.g. \"columns of "
            f"{schema.tables[0].name}\" - to see its columns."
        )

    execution = ExecutionResult(columns=columns, rows=rows, row_count=len(rows), truncated=False)
    execution["execution_time_ms"] = 0
    return {"explanation": explanation, "execution": execution}
