"""
Schema introspection using SQLAlchemy's Inspector.

This is dialect-agnostic: Postgres, MySQL, SQL Server and SQLite are all
introspected through the same code path, since SQLAlchemy's Inspector
abstracts the catalog-query differences between engines. This is the reason
"all 4 engines fully supported" is achievable without four parallel
implementations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import SchemaIntrospectionError


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    default: Optional[str]
    is_primary_key: bool
    autoincrement: bool = False


@dataclass
class ForeignKeyInfo:
    column: str
    references_table: str
    references_column: str


@dataclass
class IndexInfo:
    name: str
    columns: List[str]
    unique: bool


@dataclass
class TableInfo:
    name: str
    schema: Optional[str]
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    foreign_keys: List[ForeignKeyInfo] = field(default_factory=list)
    indexes: List[IndexInfo] = field(default_factory=list)
    row_count_estimate: Optional[int] = None


@dataclass
class DatabaseSchema:
    engine_name: str
    database_name: str
    tables: List[TableInfo] = field(default_factory=list)

    def table_names(self) -> List[str]:
        return [t.name for t in self.tables]

    def get_table(self, name: str) -> Optional[TableInfo]:
        return next((t for t in self.tables if t.name == name), None)

    def to_dict(self) -> dict:
        """JSON-serializable form, used by the Redis-backed cache. Plain
        `dataclasses.asdict` would work too, but being explicit here keeps
        the wire format stable even if internal field order/types shift."""
        return {
            "engine_name": self.engine_name,
            "database_name": self.database_name,
            "tables": [
                {
                    "name": t.name,
                    "schema": t.schema,
                    "row_count_estimate": t.row_count_estimate,
                    "primary_key": t.primary_key,
                    "columns": [
                        {
                            "name": c.name, "type": c.type, "nullable": c.nullable,
                            "default": c.default, "is_primary_key": c.is_primary_key,
                            "autoincrement": c.autoincrement,
                        }
                        for c in t.columns
                    ],
                    "foreign_keys": [
                        {"column": fk.column, "references_table": fk.references_table, "references_column": fk.references_column}
                        for fk in t.foreign_keys
                    ],
                    "indexes": [{"name": i.name, "columns": i.columns, "unique": i.unique} for i in t.indexes],
                }
                for t in self.tables
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DatabaseSchema":
        tables = [
            TableInfo(
                name=t["name"],
                schema=t.get("schema"),
                row_count_estimate=t.get("row_count_estimate"),
                primary_key=t.get("primary_key", []),
                columns=[ColumnInfo(**c) for c in t.get("columns", [])],
                foreign_keys=[ForeignKeyInfo(**fk) for fk in t.get("foreign_keys", [])],
                indexes=[IndexInfo(**i) for i in t.get("indexes", [])],
            )
            for t in data.get("tables", [])
        ]
        return cls(engine_name=data["engine_name"], database_name=data["database_name"], tables=tables)


class SchemaIntrospector:
    """Introspects a live SQLAlchemy Engine into a DatabaseSchema."""

    def __init__(self, engine: Engine, max_tables: int = 200):
        self.engine = engine
        self.max_tables = max_tables

    def introspect(self, *, include_tables: Optional[List[str]] = None) -> DatabaseSchema:
        try:
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            view_names = []
            try:
                view_names = inspector.get_view_names()
            except NotImplementedError:
                pass

            all_names = table_names + view_names
            if include_tables:
                all_names = [t for t in all_names if t in include_tables]
            all_names = all_names[: self.max_tables]

            tables = [self._introspect_table(inspector, name) for name in all_names]

            return DatabaseSchema(
                engine_name=self.engine.dialect.name,
                database_name=self.engine.url.database or "",
                tables=tables,
            )
        except SQLAlchemyError as exc:
            raise SchemaIntrospectionError(f"Failed to introspect schema: {exc}") from exc

    def _introspect_table(self, inspector, table_name: str) -> TableInfo:
        pk_constraint = inspector.get_pk_constraint(table_name) or {}
        pk_columns = pk_constraint.get("constrained_columns", []) or []

        columns = []
        for col in inspector.get_columns(table_name):
            columns.append(
                ColumnInfo(
                    name=col["name"],
                    type=str(col["type"]),
                    nullable=col.get("nullable", True),
                    default=str(col["default"]) if col.get("default") is not None else None,
                    is_primary_key=col["name"] in pk_columns,
                    autoincrement=bool(col.get("autoincrement", False)),
                )
            )

        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            referred_cols = fk.get("referred_columns", [])
            constrained_cols = fk.get("constrained_columns", [])
            for local_col, remote_col in zip(constrained_cols, referred_cols):
                foreign_keys.append(
                    ForeignKeyInfo(
                        column=local_col,
                        references_table=fk.get("referred_table", ""),
                        references_column=remote_col,
                    )
                )

        indexes = []
        try:
            for idx in inspector.get_indexes(table_name):
                indexes.append(
                    IndexInfo(name=idx.get("name") or "", columns=idx.get("column_names", []), unique=idx.get("unique", False))
                )
        except (SQLAlchemyError, NotImplementedError):
            pass

        return TableInfo(
            name=table_name,
            schema=None,
            columns=columns,
            primary_key=pk_columns,
            foreign_keys=foreign_keys,
            indexes=indexes,
        )
