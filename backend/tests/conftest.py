"""Shared pytest fixtures. Tests run against a SQLite metadata DB and a
separate SQLite "target" DB with sample data - no external services
required, so `pytest` works out of the box in CI.

Env vars are set at collection time (before any `app.*` module is
imported), since app.database.session builds its engine from settings at
import time - this avoids fragile module-reload gymnastics mid-test-run.
"""
from __future__ import annotations

import os

os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-prod"
os.environ["DATABASE_URL"] = "sqlite:///./test_app_metadata.db"

import pytest
from fastapi.testclient import TestClient

from app.database.connector import ConnectionConfig, DatabaseConnector
from app.database.session import init_metadata_db
from app.models.connection import DBEngine


@pytest.fixture(scope="session", autouse=True)
def _init_test_metadata_db():
    init_metadata_db()
    yield
    try:
        os.remove("./test_app_metadata.db")
    except OSError:
        pass


@pytest.fixture()
def target_db_path(tmp_path):
    db_path = tmp_path / "target.db"
    cfg = ConnectionConfig(engine=DBEngine.SQLITE, file_path=str(db_path))
    connector = DatabaseConnector(cfg)
    with connector.engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT)")
        conn.exec_driver_sql(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, amount REAL, "
            "FOREIGN KEY(customer_id) REFERENCES customers(id))"
        )
        conn.exec_driver_sql("INSERT INTO customers VALUES (1,'Acme','US'),(2,'Globex','UK')")
        conn.exec_driver_sql("INSERT INTO orders VALUES (1,1,100.5),(2,1,50.0),(3,2,200.0)")
    connector.dispose()
    return str(db_path)


@pytest.fixture()
def app_client():
    from app.main import app as fastapi_app
    with TestClient(fastapi_app) as client:
        yield client
