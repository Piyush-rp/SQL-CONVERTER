"""
Integration tests against REAL Postgres and MySQL servers (not just
SQLite). These are skipped automatically if the servers aren't reachable -
CI/local dev without Postgres/MySQL installed still gets a clean run via
the SQLite-backed tests elsewhere; this file is what proves the
dialect-agnostic introspection/execution/cost-estimation code paths
actually work against the other two real engines, not just in theory.

To run these locally: have a Postgres on localhost:5432 and MySQL on
localhost:3306 reachable with user "copilot" / password "copilot_test_pw"
and a database called "copilot_target_test" on each (see docs/setup.md).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.connector import ConnectionConfig, DatabaseConnector
from app.database.introspector import SchemaIntrospector
from app.database.relationship_builder import RelationshipBuilder
from app.models.connection import DBEngine
from app.validators.sql_cost_estimator import SQLCostEstimator
from app.validators.sql_validator import SQLValidator

PG_CFG = ConnectionConfig(
    engine=DBEngine.POSTGRESQL, host="localhost", port=5432,
    database="copilot_target_test", username="copilot", password="copilot_test_pw",
)
MYSQL_CFG = ConnectionConfig(
    engine=DBEngine.MYSQL, host="localhost", port=3306,
    database="copilot_target_test", username="copilot", password="copilot_test_pw",
)


def _reachable(cfg: ConnectionConfig) -> bool:
    try:
        DatabaseConnector(cfg).test_connection()
        return True
    except Exception:
        return False


def _seed(connector: DatabaseConnector, engine_name: str) -> None:
    with connector.engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS orders")
        conn.exec_driver_sql("DROP TABLE IF EXISTS customers")
        if engine_name == "postgresql":
            conn.exec_driver_sql("CREATE TABLE customers (id SERIAL PRIMARY KEY, name TEXT NOT NULL, country TEXT)")
            conn.exec_driver_sql("CREATE TABLE orders (id SERIAL PRIMARY KEY, customer_id INT NOT NULL REFERENCES customers(id), amount NUMERIC)")
        else:
            conn.exec_driver_sql("CREATE TABLE customers (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255) NOT NULL, country VARCHAR(255))")
            conn.exec_driver_sql("CREATE TABLE orders (id INT AUTO_INCREMENT PRIMARY KEY, customer_id INT NOT NULL, amount DECIMAL(10,2), FOREIGN KEY (customer_id) REFERENCES customers(id))")
        conn.exec_driver_sql("INSERT INTO customers (name, country) VALUES ('Acme','US'),('Globex','UK')")
        conn.exec_driver_sql("INSERT INTO orders (customer_id, amount) VALUES (1,100.5),(1,50.0),(2,200.0)")


@pytest.mark.parametrize("cfg,label", [(PG_CFG, "postgresql"), (MYSQL_CFG, "mysql")])
def test_full_stack_against_real_server(cfg, label):
    if not _reachable(cfg):
        pytest.skip(f"No {label} server reachable at {cfg.host}:{cfg.port} - see docs/setup.md")

    admin_cfg = ConnectionConfig(**{**cfg.__dict__, "read_only": False})
    admin_connector = DatabaseConnector(admin_cfg)
    _seed(admin_connector, label)
    admin_connector.dispose()

    readonly_cfg = ConnectionConfig(**{**cfg.__dict__, "read_only": True})
    connector = DatabaseConnector(readonly_cfg)

    assert connector.test_connection() is True

    schema = SchemaIntrospector(connector.engine).introspect()
    assert set(schema.table_names()) == {"customers", "orders"}

    rels = RelationshipBuilder.build(schema)
    assert any(r.as_join_hint() == "orders.customer_id = customers.id" for r in rels)

    sql = "SELECT country, SUM(amount) AS total FROM orders o JOIN customers c ON o.customer_id = c.id GROUP BY country"
    validation = SQLValidator.validate(sql, engine_name=label)
    assert validation.is_valid

    cost = SQLCostEstimator.estimate(connector.engine, sql)
    assert cost.supported
    assert cost.estimated_rows is not None and cost.estimated_rows > 0

    with connector.engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    assert len(rows) == 2

    # Postgres enforces read-only at the session level (see connector.py);
    # MySQL's DBAPI doesn't support an equivalent session flag, so for MySQL
    # this is enforced by the app-level validator only (tested elsewhere) -
    # only assert the extra DB-level guarantee where it actually applies.
    if label == "postgresql":
        with pytest.raises(SQLAlchemyError):
            with connector.engine.begin() as conn:
                conn.exec_driver_sql("DELETE FROM customers")

    connector.dispose()
