"""Loads and narrows the target database's schema for this question."""
from __future__ import annotations

from app.agents.state import WorkflowState
from app.database.schema_loader import load_schema
from app.llm.schema_formatter import format_schema_for_question
from app.models.connection import DatabaseConnection


class SchemaAgent:
    def run(self, state: WorkflowState, connection: DatabaseConnection) -> WorkflowState:
        schema = load_schema(connection)
        schema_text = format_schema_for_question(schema, state["question"], connection_id=connection.id)
        return {**state, "full_schema": schema, "schema_text": schema_text}
