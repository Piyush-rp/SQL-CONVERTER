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

from sqlalchemy import inspect, text
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
            try:
                all_names = inspector.get_table_names()
                try:
                    all_names = all_names + inspector.get_view_names()
                except (NotImplementedError, SQLAlchemyError):
                    pass
            except SQLAlchemyError:
                # Restricted accounts sometimes can't read the system catalogs
                # SQLAlchemy uses; the ANSI information_schema is readable by anyone.
                all_names = self._fallback_table_names()

            if include_tables:
                all_names = [t for t in all_names if t in include_tables]
            all_names = all_names[: self.max_tables]

            tables = self._introspect_tables(inspector, all_names)

            return DatabaseSchema(
                engine_name=self.engine.dialect.name,
                database_name=self.engine.url.database or "",
                tables=tables,
            )
        except SQLAlchemyError as exc:
            raise SchemaIntrospectionError(f"Failed to introspect schema: {exc}") from exc

    def _introspect_tables(self, inspector, names: List[str]) -> List[TableInfo]:
        """Reads every table's structure using as few round trips as possible -
        remote databases are often 100-300 ms away, and reading table by table
        (5+ queries each) made a 64-table MySQL schema take ~95 s."""
        if not names:
            return []
        dialect = self.engine.dialect.name

        if dialect == "postgresql":
            # SQLAlchemy's bulk reflection: one catalog query per kind of
            # metadata for ALL tables. Restricted users (e.g. denied
            # pg_collation) fall back to information_schema.
            try:
                return self._bulk_reflect(inspector, names)
            except SQLAlchemyError:
                return self._information_schema_tables(names)

        if dialect in ("mysql", "mariadb", "mssql"):
            # SQLAlchemy has no bulk reflection for these, so read the ANSI
            # information_schema in bulk instead (works for any user).
            try:
                return self._information_schema_tables(names)
            except SQLAlchemyError:
                pass  # fall through to per-table reflection

        # SQLite (local file, so per-table is fast) and last-resort path.
        tables: List[TableInfo] = []
        for index, name in enumerate(names):
            try:
                tables.append(self._introspect_table(inspector, name))
            except SQLAlchemyError:
                tables.extend(self._information_schema_tables(names[index:]))
                break
        return tables

    def _bulk_reflect(self, inspector, names: List[str]) -> List[TableInfo]:
        from sqlalchemy.engine.reflection import ObjectKind

        kw = {"filter_names": names, "kind": ObjectKind.ANY}
        multi_cols = inspector.get_multi_columns(**kw)
        multi_pks = inspector.get_multi_pk_constraint(**kw)
        try:
            multi_fks = inspector.get_multi_foreign_keys(**kw)
        except SQLAlchemyError:
            multi_fks = {}
        try:
            multi_idx = inspector.get_multi_indexes(**kw)
        except (SQLAlchemyError, NotImplementedError):
            multi_idx = {}

        def by_name(d):
            return {key[1]: value for key, value in d.items()}

        cols, pks, fks, idxs = by_name(multi_cols), by_name(multi_pks), by_name(multi_fks), by_name(multi_idx)
        tables = []
        for name in names:
            if name not in cols:
                continue
            pk_columns = (pks.get(name) or {}).get("constrained_columns", []) or []
            tables.append(
                TableInfo(
                    name=name,
                    schema=None,
                    columns=[
                        ColumnInfo(
                            name=c["name"],
                            type=str(c["type"]),
                            nullable=c.get("nullable", True),
                            default=str(c["default"]) if c.get("default") is not None else None,
                            is_primary_key=c["name"] in pk_columns,
                            autoincrement=bool(c.get("autoincrement", False)),
                        )
                        for c in cols[name]
                    ],
                    primary_key=pk_columns,
                    foreign_keys=[
                        ForeignKeyInfo(column=lc, references_table=fk.get("referred_table", ""), references_column=rc)
                        for fk in fks.get(name, [])
                        for lc, rc in zip(fk.get("constrained_columns", []), fk.get("referred_columns", []))
                    ],
                    indexes=[
                        IndexInfo(name=i.get("name") or "", columns=[c for c in i.get("column_names", []) if c], unique=i.get("unique", False))
                        for i in idxs.get(name, [])
                    ],
                )
            )
        return tables

    # --- information_schema path ----------------------------------------------
    # Works on PostgreSQL, MySQL and SQL Server for any user that can see the
    # tables at all: a few bulk queries give tables, columns, primary keys and
    # (best effort) foreign keys. Indexes are left empty.

    def _current_schema_sql(self) -> str:
        return {
            "postgresql": "current_schema()",
            "mysql": "DATABASE()",
            "mssql": "SCHEMA_NAME()",
        }.get(self.engine.dialect.name, "")

    def _fallback_table_names(self) -> List[str]:
        schema_sql = self._current_schema_sql()
        if not schema_sql:
            raise SchemaIntrospectionError("Could not list tables for this database")
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    f"WHERE table_schema = {schema_sql} ORDER BY table_name"
                )
            ).fetchall()
        return [r[0] for r in rows]

    def _information_schema_fks(self, conn, schema_sql: str) -> List[tuple]:
        dialect = self.engine.dialect.name
        if dialect in ("mysql", "mariadb"):
            sql = (
                "SELECT table_name, column_name, referenced_table_name, referenced_column_name "
                "FROM information_schema.key_column_usage "
                f"WHERE table_schema = {schema_sql} AND referenced_table_name IS NOT NULL"
            )
        else:  # ANSI form - PostgreSQL and SQL Server
            sql = (
                "SELECT kcu.table_name, kcu.column_name, ref.table_name, ref.column_name "
                "FROM information_schema.referential_constraints rc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON kcu.constraint_name = rc.constraint_name AND kcu.constraint_schema = rc.constraint_schema "
                "JOIN information_schema.key_column_usage ref "
                "  ON ref.constraint_name = rc.unique_constraint_name "
                " AND ref.constraint_schema = rc.unique_constraint_schema "
                " AND ref.ordinal_position = kcu.ordinal_position "
                f"WHERE kcu.table_schema = {schema_sql}"
            )
        try:
            return conn.execute(text(sql)).fetchall()
        except SQLAlchemyError:
            return []

    def _information_schema_tables(self, names: List[str]) -> List[TableInfo]:
        schema_sql = self._current_schema_sql()
        if not schema_sql or not names:
            return []
        wanted = set(names)
        with self.engine.connect() as conn:
            col_rows = conn.execute(
                text(
                    "SELECT table_name, column_name, data_type, is_nullable, column_default "
                    "FROM information_schema.columns "
                    f"WHERE table_schema = {schema_sql} ORDER BY table_name, ordinal_position"
                )
            ).fetchall()
        # Separate connections: on PostgreSQL a failed query aborts the whole
        # transaction, which would make every later query fail too.
        try:
            with self.engine.connect() as conn:
                pk_rows = conn.execute(
                    text(
                        "SELECT kcu.table_name, kcu.column_name "
                        "FROM information_schema.table_constraints tc "
                        "JOIN information_schema.key_column_usage kcu "
                        "  ON tc.constraint_name = kcu.constraint_name "
                        " AND tc.table_schema = kcu.table_schema AND tc.table_name = kcu.table_name "
                        f"WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = {schema_sql}"
                    )
                ).fetchall()
        except SQLAlchemyError:
            pk_rows = []
        with self.engine.connect() as conn:
            fk_rows = self._information_schema_fks(conn, schema_sql)

        fks: Dict[str, List[ForeignKeyInfo]] = {}
        for table_name, column_name, ref_table, ref_column in fk_rows:
            fks.setdefault(table_name, []).append(
                ForeignKeyInfo(column=column_name, references_table=ref_table, references_column=ref_column)
            )

        pks: Dict[str, List[str]] = {}
        for table_name, column_name in pk_rows:
            pks.setdefault(table_name, []).append(column_name)

        by_table: Dict[str, List[ColumnInfo]] = {}
        for table_name, column_name, data_type, is_nullable, column_default in col_rows:
            if table_name not in wanted:
                continue
            by_table.setdefault(table_name, []).append(
                ColumnInfo(
                    name=column_name,
                    type=str(data_type).upper(),
                    nullable=str(is_nullable).upper() == "YES",
                    default=str(column_default) if column_default is not None else None,
                    is_primary_key=column_name in pks.get(table_name, []),
                )
            )

        return [
            TableInfo(
                name=name,
                schema=None,
                columns=by_table[name],
                primary_key=pks.get(name, []),
                foreign_keys=fks.get(name, []),
            )
            for name in names
            if name in by_table
        ]

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
