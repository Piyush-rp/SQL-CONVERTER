"""Lazy, shared Redis connection. Returns None when REDIS_URL isn't set,
so every caller (schema cache, rate limiter) can gracefully fall back to
an in-process implementation for single-instance deployments."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from app.core.config import settings


@lru_cache
def get_redis_client() -> Optional["redis.Redis"]:  # noqa: F821 - imported lazily below
    if not settings.REDIS_URL:
        return None

    import redis

    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    client.ping()  # fail fast at startup rather than on the first request
    return client
