"""Connection robustness: URL escaping, extra options, driver choice, error
messages, input clean-up, and not saving connections that fail their test."""
from sqlalchemy.exc import OperationalError

from app.core.exceptions import DatabaseConnectionError
from app.database.connector import (
    ConnectionConfig,
    DatabaseConnector,
    _connect_args,
    build_sqlalchemy_url,
    build_url,
    explain_connection_error,
    parse_extra_params,
)
from app.models.connection import DBEngine
from app.schemas import ConnectionCreate


def test_special_characters_in_password_are_escaped():
    url = build_url(ConnectionConfig(DBEngine.POSTGRESQL, "h", 5432, "db", "user", "p@ss:w/rd#1?"))
    assert url == "postgresql+psycopg2://user:p%40ss%3Aw%2Frd%231%3F@h:5432/db"
    # and SQLAlchemy decodes it back to the exact original password
    assert build_sqlalchemy_url(ConnectionConfig(DBEngine.POSTGRESQL, "h", 5432, "db", "user", "p@ss:w/rd#1?")).password == "p@ss:w/rd#1?"


def test_empty_password_is_allowed():
    url = build_url(ConnectionConfig(DBEngine.MYSQL, "h", 4497, "Rfam", "rfamro", ""))
    assert url == "mysql+pymysql://rfamro@h:4497/Rfam"


def test_extra_params_accept_common_shapes():
    assert parse_extra_params("sslmode=require") == {"sslmode": "require"}
    assert parse_extra_params("?sslmode=require&connect_timeout=5") == {"sslmode": "require", "connect_timeout": "5"}
    assert parse_extra_params("a=1; b=2") == {"a": "1", "b": "2"}
    assert parse_extra_params("") == {}


def test_postgres_extra_params_go_into_url():
    url = build_url(ConnectionConfig(DBEngine.POSTGRESQL, "h", 5432, "db", "u", "p", extra_params="sslmode=require"))
    assert url.endswith("?sslmode=require")


def test_sql_server_uses_pymssql_unless_odbc_driver_named():
    plain = ConnectionConfig(DBEngine.MSSQL, "srv.database.windows.net", 1433, "db", "u", "p")
    assert build_sqlalchemy_url(plain).drivername == "mssql+pymssql"
    odbc = ConnectionConfig(DBEngine.MSSQL, "srv", 1433, "db", "u", "p", extra_params="driver=ODBC Driver 18 for SQL Server")
    assert build_sqlalchemy_url(odbc).drivername == "mssql+pyodbc"


def test_mysql_uses_opportunistic_ssl_unless_disabled():
    cfg = ConnectionConfig(DBEngine.MYSQL, "h", 3306, "db", "u", "p")
    assert "ssl" in _connect_args(cfg)
    off = ConnectionConfig(DBEngine.MYSQL, "h", 3306, "db", "u", "p", extra_params="ssl=false")
    assert "ssl" not in _connect_args(off)
    # SSL options must not leak into the URL query, where pymysql would reject them
    assert "ssl" not in build_url(ConnectionConfig(DBEngine.MYSQL, "h", 3306, "db", "u", "p", extra_params="ssl=true"))


def test_connect_timeouts_are_set_for_network_engines():
    assert _connect_args(ConnectionConfig(DBEngine.POSTGRESQL, "h"))["connect_timeout"] > 0
    assert _connect_args(ConnectionConfig(DBEngine.MYSQL, "h"))["connect_timeout"] > 0
    assert _connect_args(ConnectionConfig(DBEngine.MSSQL, "h"))["login_timeout"] > 0


def test_error_messages_explain_cause_and_fix():
    auth = OperationalError("SELECT 1", {}, Exception('FATAL:  password authentication failed for user "x"'))
    assert "username or password is wrong" in explain_connection_error(auth)
    dns = OperationalError("SELECT 1", {}, Exception('could not translate host name "nope" to address'))
    assert "host name" in explain_connection_error(dns)
    firewall = Exception("Connection was denied because Deny Public Network Access is set to Yes")
    assert "allow all IP addresses" in explain_connection_error(firewall)


def test_unreachable_sqlite_file_raises_friendly_error(tmp_path):
    connector = DatabaseConnector(ConnectionConfig(DBEngine.SQLITE, file_path=str(tmp_path / "missing" / "x.db")))
    try:
        connector.test_connection()
        raise AssertionError("expected a DatabaseConnectionError")
    except DatabaseConnectionError as exc:
        assert "SQLite file" in exc.message


def test_connection_form_values_are_trimmed():
    payload = ConnectionCreate(
        name=" demo ", engine="postgresql", host="  tcp://db.example.com/ ", database=" app ", username="   reader ",
        password=" keep spaces ",
    )
    assert payload.host == "db.example.com"
    assert payload.username == "reader"
    assert payload.database == "app"
    assert payload.password == " keep spaces "  # passwords are never altered


def test_failed_connection_is_not_saved(app_client, tmp_path):
    app_client.post("/api/v1/auth/register", json={"email": "frank@example.com", "password": "pw-12345678", "full_name": "F"})
    token = app_client.post("/api/v1/auth/login", json={"email": "frank@example.com", "password": "pw-12345678"}).json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    bad = app_client.post(
        "/api/v1/connections",
        headers=headers,
        json={"name": "broken", "engine": "sqlite", "file_path": str(tmp_path / "missing" / "x.db")},
    )
    assert bad.status_code == 400
    assert "SQLite file" in bad.json()["error"]["message"]

    listed = app_client.get("/api/v1/connections", headers=headers).json()["data"]
    assert listed == []
