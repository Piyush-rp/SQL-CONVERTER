"""
Owns the lifetime of DatabaseConnector instances (i.e. connection pools),
one per saved DatabaseConnection row, and encrypts/decrypts credentials
on the way in/out of storage.

This is the single place that turns a `DatabaseConnection` ORM row into a
live, poolable `DatabaseConnector` - callers never build engines by hand.
"""
from __future__ import annotations

from threading import Lock
from typing import Dict

from app.core.crypto import decrypt, encrypt
from app.database.connector import ConnectionConfig, DatabaseConnector
from app.models.connection import DatabaseConnection


class ConnectionManager:
    def __init__(self):
        self._connectors: Dict[str, DatabaseConnector] = {}
        self._lock = Lock()

    @staticmethod
    def encrypt_password(password: str) -> str:
        return encrypt(password)

    def _to_config(self, conn: DatabaseConnection) -> ConnectionConfig:
        return ConnectionConfig(
            engine=conn.engine,
            host=conn.host,
            port=conn.port,
            database=conn.database,
            username=conn.username,
            password=decrypt(conn.encrypted_password),
            file_path=conn.file_path,
            extra_params=conn.extra_params,
            read_only=conn.read_only,
        )

    def get_connector(self, conn: DatabaseConnection) -> DatabaseConnector:
        with self._lock:
            existing = self._connectors.get(conn.id)
            if existing is not None:
                return existing
            connector = DatabaseConnector(self._to_config(conn))
            self._connectors[conn.id] = connector
            return connector

    def test(self, conn: DatabaseConnection) -> bool:
        connector = DatabaseConnector(self._to_config(conn))
        try:
            return connector.test_connection()
        finally:
            connector.dispose()

    def drop(self, connection_id: str) -> None:
        with self._lock:
            connector = self._connectors.pop(connection_id, None)
            if connector:
                connector.dispose()


connection_manager = ConnectionManager()
