from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.connection import DBEngine


class ConnectionCreate(BaseModel):
    name: str
    engine: DBEngine
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""  # optional: some public databases have passwordless read-only users
    file_path: str = ""
    extra_params: str = ""
    read_only: bool = True

    @field_validator("name", "host", "database", "username", "file_path", "extra_params")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        # Pasted values often carry stray spaces (" reader"), which make the
        # database reject the login with a confusing error.
        return v.strip() if isinstance(v, str) else v

    @field_validator("host")
    @classmethod
    def strip_scheme_from_host(cls, v: str) -> str:
        # Users sometimes paste "tcp://host" or "host/" into the Host field.
        for prefix in ("tcp://", "tcp:", "http://", "https://"):
            if v.lower().startswith(prefix):
                v = v[len(prefix):]
        return v.rstrip("/")


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
