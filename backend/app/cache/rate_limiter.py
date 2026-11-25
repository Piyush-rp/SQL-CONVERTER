"""
Rate limiter implementations, alongside the schema cache in this package
since both are "shared, ephemeral, TTL'd state" with the identical
in-process-vs-Redis tradeoff.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from app.core.exceptions import RateLimitError


class RateLimiter:
    """Fixed-window-ish limiter per user id, in-process. Fine for a single
    instance / dev / small deployments; each replica in a multi-instance
    deployment would otherwise track its own independent window - see
    RedisRateLimiter below."""

    def __init__(self, limit_per_minute: int):
        self.limit = limit_per_minute
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - 60
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < window_start:
                hits.popleft()
            if len(hits) >= self.limit:
                raise RateLimitError(f"Rate limit of {self.limit} requests/minute exceeded")
            hits.append(now)


class RedisRateLimiter:
    """Same fixed-window semantics as RateLimiter, but shared across every
    replica via Redis, so the configured limit is the *actual* limit
    regardless of how many backend instances are running behind a load
    balancer. Uses a sorted set per user: each hit is added with the
    current timestamp as its score, then anything older than the window
    is trimmed before counting - this is the standard Redis sliding-window
    pattern and needs no Lua scripting for our accuracy requirements."""

    _KEY_PREFIX = "sqlcopilot:ratelimit:"

    def __init__(self, redis_client, limit_per_minute: int):
        self._redis = redis_client
        self.limit = limit_per_minute

    def check(self, key: str) -> None:
        redis_key = f"{self._KEY_PREFIX}{key}"
        now = time.time()
        window_start = now - 60

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        _, count = pipe.execute()

        if count >= self.limit:
            raise RateLimitError(f"Rate limit of {self.limit} requests/minute exceeded")

        pipe = self._redis.pipeline()
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, 60)
        pipe.execute()


def build_rate_limiter(settings_obj):
    from app.core.redis_client import get_redis_client

    redis_client = get_redis_client()
    if redis_client is not None:
        return RedisRateLimiter(redis_client, settings_obj.RATE_LIMIT_PER_MINUTE)
    return RateLimiter(settings_obj.RATE_LIMIT_PER_MINUTE)
