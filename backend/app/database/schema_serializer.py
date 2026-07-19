"""
Serializes a DatabaseSchema into the compact text format fed to the LLM.

Token budget matters: a 200-table enterprise database won't fit in a prompt,
so this renders a compact, information-dense DDL-like format rather than
verbose JSON, and supports filtering down to a relevant subset of tables
(see schema_loader.relevant_subset).
"""
from __future__ import annotations

from typing import List, Optional

from app.database.introspector import DatabaseSchema
from app.database.relationship_builder import RelationshipBuilder


def serialize_for_llm(schema: DatabaseSchema, *, only_tables: Optional[List[str]] = None) -> str:
    lines: List[str] = []
    tables = schema.tables
    if only_tables:
        tables = [t for t in tables if t.name in only_tables]

    for table in tables:
        col_parts = []
        for col in table.columns:
            markers = []
            if col.is_primary_key:
                markers.append("PK")
            if not col.nullable:
                markers.append("NOT NULL")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            col_parts.append(f"{col.name} {col.type}{marker_str}")
        lines.append(f"TABLE {table.name} (")
        lines.append("  " + ",\n  ".join(col_parts))
        lines.append(")")

        if table.foreign_keys:
            for fk in table.foreign_keys:
                lines.append(f"  FK: {table.name}.{fk.column} -> {fk.references_table}.{fk.references_column}")
        lines.append("")

    relationships = RelationshipBuilder.build(schema)
    if relationships:
        lines.append("RELATIONSHIPS:")
        for rel in relationships:
            lines.append(f"  {rel.as_join_hint()}")

    return "\n".join(lines)


def serialize_for_api(schema: DatabaseSchema) -> dict:
    """JSON-friendly shape for the frontend's schema browser."""
    return {
        "engine": schema.engine_name,
        "database": schema.database_name,
        "tables": [
            {
                "name": t.name,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.type,
                        "nullable": c.nullable,
                        "isPrimaryKey": c.is_primary_key,
                    }
                    for c in t.columns
                ],
                "primaryKey": t.primary_key,
                "foreignKeys": [
                    {"column": fk.column, "referencesTable": fk.references_table, "referencesColumn": fk.references_column}
                    for fk in t.foreign_keys
                ],
                "indexes": [{"name": i.name, "columns": i.columns, "unique": i.unique} for i in t.indexes],
            }
            for t in schema.tables
        ],
    }
