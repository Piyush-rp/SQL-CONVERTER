"""Public entry point for running the full NL -> SQL pipeline. This is the
only thing app.services.query_service calls - it doesn't know or care that
LangGraph is the orchestration engine underneath, or that conversation
memory is backed by Redis vs in-process."""
from __future__ import annotations

import uuid
from typing import Optional

from app.agents.memory_agent import MemoryAgent
from app.agents.state import WorkflowState
from app.core.config import settings
from app.core.exceptions import QueryExecutionError, QueryTimeoutError
from app.llm.llm_config import LLMConfig
from app.memory import build_conversation_memory
from app.models.connection import DatabaseConnection
from app.workflows.sql_workflow import build_graph
from app.workflows.workflow_result import WorkflowResult


class WorkflowManager:
    def __init__(self):
        # Shared across every run() call - one memory backend instance so
        # fetch (inside the graph) and record_turn (after it) agree on the
        # same store, whether that's in-process or Redis.
        self._memory_backend = build_conversation_memory(settings)
        self._memory_agent = MemoryAgent(self._memory_backend)

    def run(
        self,
        *,
        question: str,
        connection: DatabaseConnection,
        llm_config: Optional[LLMConfig] = None,
        session_id: Optional[str] = None,
    ) -> WorkflowResult:
        session_id = session_id or str(uuid.uuid4())

        initial_state: WorkflowState = {
            "question": question,
            "connection_id": connection.id,
            "connection_name": connection.name,
            "engine_name": connection.engine.value,
            "allow_write": settings.ALLOW_WRITE_QUERIES and not connection.read_only,
            "llm_config": llm_config or LLMConfig(),
            "max_retries": settings.MAX_AGENT_RETRIES,
            "retry_count": 0,
            "errors": [],
            "session_id": session_id,
        }

        graph = build_graph(connection, memory_backend=self._memory_backend)
        try:
            final_state = graph.invoke(initial_state)
            result = WorkflowResult.from_state(final_state)
        except (QueryExecutionError, QueryTimeoutError) as exc:
            result = WorkflowResult(status="failed", question=question, error_message=str(exc), session_id=session_id)

        self._memory_agent.record_turn(
            session_id,
            question=question,
            status=result.status,
            sql=result.sql or "",
            explanation=result.explanation,
            row_count=result.execution["row_count"] if result.execution else 0,
        )

        return result


workflow_manager = WorkflowManager()
