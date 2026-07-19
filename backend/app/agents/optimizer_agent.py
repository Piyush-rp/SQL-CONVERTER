"""Runs rule-based optimization suggestions and a best-effort cost estimate
against the final SQL - after execution, since EXPLAIN needs a live connection
and we want this to run even if it can't block the result on failure."""
from __future__ import annotations

from app.agents.state import WorkflowState
from app.database.connection_manager import connection_manager
from app.models.connection import DatabaseConnection
from app.validators.sql_cost_estimator import SQLCostEstimator
from app.validators.sql_optimizer import SQLOptimizer


class OptimizerAgent:
    def run(self, state: WorkflowState, connection: DatabaseConnection) -> WorkflowState:
        validation = state.get("validation")
        if validation is None or not validation.is_valid:
            return state

        sql = validation.sql
        suggestions = SQLOptimizer.analyze(sql, dialect=state.get("engine_name"))

        cost_estimate = None
        try:
            connector = connection_manager.get_connector(connection)
            cost_estimate = SQLCostEstimator.estimate(connector.engine, sql)
        except Exception:
            # Cost estimation is a nice-to-have, never block the pipeline on it.
            cost_estimate = None

        return {**state, "optimization_suggestions": suggestions, "cost_estimate": cost_estimate}
