from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.connection import DBEngine


class ConnectionCreate(BaseModel):
    name: str
    engine: DBEngine
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    file_path: str = ""
    extra_params: str = ""
    read_only: bool = True


class ConnectionOut(BaseModel):
    id: str
    name: str
    engine: DBEngine
    host: str
    database: str
    read_only: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
