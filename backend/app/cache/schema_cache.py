"""
TTL cache for introspected schemas, keyed by connection id.

Introspecting a large database on every question would add real latency and
load to the customer's DB. This trades a small staleness window
(settings.SCHEMA_CACHE_TTL_SECONDS) for consistently fast requests.

Two backends, same interface:
  - SchemaCache: in-process dict. Fine for a single instance.
  - RedisSchemaCache: shared across replicas. Used automatically when
    settings.REDIS_URL is set (see schema_loader.py's factory) - this is
    what makes cache invalidation (schema refresh) actually consistent
    across a multi-instance deployment instead of only affecting whichever
    replica handled that request (see docs/scaling.md item 1).
"""
from __future__ import annotations

import json
import time
from threading import Lock
from typing import Dict, Optional, Protocol, Tuple

from app.database.introspector import DatabaseSchema


class SchemaCacheBackend(Protocol):
    def get(self, key: str) -> Optional[DatabaseSchema]: ...
    def set(self, key: str, schema: DatabaseSchema) -> None: ...
    def invalidate(self, key: str) -> None: ...


class SchemaCache:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Tuple[float, DatabaseSchema]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[DatabaseSchema]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, schema = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return schema

    def set(self, key: str, schema: DatabaseSchema) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self.ttl_seconds, schema)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)


class RedisSchemaCache:
    """Same interface as SchemaCache, backed by Redis so every replica sees
    the same cache and the same invalidations."""

    _KEY_PREFIX = "sqlcopilot:schema:"

    def __init__(self, redis_client, ttl_seconds: int):
        self._redis = redis_client
        self.ttl_seconds = ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self._KEY_PREFIX}{key}"

    def get(self, key: str) -> Optional[DatabaseSchema]:
        raw = self._redis.get(self._key(key))
        if raw is None:
            return None
        try:
            return DatabaseSchema.from_dict(json.loads(raw))
        except (ValueError, KeyError):
            # Malformed/stale cache entry (e.g. from an older app version's
            # schema shape) - treat as a miss rather than crashing the request.
            return None

    def set(self, key: str, schema: DatabaseSchema) -> None:
        self._redis.set(self._key(key), json.dumps(schema.to_dict()), ex=self.ttl_seconds)

    def invalidate(self, key: str) -> None:
        self._redis.delete(self._key(key))
