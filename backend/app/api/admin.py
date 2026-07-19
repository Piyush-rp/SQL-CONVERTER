"""Admin-only endpoints: audit log export. Gated by role (see
app.dependencies.require_role), not just authentication - a regular user
must not be able to see every other user's query history."""
from __future__ import annotations

import csv
import io
from typing import List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.responses import APIResponse
from app.database.repository import QueryHistoryRepository
from app.database.session import get_db
from app.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas import AuditLogEntryOut

router = APIRouter(prefix="/admin", tags=["Admin"])


def _fetch_audit_rows(db: Session, limit: int, offset: int) -> List[AuditLogEntryOut]:
    rows = QueryHistoryRepository(db).list_all_for_audit(limit=limit, offset=offset)
    return [
        AuditLogEntryOut(
            id=entry.id,
            user_id=entry.user_id,
            user_email=email,
            connection_id=entry.connection_id,
            connection_name=connection_name,
            question=entry.question,
            generated_sql=entry.generated_sql,
            status=entry.status,
            error_message=entry.error_message,
            row_count=entry.row_count,
            execution_time_ms=entry.execution_time_ms,
            retry_count=entry.retry_count,
            created_at=entry.created_at,
        )
        for entry, email, connection_name in rows
    ]


@router.get("/audit-log", response_model=APIResponse[List[AuditLogEntryOut]])
def get_audit_log(
    limit: int = Query(1000, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    return APIResponse.ok(_fetch_audit_rows(db, limit, offset))


@router.get("/audit-log/export.csv")
def export_audit_log_csv(
    limit: int = Query(5000, le=50000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    entries = _fetch_audit_rows(db, limit, offset)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "created_at", "user_email", "connection_name", "question", "generated_sql",
         "status", "error_message", "row_count", "execution_time_ms", "retry_count"]
    )
    for e in entries:
        writer.writerow(
            [e.id, e.created_at.isoformat(), e.user_email, e.connection_name, e.question,
             e.generated_sql, e.status.value, e.error_message, e.row_count, e.execution_time_ms, e.retry_count]
        )
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
