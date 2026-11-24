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
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

from app.core.exceptions import DatabaseConnectionError
from app.models.connection import DBEngine

# Driver used per engine. All of these install from pip wheels with no OS
# packages, so they work on serverless hosts (e.g. Vercel) as well as Docker.
# SQL Server uses pymssql (bundles FreeTDS) by default; pyodbc is used only if
# the connection's extra params name an ODBC driver (driver=...), because
# pyodbc needs Microsoft's ODBC driver installed on the machine.
_DIALECT_DRIVER = {
    DBEngine.POSTGRESQL: "postgresql+psycopg2",
    DBEngine.MYSQL: "mysql+pymysql",
    DBEngine.MSSQL: "mssql+pymssql",
    DBEngine.SQLITE: "sqlite",
}

_DEFAULT_PORT = {
    DBEngine.POSTGRESQL: 5432,
    DBEngine.MYSQL: 3306,
    DBEngine.MSSQL: 1433,
    DBEngine.SQLITE: 0,
}

# Seconds to wait for a TCP connection/login before giving up, so an
# unreachable host fails fast with a clear error instead of hanging the request.
CONNECT_TIMEOUT_SECONDS = 10


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


def parse_extra_params(extra: str) -> Dict[str, str]:
    """Accepts "a=b&c=d", "a=b;c=d", "a=b c=d" or a leading "?" - users paste
    these in many shapes (copied from connection strings or docs)."""
    extra = (extra or "").strip().lstrip("?")
    if not extra:
        return {}
    normalized = extra.replace(";", "&").replace(" ", "&").replace(",", "&")
    return {k.strip(): v.strip() for k, v in parse_qsl(normalized, keep_blank_values=True) if k.strip()}


_MYSQL_SSL_KEYS = {"ssl", "ssl-mode", "ssl_mode", "sslmode", "tls", "ssl_disabled"}
_TRUE = {"1", "true", "yes", "on", "require", "required", "verify_ca", "verify_identity", "verify-ca", "verify-full"}
_FALSE = {"0", "false", "no", "off", "disable", "disabled"}


def _uses_odbc(cfg: ConnectionConfig) -> bool:
    return cfg.engine == DBEngine.MSSQL and "driver" in {k.lower() for k in parse_extra_params(cfg.extra_params)}


def build_sqlalchemy_url(cfg: ConnectionConfig) -> URL:
    """Builds the URL with SQLAlchemy's URL.create, which escapes the username
    and password - so passwords containing @ : / # ? % work."""
    if cfg.engine == DBEngine.SQLITE:
        return URL.create("sqlite", database=cfg.file_path or cfg.database or ":memory:")

    params = parse_extra_params(cfg.extra_params)
    driver = _DIALECT_DRIVER[cfg.engine]
    if cfg.engine == DBEngine.MSSQL:
        if _uses_odbc(cfg):
            driver = "mssql+pyodbc"
            params.setdefault("TrustServerCertificate", "yes")
        else:
            # pymssql takes its options as connect() kwargs, not URL query params.
            params = {}
    elif cfg.engine == DBEngine.MYSQL:
        # SSL for pymysql is configured via connect_args (see _connect_args).
        params = {k: v for k, v in params.items() if k.lower() not in _MYSQL_SSL_KEYS}

    return URL.create(
        driver,
        username=cfg.username or None,
        password=cfg.password or None,
        host=cfg.host or None,
        port=cfg.port_or_default(),
        database=cfg.database or None,
        query=params,
    )


def build_url(cfg: ConnectionConfig) -> str:
    """String form of the connection URL (password included) - kept for callers
    that want a plain string; engines are built from build_sqlalchemy_url."""
    return build_sqlalchemy_url(cfg).render_as_string(hide_password=False)


def _mysql_ssl_mode(cfg: ConnectionConfig) -> str:
    """"on" / "off" when the user set it explicitly, else "auto"."""
    params = {k.lower(): v.lower() for k, v in parse_extra_params(cfg.extra_params).items()}
    if params.get("ssl_disabled", "") in _TRUE:
        return "off"
    value = next((params[k] for k in ("ssl-mode", "ssl_mode", "sslmode", "ssl", "tls") if k in params), "")
    if value in _FALSE:
        return "off"
    if value in _TRUE:
        return "on"
    return "auto"


def _connect_args(cfg: ConnectionConfig, *, mysql_ssl: bool = True) -> Dict:
    params = {k.lower(): v for k, v in parse_extra_params(cfg.extra_params).items()}

    if cfg.engine == DBEngine.SQLITE:
        return {"check_same_thread": False}

    if cfg.engine == DBEngine.POSTGRESQL:
        # libpq's default sslmode=prefer already upgrades to SSL when the
        # server offers it; users can still force sslmode=require/verify-full
        # through extra params (passed in the URL query).
        return {"connect_timeout": CONNECT_TIMEOUT_SECONDS}

    if cfg.engine == DBEngine.MYSQL:
        args: Dict = {"connect_timeout": CONNECT_TIMEOUT_SECONDS}
        if _mysql_ssl_mode(cfg) == "off" or not mysql_ssl:
            return args
        # Try TLS first so SSL-required cloud servers (Azure, PlanetScale,
        # Aiven, ...) work. pymysql REFUSES servers without SSL when ssl is
        # set, so in "auto" mode DatabaseConnector retries without it.
        args["ssl"] = {"check_hostname": False}
        return args

    if cfg.engine == DBEngine.MSSQL:
        if _uses_odbc(cfg):
            return {"timeout": CONNECT_TIMEOUT_SECONDS}
        args = {"login_timeout": CONNECT_TIMEOUT_SECONDS}
        for key in ("tds_version", "appname", "charset"):
            if key in params:
                args[key] = params[key]
        return args

    return {}


# Common driver error fragments -> a plain-English cause and what to do.
_ERROR_HINTS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("deny public network access", "not allowed to access the server", "40615", "is not allowed to connect"),
     "The database server is blocking connections from outside its network. In its firewall/networking "
     "settings, enable public access and allow all IP addresses (0.0.0.0 - 255.255.255.255), since this app "
     "has no fixed IP."),
    (("password authentication failed", "access denied", "login failed", "authentication failed", "18456"),
     "The username or password is wrong. Check them (no extra spaces) and try again."),
    (("could not translate host name", "name or service not known", "getaddrinfo failed", "unknown host",
      "nodename nor servname", "unknown mysql server host", "no such host", "unable to connect: adaptive server is unavailable"),
     "The host name can't be found or reached. Check the Host field for typos "
     "(e.g. yourserver.database.windows.net) and that the server is running."),
    (("timeout", "timed out"),
     "The server didn't respond in time. Check the host and port, and make sure the database's firewall allows "
     "connections from anywhere (0.0.0.0/0) - cloud hosts like this app don't have a fixed IP address."),
    (("connection refused", "actively refused", "10061"),
     "The server refused the connection. Check the port, and that the database accepts remote "
     "(not just localhost) connections."),
    (("does not exist", "unknown database", "cannot open database"),
     "That database name doesn't exist on the server. Check the Database name field."),
    (("doesn't support it", "server does not support ssl"),
     "This server doesn't support SSL. Remove the SSL setting from Extra options (or set ssl=false) and try again."),
    (("ssl", "tls", "encryption", "no pg_hba.conf entry"),
     "The server requires a secure (SSL) connection or rejected this client. Try Extra options: "
     "sslmode=require (PostgreSQL) or ssl=true (MySQL)."),
    (("server closed the connection", "lost connection", "connection reset"),
     "The server closed the connection immediately - it may be paused/sleeping, out of credits, or blocking "
     "this client. Check that it's running."),
    (("unable to open database file", "no such file"),
     "The SQLite file wasn't found at that path on the server."),
    (("no module named",),
     "The database driver for this engine isn't installed on the server. Redeploy with the latest requirements."),
)


def explain_connection_error(exc: BaseException) -> str:
    """Turns a raw driver exception into "what's wrong + what to do", keeping
    the first line of the original error as details for debugging."""
    raw = str(getattr(exc, "orig", None) or exc).strip().splitlines()
    detail = raw[0][:300] if raw else exc.__class__.__name__
    lowered = " ".join(raw).lower()
    for needles, hint in _ERROR_HINTS:
        if any(n in lowered for n in needles):
            return f"{hint} (Details: {detail})"
    return f"Could not connect to the database: {detail}"


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
        engine = self._build_engine(mysql_ssl=True)
        if self.config.engine == DBEngine.MYSQL and _mysql_ssl_mode(self.config) == "auto":
            # Probe once: servers without SSL (many public/local MySQL servers)
            # reject an SSL-enabled client, so fall back to a plain connection.
            try:
                with engine.connect():
                    pass
            except Exception as exc:
                if "doesn't support it" in str(exc) or "does not support ssl" in str(exc).lower():
                    engine.dispose()
                    engine = self._build_engine(mysql_ssl=False)
                # any other error is reported by test_connection / the caller
        return engine

    def _build_engine(self, *, mysql_ssl: bool) -> Engine:
        pool_kwargs = {} if self.config.engine == DBEngine.SQLITE else {
            "pool_size": 5, "max_overflow": 5, "pool_recycle": 1800,
        }
        try:
            return create_engine(
                build_sqlalchemy_url(self.config),
                pool_pre_ping=True,
                connect_args=_connect_args(self.config, mysql_ssl=mysql_ssl),
                # Execution options enforce read-only at the DBAPI/session level
                # wherever the driver supports it; app-level SQL validation
                # (see app.validators) is the primary and mandatory gate.
                execution_options={"postgresql_readonly": self.config.read_only}
                if self.config.engine == DBEngine.POSTGRESQL
                else {},
                **pool_kwargs,
            )
        except Exception as exc:  # bad URL, missing driver module, etc.
            raise DatabaseConnectionError(explain_connection_error(exc)) from exc

    def test_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return True
        except DatabaseConnectionError:
            raise
        except Exception as exc:  # driver errors aren't always SQLAlchemyError (OSError, ImportError, ...)
            raise DatabaseConnectionError(explain_connection_error(exc)) from exc

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
