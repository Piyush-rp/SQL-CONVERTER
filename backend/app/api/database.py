"""Schema browsing for a saved connection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import APIResponse
from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas import SchemaOut
from app.services.connection_service import ConnectionService
from app.services.schema_service import SchemaService

router = APIRouter(prefix="/connections/{connection_id}", tags=["Database"])


@router.get("/schema", response_model=APIResponse[SchemaOut])
def get_schema(
    connection_id: str,
    refresh: bool = Query(False, description="Bypass the schema cache and re-introspect now"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    connection = ConnectionService(db).get_owned(connection_id, user.id)
    schema = SchemaService.get_schema(connection, force_refresh=refresh)
    return APIResponse.ok(schema)
