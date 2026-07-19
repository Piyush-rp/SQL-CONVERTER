"""
Tests for app.tools - both the individual tools directly, and the full
agentic tool-calling loop with a FAKE tool-calling model (no network/API
key required) that mimics the real protocol: .bind_tools() returns a
model, .invoke() returns an AIMessage with .tool_calls on intermediate
turns and a final content-only AIMessage with no tool_calls.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from app.database.introspector import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from app.tools.query_execution_tool import make_query_execution_tool
from app.tools.schema_lookup_tool import make_schema_lookup_tool
from app.tools.sql_validation_tool import make_sql_validation_tool


def _sample_schema() -> DatabaseSchema:
    return DatabaseSchema(
        engine_name="sqlite",
        database_name="test",
        tables=[
            TableInfo(
                name="customers", schema=None,
                columns=[
                    ColumnInfo("id", "INTEGER", False, None, True),
                    ColumnInfo("name", "TEXT", False, None, False),
                    ColumnInfo("country", "TEXT", True, None, False),
                ],
                primary_key=["id"],
            ),
            TableInfo(
                name="orders", schema=None,
                columns=[ColumnInfo("id", "INTEGER", False, None, True), ColumnInfo("customer_id", "INTEGER", False, None, False)],
                primary_key=["id"],
                foreign_keys=[ForeignKeyInfo("customer_id", "customers", "id")],
            ),
        ],
    )


class TestSchemaLookupTool:
    def test_looks_up_existing_table(self):
        tool = make_schema_lookup_tool(_sample_schema())
        result = tool.invoke({"table_name": "customers"})
        assert "id: INTEGER" in result
        assert "PK" in result
        assert "name: TEXT" in result
        assert "NOT NULL" in result

    def test_includes_foreign_keys(self):
        tool = make_schema_lookup_tool(_sample_schema())
        result = tool.invoke({"table_name": "orders"})
        assert "customer_id -> customers.id" in result

    def test_unknown_table_lists_available_tables(self):
        tool = make_schema_lookup_tool(_sample_schema())
        result = tool.invoke({"table_name": "nonexistent_table"})
        assert "No table named" in result
        assert "customers" in result


class TestSQLValidationTool:
    def test_valid_query_reports_valid(self):
        tool = make_sql_validation_tool(engine_name="sqlite")
        result = tool.invoke({"sql": "SELECT id, name FROM customers"})
        assert result.startswith("Valid")

    def test_dangerous_query_reports_invalid_with_reason(self):
        tool = make_sql_validation_tool(engine_name="sqlite")
        result = tool.invoke({"sql": "DROP TABLE customers"})
        assert result.startswith("Invalid")
        assert "not allowed" in result.lower()

    def test_write_query_blocked_unless_allowed(self):
        tool = make_sql_validation_tool(engine_name="sqlite", allow_write=False)
        result = tool.invoke({"sql": "DELETE FROM customers"})
        assert result.startswith("Invalid")


class TestQueryExecutionTool:
    def test_runs_real_exploratory_query(self, target_db_path):
        from app.database.connector import ConnectionConfig, DatabaseConnector
        from app.models.connection import DBEngine

        connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
        tool = make_query_execution_tool(connector, engine_name="sqlite")

        result = tool.invoke({"sql": "SELECT DISTINCT country FROM customers"})
        assert "country" in result
        assert "US" in result or "UK" in result

    def test_rejects_unsafe_sql_before_touching_the_database(self, target_db_path):
        from app.database.connector import ConnectionConfig, DatabaseConnector
        from app.models.connection import DBEngine

        connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
        tool = make_query_execution_tool(connector, engine_name="sqlite")

        result = tool.invoke({"sql": "DROP TABLE customers"})
        assert result.startswith("Query rejected")

        # prove the table really wasn't touched
        from sqlalchemy import text
        with connector.engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
        assert count == 2


class TestAgenticSQLGenerator:
    def test_tool_calling_loop_uses_lookup_tool_then_answers(self, target_db_path):
        """A fake tool-calling model that first calls the schema-lookup
        tool, THEN produces the final SQL - proves the loop correctly
        executes tool calls, feeds results back, and terminates on the
        final content-only response."""
        from app.database.connector import ConnectionConfig, DatabaseConnector
        from app.models.connection import DBEngine
        from app.tools.agentic_sql_generator import AgenticSQLGenerator

        connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
        schema = _sample_schema()

        class FakeToolCallingModel:
            def __init__(self):
                self.call_count = 0

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                self.call_count += 1
                if self.call_count == 1:
                    return AIMessage(
                        content="",
                        tool_calls=[{"name": "lookup_table_schema", "args": {"table_name": "customers"}, "id": "call_1"}],
                    )
                return AIMessage(content="```sql\nSELECT name FROM customers\n```")

        generator = AgenticSQLGenerator(
            chat_model=FakeToolCallingModel(), schema=schema, connector=connector, engine_name="sqlite",
        )
        result = generator.generate(question="list customer names", schema_text="(irrelevant for this test)")

        assert result.sql == "SELECT name FROM customers"
        assert result.tool_calls_made == 1

    def test_stops_after_max_iterations_if_model_keeps_calling_tools(self, target_db_path):
        """Guards against an infinite loop if a misbehaving model never
        stops calling tools - the loop must terminate and return whatever
        the last response was, not hang forever."""
        from app.database.connector import ConnectionConfig, DatabaseConnector
        from app.models.connection import DBEngine
        from app.tools.agentic_sql_generator import AgenticSQLGenerator

        connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
        schema = _sample_schema()

        class AlwaysCallsToolsModel:
            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "lookup_table_schema", "args": {"table_name": "customers"}, "id": "call_x"}],
                )

        generator = AgenticSQLGenerator(
            chat_model=AlwaysCallsToolsModel(), schema=schema, connector=connector, engine_name="sqlite",
        )
        result = generator.generate(question="list customer names", schema_text="(irrelevant)")

        # never produced final SQL, but critically: returned instead of hanging
        assert result.sql is None
        assert result.tool_calls_made == 5  # _MAX_TOOL_ITERATIONS
