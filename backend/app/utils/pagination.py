"""Shared limit/offset validation for list endpoints - a small thing, but
having it in one place means every paginated endpoint enforces the same
bounds instead of each router hand-rolling its own Query(le=...) constants."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PageParams:
    limit: int
    offset: int

    @classmethod
    def clamp(cls, limit: int, offset: int, *, max_limit: int = 200) -> "PageParams":
        return cls(limit=max(1, min(limit, max_limit)), offset=max(0, offset))
