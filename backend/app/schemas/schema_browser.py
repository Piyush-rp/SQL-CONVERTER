"""Pydantic models for the /connections/{id}/schema endpoint. Named
schema_browser (not schema.py) to avoid shadowing the `schemas` package
itself and app.database.schema_loader in imports."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel


class ColumnOut(BaseModel):
    name: str
    type: str
    nullable: bool
    isPrimaryKey: bool


class TableOut(BaseModel):
    name: str
    columns: List[ColumnOut]
    primaryKey: List[str]
    foreignKeys: List[dict]
    indexes: List[dict]


class SchemaOut(BaseModel):
    engine: str
    database: str
    tables: List[TableOut]
