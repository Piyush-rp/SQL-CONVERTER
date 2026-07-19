"""End-to-end tests of the LangGraph multi-agent pipeline, with the LLM
mocked (no network/API key required) but everything else - schema
introspection, validation, real SQLite execution, chart selection - real."""
from unittest.mock import patch

from app.database.connector import ConnectionConfig, DatabaseConnector
from app.models.connection import DatabaseConnection, DBEngine
from app.workflows.workflow_manager import WorkflowManager


def _fake_response(sql_or_text: str):
    return type("R", (), {"content": sql_or_text})()


def _connection_row(target_db_path):
    return DatabaseConnection(
        id="conn-1", owner_id="user-1", name="test", engine=DBEngine.SQLITE,
        file_path=target_db_path, read_only=True, is_active=True,
    )


def test_happy_path_success(target_db_path):
    connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
    conn_row = _connection_row(target_db_path)

    class GoodModel:
        def invoke(self, messages):
            if any("Explain the following SQL" in m.content for m in messages):
                return _fake_response("Totals order amounts grouped by country.")
            return _fake_response(
                "```sql\nSELECT c.country, SUM(o.amount) AS total_amount FROM orders o "
                "JOIN customers c ON o.customer_id = c.id GROUP BY c.country\n```"
            )

    with patch("app.llm.sql_generator.get_chat_model", return_value=GoodModel()), \
         patch("app.agents.explanation_agent.get_chat_model", return_value=GoodModel()), \
         patch("app.database.connection_manager.connection_manager.get_connector", return_value=connector):
        result = WorkflowManager().run(question="total order amount by country", connection=conn_row)

    assert result.status == "success"
    assert result.execution["row_count"] == 2
    assert result.chart_spec["chart_type"] in ("bar", "pie")


def test_execution_failure_triggers_retry_and_recovers(target_db_path):
    connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
    conn_row = _connection_row(target_db_path)

    class FlakyModel:
        def __init__(self):
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return _fake_response("```sql\nSELECT made_up_column FROM customers\n```")
            return _fake_response("```sql\nSELECT name FROM customers\n```")

    explainer = type("M", (), {"invoke": lambda self, m: _fake_response("explained")})()

    with patch("app.llm.sql_generator.get_chat_model", return_value=FlakyModel()), \
         patch("app.agents.explanation_agent.get_chat_model", return_value=explainer), \
         patch("app.database.connection_manager.connection_manager.get_connector", return_value=connector):
        result = WorkflowManager().run(question="names of customers", connection=conn_row)

    assert result.status == "success"
    assert result.retry_count == 1


def test_write_query_is_rejected_not_silently_failed(target_db_path):
    connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
    conn_row = _connection_row(target_db_path)

    class BadModel:
        def invoke(self, messages):
            return _fake_response("```sql\nDELETE FROM customers\n```")

    with patch("app.llm.sql_generator.get_chat_model", return_value=BadModel()), \
         patch("app.database.connection_manager.connection_manager.get_connector", return_value=connector):
        result = WorkflowManager().run(question="delete all customers", connection=conn_row)

    assert result.status == "rejected"
    assert "disabled" in result.error_message


def test_cannot_answer_short_circuits(target_db_path):
    connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
    conn_row = _connection_row(target_db_path)

    class CannotModel:
        def invoke(self, messages):
            return _fake_response("CANNOT_ANSWER: no weather data in this schema")

    with patch("app.llm.sql_generator.get_chat_model", return_value=CannotModel()), \
         patch("app.database.connection_manager.connection_manager.get_connector", return_value=connector):
        result = WorkflowManager().run(question="what's the weather", connection=conn_row)

    assert result.status == "clarification_needed"
