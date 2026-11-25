"""
Tests for the Redis-backed schema cache and rate limiter against a REAL
Redis server (skipped automatically if one isn't reachable at REDIS_URL /
localhost:6379) - this is what proves the multi-instance scaling story is actually
implemented, not just described.
"""
from __future__ import annotations

import time

import pytest

from app.database.introspector import ColumnInfo, DatabaseSchema, TableInfo


def _redis_available():
    try:
        import redis
        client = redis.Redis.from_url("redis://localhost:6379/0")
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture()
def redis_client():
    if not _redis_available():
        pytest.skip("No Redis server reachable at localhost:6379")
    import redis
    client = redis.Redis.from_url("redis://localhost:6379/15", decode_responses=True)
    client.ping()
    yield client
    client.flushdb()


def _sample_schema() -> DatabaseSchema:
    return DatabaseSchema(
        engine_name="postgresql",
        database_name="testdb",
        tables=[
            TableInfo(
                name="customers",
                schema=None,
                columns=[
                    ColumnInfo(name="id", type="INTEGER", nullable=False, default=None, is_primary_key=True),
                    ColumnInfo(name="name", type="TEXT", nullable=False, default=None, is_primary_key=False),
                ],
                primary_key=["id"],
            )
        ],
    )


def test_schema_roundtrips_through_json(redis_client):
    schema = _sample_schema()
    as_json = schema.to_dict()
    restored = DatabaseSchema.from_dict(as_json)
    assert restored.table_names() == ["customers"]
    assert restored.get_table("customers").columns[0].is_primary_key is True


def test_redis_schema_cache_set_get_invalidate(redis_client):
    from app.cache.schema_cache import RedisSchemaCache

    cache = RedisSchemaCache(redis_client, ttl_seconds=60)
    schema = _sample_schema()

    assert cache.get("conn-1") is None
    cache.set("conn-1", schema)

    fetched = cache.get("conn-1")
    assert fetched is not None
    assert fetched.table_names() == ["customers"]

    cache.invalidate("conn-1")
    assert cache.get("conn-1") is None


def test_redis_schema_cache_expires(redis_client):
    from app.cache.schema_cache import RedisSchemaCache

    cache = RedisSchemaCache(redis_client, ttl_seconds=1)
    cache.set("conn-2", _sample_schema())
    assert cache.get("conn-2") is not None
    time.sleep(1.5)
    assert cache.get("conn-2") is None


def test_redis_rate_limiter_blocks_after_limit(redis_client):
    from app.cache.rate_limiter import RedisRateLimiter
    from app.core.exceptions import RateLimitError

    limiter = RedisRateLimiter(redis_client, limit_per_minute=3)
    limiter.check("user-a")
    limiter.check("user-a")
    limiter.check("user-a")
    with pytest.raises(RateLimitError):
        limiter.check("user-a")

    # a different user has their own independent window
    limiter.check("user-b")


def test_redis_rate_limiter_shared_across_instances(redis_client):
    """Proves the actual multi-instance scaling claim: two independent
    limiter objects (standing in for two backend replicas) pointed at the
    same Redis share one counter, unlike the in-process limiter."""
    from app.cache.rate_limiter import RedisRateLimiter

    replica_a = RedisRateLimiter(redis_client, limit_per_minute=2)
    replica_b = RedisRateLimiter(redis_client, limit_per_minute=2)

    replica_a.check("shared-user")
    replica_b.check("shared-user")  # different "instance", same Redis - counts toward the same limit

    from app.core.exceptions import RateLimitError
    with pytest.raises(RateLimitError):
        replica_a.check("shared-user")
