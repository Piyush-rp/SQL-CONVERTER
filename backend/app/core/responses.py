"""
Standard API response envelope.

Every endpoint returns the same shape so frontend code (and any third-party
API consumer) can rely on one contract instead of guessing per-endpoint.
"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    meta: dict = {}

    @classmethod
    def ok(cls, data: Any = None, meta: Optional[dict] = None) -> "APIResponse":
        return cls(success=True, data=data, meta=meta or {})

    @classmethod
    def fail(cls, code: str, message: str, details: Optional[dict] = None) -> "APIResponse":
        return cls(success=False, error=ErrorDetail(code=code, message=message, details=details or {}))


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
