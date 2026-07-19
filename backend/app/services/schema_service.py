"""Thin service wrapping schema_loader for the API layer - keeps routers
free of cache/introspection details."""
from __future__ import annotations

from app.database.schema_loader import invalidate_schema_cache, load_schema
from app.database.schema_serializer import serialize_for_api
from app.models.connection import DatabaseConnection


class SchemaService:
    @staticmethod
    def get_schema(connection: DatabaseConnection, *, force_refresh: bool = False) -> dict:
        schema = load_schema(connection, force_refresh=force_refresh)
        return serialize_for_api(schema)

    @staticmethod
    def invalidate(connection_id: str) -> None:
        invalidate_schema_cache(connection_id)
