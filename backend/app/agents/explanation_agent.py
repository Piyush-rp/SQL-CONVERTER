"""Asks the LLM for a short, plain-English explanation of the final SQL.
Runs after execution succeeds so the explanation can be skipped entirely
on failure paths, saving a model call."""
from __future__ import annotations

from app.agents.state import WorkflowState
from app.llm.llm_factory import get_chat_model
from app.prompts.templates import EXPLANATION_PROMPT
from app.llm.llm_config import LLMConfig


class ExplanationAgent:
    def run(self, state: WorkflowState) -> WorkflowState:
        validation = state.get("validation")
        if validation is None or not validation.is_valid:
            return state

        from langchain_core.messages import HumanMessage

        model = get_chat_model(state.get("llm_config") or LLMConfig())
        try:
            response = model.invoke([HumanMessage(content=EXPLANATION_PROMPT.format(sql=validation.sql))])
            explanation = response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            explanation = f"(Explanation unavailable: {exc})"

        return {**state, "explanation": explanation.strip()}
