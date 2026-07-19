"""
Pydantic request/response models for the API, split by domain rather than
one flat file. Separate from app.models (SQLAlchemy ORM) on purpose -
these are the public HTTP contract and can evolve independently of the DB
schema (e.g. never expose hashed_password).

Everything re-exported here so existing `from app.schemas import X`
call sites throughout the API routers don't need to change.
"""
from app.schemas.auth import TokenPair, UserLogin, UserOut, UserRegister
from app.schemas.connections import ConnectionCreate, ConnectionOut, ConnectionTestResult
from app.schemas.schema_browser import ColumnOut, SchemaOut, TableOut
from app.schemas.query import (
    AskRequest,
    AskResponse,
    AuditLogEntryOut,
    ChartSpecOut,
    ExecutionOut,
    OptimizationSuggestionOut,
    QueryHistoryOut,
)

__all__ = [
    "UserRegister", "UserLogin", "TokenPair", "UserOut",
    "ConnectionCreate", "ConnectionOut", "ConnectionTestResult",
    "ColumnOut", "TableOut", "SchemaOut",
    "AskRequest", "ExecutionOut", "ChartSpecOut", "OptimizationSuggestionOut",
    "AskResponse", "QueryHistoryOut", "AuditLogEntryOut",
]
