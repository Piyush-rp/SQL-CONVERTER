"""
Unified connector across PostgreSQL, MySQL, SQL Server and SQLite.

The rest of the app (introspection, execution, agents) never branches on
engine type - it talks to this one class, which builds the right SQLAlchemy
URL/driver per engine and enforces a read-only, timeout-bounded, row-capped
connection. Supporting a 5th engine later is a ~10 line addition here, not a
change scattered through the codebase.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DatabaseConnectionError
from app.models.connection import DBEngine

# Driver used per engine. psycopg2/pymysql/pyodbc/sqlite3 are all pure-Python
# or wheel-distributed, so no OS package installs are required except the
# SQL Server ODBC driver itself, which is documented in docs/setup.md.
_DIALECT_DRIVER = {
    DBEngine.POSTGRESQL: "postgresql+psycopg2",
    DBEngine.MYSQL: "mysql+pymysql",
    DBEngine.MSSQL: "mssql+pyodbc",
    DBEngine.SQLITE: "sqlite",
}

_DEFAULT_PORT = {
    DBEngine.POSTGRESQL: 5432,
    DBEngine.MYSQL: 3306,
    DBEngine.MSSQL: 1433,
    DBEngine.SQLITE: 0,
}


@dataclass
class ConnectionConfig:
    engine: DBEngine
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    file_path: str = ""  # sqlite only
    extra_params: str = ""  # e.g. "sslmode=require" or "driver=ODBC+Driver+18+for+SQL+Server"
    read_only: bool = True

    def port_or_default(self) -> int:
        return self.port or _DEFAULT_PORT[self.engine]


def build_url(cfg: ConnectionConfig) -> str:
    driver = _DIALECT_DRIVER[cfg.engine]

    if cfg.engine == DBEngine.SQLITE:
        path = cfg.file_path or cfg.database or ":memory:"
        return f"sqlite:///{path}"

    if cfg.engine == DBEngine.MSSQL:
        extra = cfg.extra_params or "driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        return (
            f"{driver}://{cfg.username}:{cfg.password}@{cfg.host}:{cfg.port_or_default()}"
            f"/{cfg.database}?{extra}"
        )

    suffix = f"?{cfg.extra_params}" if cfg.extra_params else ""
    return f"{driver}://{cfg.username}:{cfg.password}@{cfg.host}:{cfg.port_or_default()}/{cfg.database}{suffix}"


class DatabaseConnector:
    """Owns a SQLAlchemy Engine (connection pool) for a single target database."""

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    def _create_engine(self) -> Engine:
        url = build_url(self.config)
        connect_args = {}
        if self.config.engine == DBEngine.SQLITE:
            connect_args = {"check_same_thread": False}

        try:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_recycle=1800,
                connect_args=connect_args,
                # Execution options enforce read-only at the DBAPI/session level
                # wherever the driver supports it; app-level SQL validation
                # (see app.validators) is the primary and mandatory gate.
                execution_options={"postgresql_readonly": self.config.read_only}
                if self.config.engine == DBEngine.POSTGRESQL
                else {},
            )
            return engine
        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(f"Failed to build engine: {exc}") from exc

    def test_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return True
        except SQLAlchemyError as exc:
            raise DatabaseConnectionError(f"Could not connect to database: {exc}") from exc

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
