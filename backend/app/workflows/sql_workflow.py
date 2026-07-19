"""
The actual LangGraph state machine wiring every agent together:

  schema -> generate -> validate -> (invalid & retries left) -> generate
                                  -> (valid)                  -> execute -> optimize -> explain -> chart -> END
                                  -> (invalid & retries exhausted) -> END (status=failed)
  generate -> (CANNOT_ANSWER) -> END (status=clarification_needed)

Built once at import time (building a graph per-request would be wasteful);
`compiled_graph.invoke(state)` runs a full pass.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.chart_agent import ChartAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.explanation_agent import ExplanationAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.optimizer_agent import OptimizerAgent
from app.agents.retry_agent import RetryAgent
from app.agents.schema_agent import SchemaAgent
from app.agents.sql_generator_agent import SQLGeneratorAgent
from app.agents.state import WorkflowState
from app.agents.validator_agent import ValidatorAgent
from app.memory import build_conversation_memory
from app.models.connection import DatabaseConnection


def build_graph(connection: DatabaseConnection, memory_backend=None):
    from app.core.config import settings

    if memory_backend is None:
        memory_backend = build_conversation_memory(settings)
    memory_agent = MemoryAgent(memory_backend)
    schema_agent = SchemaAgent()
    generator_agent = SQLGeneratorAgent()
    validator_agent = ValidatorAgent()
    execution_agent = ExecutionAgent()
    optimizer_agent = OptimizerAgent()
    explanation_agent = ExplanationAgent()
    chart_agent = ChartAgent()

    graph = StateGraph(WorkflowState)

    graph.add_node("memory", memory_agent.fetch)
    graph.add_node("schema", lambda state: schema_agent.run(state, connection))
    graph.add_node("generate", lambda state: generator_agent.run(state, connection))
    graph.add_node("validate", validator_agent.run)
    graph.add_node("retry_increment", RetryAgent.increment)
    graph.add_node("execute", lambda state: execution_agent.run(state, connection))
    graph.add_node("optimize", lambda state: optimizer_agent.run(state, connection))
    graph.add_node("explain", explanation_agent.run)
    graph.add_node("chart", chart_agent.run)

    graph.set_entry_point("memory")
    graph.add_edge("memory", "schema")
    graph.add_edge("schema", "generate")

    def after_generate(state: WorkflowState) -> str:
        return "cannot_answer" if state.get("cannot_answer_reason") else "validate"

    graph.add_conditional_edges("generate", after_generate, {"cannot_answer": END, "validate": "validate"})

    def after_validate(state: WorkflowState) -> str:
        validation = state.get("validation")
        if validation is not None and validation.is_valid:
            return "execute"
        if RetryAgent.should_retry_validation(state):
            return "retry"
        return "give_up"

    graph.add_conditional_edges(
        "validate", after_validate, {"execute": "execute", "retry": "retry_increment", "give_up": END}
    )

    def after_execute(state: WorkflowState) -> str:
        if state.get("execution") is not None:
            return "optimize"
        if RetryAgent.should_retry_execution(state):
            return "retry"
        return "give_up"

    graph.add_conditional_edges(
        "execute", after_execute, {"optimize": "optimize", "retry": "retry_increment", "give_up": END}
    )

    # retry_increment is shared by both the validation-failure and
    # execution-failure paths - either way, the next stop is another
    # generation attempt with `last_error` fed back into the prompt.
    graph.add_edge("retry_increment", "generate")

    graph.add_edge("optimize", "explain")
    graph.add_edge("explain", "chart")
    graph.add_edge("chart", END)

    return graph.compile()
