"""
Structured logging setup using loguru.

Every log line carries a request_id (bound via contextvars in middleware) so
requests can be traced end-to-end across agents in production log aggregators
(Datadog, ELK, CloudWatch, etc). JSON output is toggled by settings.LOG_JSON
so dev gets pretty console logs and prod gets machine-parseable ones.

Two sinks: stdout (what a container orchestrator captures) and a rotating
file under logs/ (useful for local dev without a log aggregator, and as a
fallback if stdout capture is misconfigured). Both are configured the same
way regardless of environment - disable the file sink by setting
LOG_TO_FILE=false if you only want stdout (e.g. read-only containers).
"""
from __future__ import annotations

import sys
from contextvars import ContextVar
from pathlib import Path

from loguru import logger as _logger

from app.core.config import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="-")

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"


def _patch_record(record):
    record["extra"]["request_id"] = request_id_ctx.get()
    record["extra"]["user_id"] = user_id_ctx.get()


# `log` is the single logger instance the whole app imports. It auto-injects
# request_id/user_id from contextvars into every record.
log = _logger.patch(lambda record: _patch_record(record))


def configure_logging() -> None:
    """Call once at startup (see app.main) to attach the sinks."""
    _logger.remove()
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
        "req={extra[request_id]} user={extra[user_id]} | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    _logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        serialize=settings.LOG_JSON,
        format=fmt if not settings.LOG_JSON else "{message}",
        backtrace=False,
        diagnose=settings.ENVIRONMENT.value == "dev",
    )

    if settings.LOG_TO_FILE:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _logger.add(
            _LOG_DIR / "app.log",
            level=settings.LOG_LEVEL,
            serialize=settings.LOG_JSON,
            format=fmt if not settings.LOG_JSON else "{message}",
            rotation="20 MB",
            retention="14 days",
            compression="gz",
            backtrace=False,
            diagnose=False,  # never write full local-variable tracebacks to a file that might get shipped/shared
        )
