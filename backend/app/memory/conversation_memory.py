"""
Multi-turn conversation memory: lets a follow-up question like "and by
region?" or "now just for last month" resolve against the previous
turn's question/SQL, instead of every question being handled in total
isolation.

Same in-process-vs-Redis pattern as app.cache: a session's turns live in
whichever backend is configured, with a bounded turn count per session so
memory can't grow unbounded, and a TTL so abandoned sessions don't leak
forever.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Dict, List, Optional, Protocol


@dataclass
class ConversationTurn:
    question: str
    sql: Optional[str]
    status: str
    explanation: str = ""
    row_count: int = 0
    created_at: float = field(default_factory=time.time)


class ConversationMemoryBackend(Protocol):
    def append_turn(self, session_id: str, turn: ConversationTurn) -> None: ...
    def get_turns(self, session_id: str, limit: int) -> List[ConversationTurn]: ...
    def clear(self, session_id: str) -> None: ...


class InProcessConversationMemory:
    """In-process backend - fine for a single instance. See
    RedisConversationMemory for the multi-instance-safe equivalent."""

    def __init__(self, max_turns_per_session: int = 10, ttl_seconds: int = 1800):
        self.max_turns = max_turns_per_session
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, tuple[float, List[ConversationTurn]]] = {}
        self._lock = Lock()

    def append_turn(self, session_id: str, turn: ConversationTurn) -> None:
        with self._lock:
            _, turns = self._store.get(session_id, (0.0, []))
            turns = turns + [turn]
            turns = turns[-self.max_turns:]
            self._store[session_id] = (time.monotonic() + self.ttl_seconds, turns)

    def get_turns(self, session_id: str, limit: int = 3) -> List[ConversationTurn]:
        with self._lock:
            entry = self._store.get(session_id)
            if entry is None:
                return []
            expires_at, turns = entry
            if time.monotonic() > expires_at:
                del self._store[session_id]
                return []
            return turns[-limit:]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)


class RedisConversationMemory:
    """Redis-backed equivalent - a capped list per session, so multiple
    backend replicas share the same conversation state."""

    _KEY_PREFIX = "sqlcopilot:memory:"

    def __init__(self, redis_client, max_turns_per_session: int = 10, ttl_seconds: int = 1800):
        self._redis = redis_client
        self.max_turns = max_turns_per_session
        self.ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{self._KEY_PREFIX}{session_id}"

    def append_turn(self, session_id: str, turn: ConversationTurn) -> None:
        key = self._key(session_id)
        pipe = self._redis.pipeline()
        pipe.rpush(key, json.dumps(asdict(turn)))
        pipe.ltrim(key, -self.max_turns, -1)
        pipe.expire(key, self.ttl_seconds)
        pipe.execute()

    def get_turns(self, session_id: str, limit: int = 3) -> List[ConversationTurn]:
        raw_turns = self._redis.lrange(self._key(session_id), -limit, -1)
        return [ConversationTurn(**json.loads(t)) for t in raw_turns]

    def clear(self, session_id: str) -> None:
        self._redis.delete(self._key(session_id))


def build_conversation_memory(settings_obj) -> ConversationMemoryBackend:
    from app.core.redis_client import get_redis_client

    redis_client = get_redis_client()
    if redis_client is not None:
        return RedisConversationMemory(redis_client)
    return InProcessConversationMemory()
