"""
A real LangChain tool the model can call mid-generation to fetch full
column detail for a specific table by name.

Why this matters: schema narrowing (app.database.schema_loader /
app.vectorstore) includes a table in the prompt by NAME to keep token
usage bounded on large schemas, but for a schema with hundreds of columns
per table, even the narrowed set's full column listing can be expensive.
This tool lets the model ask for one table's full detail on demand instead
of every candidate table's complete column list being front-loaded into
every prompt - a genuine complement to schema narrowing, not a duplicate
of it.
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.database.introspector import DatabaseSchema


def make_schema_lookup_tool(schema: DatabaseSchema):
    """Factory (not a bare @tool function) because the tool needs to close
    over a specific schema instance - LangChain tools are otherwise
    stateless functions, and binding the right schema per-request (not a
    shared global) matters since different questions can be against
    different connections."""

    @tool
    def lookup_table_schema(table_name: str) -> str:
        """Look up the full column list, types, primary key, and foreign
        keys for a specific table by exact name. Use this when you need
        more detail on a table than what's shown in the schema summary -
        for example, if a table's columns were truncated for brevity, or
        to confirm a column's exact name/type before referencing it in SQL."""
        table = schema.get_table(table_name)
        if table is None:
            available = ", ".join(schema.table_names()[:20])
            return f"No table named '{table_name}' exists. Available tables include: {available}"

        lines = [f"TABLE {table.name}:"]
        for col in table.columns:
            markers = []
            if col.is_primary_key:
                markers.append("PK")
            if not col.nullable:
                markers.append("NOT NULL")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            lines.append(f"  - {col.name}: {col.type}{marker_str}")

        if table.foreign_keys:
            lines.append("Foreign keys:")
            for fk in table.foreign_keys:
                lines.append(f"  - {fk.column} -> {fk.references_table}.{fk.references_column}")

        return "\n".join(lines)

    return lookup_table_schema
