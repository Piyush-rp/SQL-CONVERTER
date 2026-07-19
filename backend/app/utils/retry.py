"""Generic retry-with-exponential-backoff decorator for transient
failures talking to external services (Vault, in particular - see
app/core/secrets.py, which had no retry logic before this)."""
from __future__ import annotations

import functools
import time
from typing import Callable, Tuple, Type, TypeVar

from app.core.logger import log

T = TypeVar("T")


def retry_with_backoff(
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 5.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Retries the decorated function on the given exception types, with
    exponential backoff (base_delay * 2^attempt, capped at max_delay).
    Re-raises the last exception if all attempts are exhausted."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        break
                    delay = min(base_delay_seconds * (2 ** attempt), max_delay_seconds)
                    log.warning(f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {exc}. Retrying in {delay}s.")
                    time.sleep(delay)
            raise last_exc

        return wrapper

    return decorator
