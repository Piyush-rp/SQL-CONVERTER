"""Business logic for creating/testing/listing saved database connections.
Encrypts the password on the way in; the raw password never touches the
DB row or a log line."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.database.connection_manager import connection_manager
from app.database.repository import ConnectionRepository
from app.models.connection import DatabaseConnection
from app.schemas import ConnectionCreate


class ConnectionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ConnectionRepository(db)

    def create(self, owner_id: str, payload: ConnectionCreate) -> DatabaseConnection:
        connection = DatabaseConnection(
            owner_id=owner_id,
            name=payload.name,
            engine=payload.engine,
            host=payload.host,
            port=payload.port,
            database=payload.database,
            username=payload.username,
            encrypted_password=connection_manager.encrypt_password(payload.password),
            file_path=payload.file_path,
            extra_params=payload.extra_params,
            read_only=payload.read_only,
        )
        return self.repo.create(connection)

    def list_for_user(self, owner_id: str) -> List[DatabaseConnection]:
        return self.repo.list_for_user(owner_id)

    def get_owned(self, connection_id: str, owner_id: str) -> DatabaseConnection:
        connection = self.repo.get(connection_id, owner_id)
        if connection is None:
            raise NotFoundError("Connection not found")
        return connection

    def test(self, connection: DatabaseConnection) -> bool:
        return connection_manager.test(connection)

    def delete(self, connection: DatabaseConnection) -> None:
        connection_manager.drop(connection.id)
        self.repo.soft_delete(connection)
