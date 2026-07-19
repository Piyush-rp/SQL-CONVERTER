"""
Application exception hierarchy.

Every exception the app raises intentionally derives from AppError so a single
FastAPI exception handler can turn it into a consistent JSON error envelope
with the right HTTP status code, instead of leaking tracebacks or generic 500s.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    """Base class for all application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ValidationAppError(AppError):
    status_code = 422
    error_code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    error_code = "authentication_error"


class AuthorizationError(AppError):
    status_code = 403
    error_code = "authorization_error"


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"


class RateLimitError(AppError):
    status_code = 429
    error_code = "rate_limited"


# --- Domain-specific errors ------------------------------------------------

class DatabaseConnectionError(AppError):
    """Raised when Copilot cannot connect to a user's target database."""
    status_code = 400
    error_code = "database_connection_error"


class SchemaIntrospectionError(AppError):
    status_code = 400
    error_code = "schema_introspection_error"


class SQLGenerationError(AppError):
    """Raised when the LLM pipeline fails to produce valid SQL after retries."""
    status_code = 422
    error_code = "sql_generation_error"


class SQLValidationError(AppError):
    status_code = 422
    error_code = "sql_validation_error"


class UnsafeSQLError(AppError):
    """Raised when generated or user-submitted SQL fails the security gate."""
    status_code = 403
    error_code = "unsafe_sql"


class QueryExecutionError(AppError):
    status_code = 400
    error_code = "query_execution_error"


class QueryTimeoutError(AppError):
    status_code = 408
    error_code = "query_timeout"


class LLMProviderError(AppError):
    status_code = 502
    error_code = "llm_provider_error"
