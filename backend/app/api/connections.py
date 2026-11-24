from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import APIResponse
from app.database.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas import ConnectionCreate, ConnectionOut, ConnectionTestResult
from app.services.connection_service import ConnectionService

router = APIRouter(prefix="/connections", tags=["Connections"])


@router.post("", response_model=APIResponse[ConnectionOut], status_code=201)
def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # create() tests the credentials first and only saves on success, so a
    # bad host/password returns a clear 400 without leaving a broken entry.
    connection = ConnectionService(db).create(user.id, payload)
    return APIResponse.ok(ConnectionOut.model_validate(connection))


@router.get("", response_model=APIResponse[List[ConnectionOut]])
def list_connections(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    connections = ConnectionService(db).list_for_user(user.id)
    return APIResponse.ok([ConnectionOut.model_validate(c) for c in connections])


@router.post("/{connection_id}/test", response_model=APIResponse[ConnectionTestResult])
def test_connection(connection_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = ConnectionService(db)
    connection = service.get_owned(connection_id, user.id)
    try:
        service.test(connection)
        return APIResponse.ok(ConnectionTestResult(success=True, message="Connection successful"))
    except Exception as exc:
        return APIResponse.ok(ConnectionTestResult(success=False, message=str(exc)))


@router.delete("/{connection_id}", response_model=APIResponse[None])
def delete_connection(connection_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = ConnectionService(db)
    connection = service.get_owned(connection_id, user.id)
    service.delete(connection)
    return APIResponse.ok()
