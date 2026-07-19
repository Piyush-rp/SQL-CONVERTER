"""
Fetches recent conversation turns for this session before generation, and
(via record_turn, called from workflow_manager once the final result is
known) appends the new turn afterward. Split into fetch/record rather than
a single graph node because the outcome needed for record_turn - success,
failed, rejected, or clarification_needed - isn't known until after the
whole graph has run, not at any single node within it.
"""
from __future__ import annotations

from app.agents.state import WorkflowState
from app.memory import ConversationTurn, is_likely_followup
from app.memory.conversation_memory import ConversationMemoryBackend


class MemoryAgent:
    def __init__(self, backend: ConversationMemoryBackend):
        self._backend = backend

    def fetch(self, state: WorkflowState) -> WorkflowState:
        session_id = state.get("session_id")
        if not session_id:
            return state

        prior_turns = self._backend.get_turns(session_id, limit=3)
        if not prior_turns or not is_likely_followup(state["question"], has_prior_turns=True):
            return state

        return {**state, "conversation_turns": prior_turns}

    def record_turn(self, session_id: str, question: str, status: str, sql: str = "", explanation: str = "", row_count: int = 0) -> None:
        if not session_id:
            return
        self._backend.append_turn(
            session_id,
            ConversationTurn(question=question, sql=sql or None, status=status, explanation=explanation, row_count=row_count),
        )
