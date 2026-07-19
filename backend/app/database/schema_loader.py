"""
Orchestrates: get pooled connector -> check cache -> introspect if stale ->
optionally narrow to the tables relevant to a specific question.

This is the one function agents and API routes call; they never touch the
cache or introspector directly.
"""
from __future__ import annotations

import re
from typing import List, Optional

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.database.connection_manager import connection_manager
from app.database.introspector import DatabaseSchema, SchemaIntrospector
from app.cache.schema_cache import RedisSchemaCache, SchemaCache
from app.models.connection import DatabaseConnection


def _build_schema_cache():
    redis_client = get_redis_client()
    if redis_client is not None:
        return RedisSchemaCache(redis_client, ttl_seconds=settings.SCHEMA_CACHE_TTL_SECONDS)
    return SchemaCache(ttl_seconds=settings.SCHEMA_CACHE_TTL_SECONDS)


_schema_cache = _build_schema_cache()

# Built vector indexes are cached per connection in-process (rebuilding a
# TF-IDF index is cheap - milliseconds even for a few hundred tables - but
# still wasteful to redo on every single question). Keyed the same as the
# schema cache and invalidated together (see invalidate_schema_cache).
_vectorstore_cache: dict = {}

_STOPWORDS = {
    "the", "a", "an", "of", "for", "in", "on", "by", "with", "and", "or",
    "show", "me", "get", "list", "find", "what", "which", "how", "many",
    "is", "are", "was", "were", "top", "all", "each",
}


def load_schema(connection: DatabaseConnection, *, force_refresh: bool = False) -> DatabaseSchema:
    if not force_refresh:
        cached = _schema_cache.get(connection.id)
        if cached is not None:
            return cached

    connector = connection_manager.get_connector(connection)
    schema = SchemaIntrospector(connector.engine).introspect()
    _schema_cache.set(connection.id, schema)
    if force_refresh:
        _vectorstore_cache.pop(connection.id, None)
    return schema


def invalidate_schema_cache(connection_id: str) -> None:
    _schema_cache.invalidate(connection_id)
    _vectorstore_cache.pop(connection_id, None)


def _get_vectorstore(connection_id: str, schema: DatabaseSchema):
    from app.vectorstore import SchemaVectorStore

    cached = _vectorstore_cache.get(connection_id)
    if cached is not None:
        return cached

    store = SchemaVectorStore()
    store.build(schema)
    _vectorstore_cache[connection_id] = store
    return store


def relevant_subset(schema: DatabaseSchema, question: str, *, max_tables: int = 12) -> List[str]:
    """
    Narrow a large schema down to the tables most likely relevant to a
    question, by scoring table/column name token overlap. Keeps the LLM
    prompt small and focused on enterprise schemas with 100+ tables, and
    always keeps tables directly FK-linked to any table that scores.
    """
    if len(schema.tables) <= max_tables:
        return schema.table_names()

    tokens = {t for t in re.findall(r"[a-zA-Z]+", question.lower()) if t not in _STOPWORDS}
    if not tokens:
        return schema.table_names()[:max_tables]

    scored = []
    for table in schema.tables:
        haystack = table.name.lower() + " " + " ".join(c.name.lower() for c in table.columns)
        score = sum(1 for tok in tokens if tok in haystack)
        scored.append((score, table.name))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    selected = {name for score, name in scored[:max_tables] if score > 0}

    if not selected:
        # nothing matched by name - fall back to the first N tables rather
        # than an empty schema, so the LLM still has something to work with
        return schema.table_names()[:max_tables]

    return _with_fk_neighbors(schema, selected, max_tables)


def vector_relevant_subset(
    connection_id: str, schema: DatabaseSchema, question: str, *, max_tables: int = 12
) -> List[str]:
    """Same contract as relevant_subset(), but ranks tables by embedding
    similarity (app.vectorstore) instead of exact keyword overlap - catches
    cases like a "clients" question matching a "customers" table that
    keyword overlap scores as zero (see app/vectorstore/schema_vectorstore.py
    for why char n-gram TF-IDF specifically helps here)."""
    if len(schema.tables) <= max_tables:
        return schema.table_names()

    store = _get_vectorstore(connection_id, schema)
    if not store.is_built():
        return relevant_subset(schema, question, max_tables=max_tables)

    results = store.search(question, k=max_tables)
    selected = {r.table_name for r in results if r.score > 0}

    if not selected:
        return relevant_subset(schema, question, max_tables=max_tables)

    return _with_fk_neighbors(schema, selected, max_tables)


def _with_fk_neighbors(schema: DatabaseSchema, selected: set, max_tables: int) -> List[str]:
    """Pull in direct FK neighbors so joins referenced by matched tables
    aren't missing from the prompt - shared by both narrowing strategies."""
    neighbors = set()
    for table in schema.tables:
        if table.name in selected:
            for fk in table.foreign_keys:
                neighbors.add(fk.references_table)

    final = selected | neighbors
    return [name for name in schema.table_names() if name in final][:max(max_tables, len(final))]


def get_relevant_tables(connection_id: str, schema: DatabaseSchema, question: str, *, max_tables: int = 12) -> List[str]:
    """Strategy dispatcher - what app.llm.schema_formatter actually calls.
    Controlled by settings.SCHEMA_SEARCH_STRATEGY ("keyword" or "vector")."""
    if settings.SCHEMA_SEARCH_STRATEGY == "vector":
        return vector_relevant_subset(connection_id, schema, question, max_tables=max_tables)
    return relevant_subset(schema, question, max_tables=max_tables)
