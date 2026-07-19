"""
Tests for conversation memory (app.memory). The important one isn't just
"does the store round-trip data" - it's proving a follow-up question's
prompt to the LLM actually contains the prior turn's context, since that's
the entire point of this module.
"""
from __future__ import annotations

from unittest.mock import patch

from app.memory import ConversationTurn, InProcessConversationMemory, is_likely_followup
from app.memory.conversation_memory import RedisConversationMemory


class TestFollowupDetector:
    def test_no_prior_turns_is_never_a_followup(self):
        assert is_likely_followup("and by region?", has_prior_turns=False) is False

    def test_and_prefix_is_a_followup(self):
        assert is_likely_followup("and by region?", has_prior_turns=True) is True

    def test_pronoun_reference_is_a_followup(self):
        assert is_likely_followup("break that down by month", has_prior_turns=True) is True

    def test_short_question_is_a_followup(self):
        assert is_likely_followup("top 5 instead", has_prior_turns=True) is True

    def test_long_self_contained_question_is_not_a_followup(self):
        assert is_likely_followup(
            "what is the total revenue across all regions for the last fiscal year",
            has_prior_turns=True,
        ) is False


class TestInProcessConversationMemory:
    def test_append_and_retrieve(self):
        memory = InProcessConversationMemory()
        memory.append_turn("session-1", ConversationTurn(question="q1", sql="SELECT 1", status="success"))
        memory.append_turn("session-1", ConversationTurn(question="q2", sql="SELECT 2", status="success"))

        turns = memory.get_turns("session-1", limit=5)
        assert [t.question for t in turns] == ["q1", "q2"]

    def test_sessions_are_isolated(self):
        memory = InProcessConversationMemory()
        memory.append_turn("session-a", ConversationTurn(question="a-question", sql=None, status="success"))
        memory.append_turn("session-b", ConversationTurn(question="b-question", sql=None, status="success"))

        assert [t.question for t in memory.get_turns("session-a", 5)] == ["a-question"]
        assert [t.question for t in memory.get_turns("session-b", 5)] == ["b-question"]

    def test_turn_cap_keeps_only_most_recent(self):
        memory = InProcessConversationMemory(max_turns_per_session=2)
        for i in range(5):
            memory.append_turn("session-1", ConversationTurn(question=f"q{i}", sql=None, status="success"))
        turns = memory.get_turns("session-1", limit=10)
        assert [t.question for t in turns] == ["q3", "q4"]

    def test_clear_removes_session(self):
        memory = InProcessConversationMemory()
        memory.append_turn("session-1", ConversationTurn(question="q1", sql=None, status="success"))
        memory.clear("session-1")
        assert memory.get_turns("session-1", 5) == []


class TestRedisConversationMemory:
    def _redis_available(self):
        try:
            import redis
            client = redis.Redis.from_url("redis://localhost:6379/0")
            client.ping()
            return True
        except Exception:
            return False

    def test_append_and_retrieve_via_real_redis(self):
        import pytest
        if not self._redis_available():
            pytest.skip("No Redis server reachable at localhost:6379")

        import redis
        client = redis.Redis.from_url("redis://localhost:6379/15", decode_responses=True)
        client.flushdb()

        memory = RedisConversationMemory(client, max_turns_per_session=10, ttl_seconds=60)
        memory.append_turn("session-x", ConversationTurn(question="first question", sql="SELECT 1", status="success"))
        memory.append_turn("session-x", ConversationTurn(question="and by region?", sql="SELECT 2", status="success"))

        turns = memory.get_turns("session-x", limit=5)
        assert [t.question for t in turns] == ["first question", "and by region?"]
        client.flushdb()


class TestFollowUpContextReachesThePrompt:
    """The test that actually matters: run the real workflow twice with the
    SAME session_id, and prove the second call's prompt to the (mocked) LLM
    contains the first turn's question and SQL."""

    def test_second_turn_prompt_includes_first_turn_context(self, target_db_path):
        from app.database.connector import ConnectionConfig, DatabaseConnector
        from app.models.connection import DatabaseConnection, DBEngine
        from app.workflows.workflow_manager import WorkflowManager

        connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
        conn_row = DatabaseConnection(
            id="conn-mem-1", owner_id="user-1", name="test", engine=DBEngine.SQLITE,
            file_path=target_db_path, read_only=True, is_active=True,
        )

        captured_messages = []

        class RecordingModel:
            def invoke(self, messages):
                captured_messages.append(messages)
                if any("Explain the following SQL" in m.content for m in messages):
                    return type("R", (), {"content": "explained"})()
                # first call: no prior context yet: full breakdown by country
                if len(captured_messages) <= 2:
                    return type("R", (), {
                        "content": "```sql\nSELECT c.country, SUM(o.amount) AS total FROM orders o "
                                    "JOIN customers c ON o.customer_id=c.id GROUP BY c.country\n```"
                    })()
                # second call (the follow-up) - just needs to return something valid
                return type("R", (), {"content": "```sql\nSELECT c.name, SUM(o.amount) AS total FROM orders o "
                                                  "JOIN customers c ON o.customer_id=c.id GROUP BY c.name\n```"})()

        with patch("app.llm.sql_generator.get_chat_model", return_value=RecordingModel()), \
             patch("app.agents.explanation_agent.get_chat_model", return_value=RecordingModel()), \
             patch("app.database.connection_manager.connection_manager.get_connector", return_value=connector):

            manager = WorkflowManager()
            first = manager.run(question="total order amount by country", connection=conn_row, session_id="convo-1")
            assert first.status == "success"
            assert first.session_id == "convo-1"

            second = manager.run(question="and by customer name instead", connection=conn_row, session_id="convo-1")
            assert second.status == "success"

        # Find the SQL-generation call for the second turn (not the
        # explanation calls) and confirm it actually contains the first
        # turn's question and SQL as prompt context.
        sql_gen_calls = [
            msgs for msgs in captured_messages
            if not any("Explain the following SQL" in m.content for m in msgs)
        ]
        assert len(sql_gen_calls) == 2, "expected exactly one SQL-generation call per turn"

        second_turn_messages = sql_gen_calls[1]
        all_content = " ".join(m.content for m in second_turn_messages)
        assert "total order amount by country" in all_content, "prior question should be in the follow-up's prompt"
        assert "GROUP BY c.country" in all_content, "prior turn's SQL should be in the follow-up's prompt"

    def test_unrelated_second_question_does_not_pull_in_prior_context(self, target_db_path):
        """A self-contained second question shouldn't get prior-turn
        context injected - is_likely_followup() should filter it out."""
        from app.database.connector import ConnectionConfig, DatabaseConnector
        from app.models.connection import DatabaseConnection, DBEngine
        from app.workflows.workflow_manager import WorkflowManager

        connector = DatabaseConnector(ConnectionConfig(engine=DBEngine.SQLITE, file_path=target_db_path))
        conn_row = DatabaseConnection(
            id="conn-mem-2", owner_id="user-1", name="test", engine=DBEngine.SQLITE,
            file_path=target_db_path, read_only=True, is_active=True,
        )

        captured_messages = []

        class RecordingModel:
            def invoke(self, messages):
                captured_messages.append(messages)
                if any("Explain the following SQL" in m.content for m in messages):
                    return type("R", (), {"content": "explained"})()
                return type("R", (), {"content": "```sql\nSELECT COUNT(*) AS n FROM customers\n```"})()

        with patch("app.llm.sql_generator.get_chat_model", return_value=RecordingModel()), \
             patch("app.agents.explanation_agent.get_chat_model", return_value=RecordingModel()), \
             patch("app.database.connection_manager.connection_manager.get_connector", return_value=connector):

            manager = WorkflowManager()
            manager.run(question="total order amount by country", connection=conn_row, session_id="convo-2")
            manager.run(
                question="what is the total number of customer records currently stored in the system",
                connection=conn_row, session_id="convo-2",
            )

        sql_gen_calls = [
            msgs for msgs in captured_messages
            if not any("Explain the following SQL" in m.content for m in msgs)
        ]
        second_turn_messages = sql_gen_calls[1]
        all_content = " ".join(m.content for m in second_turn_messages)
        assert "total order amount by country" not in all_content
