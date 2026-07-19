"""Calls the LLM (via SQLGenerator) to turn the question into SQL, feeding
back the previous attempt's validation error on retries. Also threads
through the full schema + a live connector so SQLGenerator can use the
agentic tool-calling path (app.tools) when settings.ENABLE_TOOL_CALLING
is on - both are already available at this point in the pipeline
(schema_agent ran first; the connector is cheap to fetch, pooled)."""
from __future__ import annotations

from app.agents.state import WorkflowState
from app.database.connection_manager import connection_manager
from app.llm.sql_generator import SQLGenerator
from app.models.connection import DatabaseConnection


class SQLGeneratorAgent:
    def run(self, state: WorkflowState, connection: DatabaseConnection) -> WorkflowState:
        generator = SQLGenerator(state.get("llm_config"))

        is_retry = state.get("retry_count", 0) > 0
        previous_sql = state.get("sql") if is_retry else None
        previous_error = state.get("last_error") if is_retry else None

        connector = connection_manager.get_connector(connection)

        result = generator.generate(
            question=state["question"],
            schema_text=state["schema_text"],
            engine_name=state["engine_name"],
            previous_sql=previous_sql,
            previous_error=previous_error,
            conversation_turns=state.get("conversation_turns"),
            full_schema=state.get("full_schema"),
            connector=connector,
            allow_write=state.get("allow_write", False),
        )

        return {
            **state,
            "sql": result.sql,
            "cannot_answer_reason": result.cannot_answer_reason,
            "raw_llm_response": result.raw_response,
        }
