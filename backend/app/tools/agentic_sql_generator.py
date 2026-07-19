"""
Tool-calling SQL generation: binds schema_lookup, sql_validation, and
query_execution tools to the chat model and runs a bounded tool-call loop,
instead of the single-shot "here's the whole schema, write SQL" approach
in app.llm.sql_generator.

This is a genuinely different generation strategy, not a wrapper around
the same thing: the model can ask for a specific table's full column list
on demand (useful when schema narrowing included a table by name but
truncated its columns), self-check its SQL via the validation tool before
answering, or run a small exploratory query to check what values a column
actually contains before writing the final aggregate query.

Enabled via settings.ENABLE_TOOL_CALLING (see app.llm.sql_generator,
which falls back to the single-shot approach for models/providers that
don't support tool calling, or when explicitly disabled).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.database.connector import DatabaseConnector
from app.database.introspector import DatabaseSchema
from app.llm.response_parser import ResponseParser
from app.llm.sql_postprocessor import SQLPostprocessor
from app.prompts.builder import PromptBuilder
from app.tools.query_execution_tool import make_query_execution_tool
from app.tools.schema_lookup_tool import make_schema_lookup_tool
from app.tools.sql_validation_tool import make_sql_validation_tool

_MAX_TOOL_ITERATIONS = 5


@dataclass
class AgenticGenerationResult:
    sql: Optional[str]
    cannot_answer_reason: Optional[str]
    raw_response: str
    tool_calls_made: int


class AgenticSQLGenerator:
    def __init__(self, chat_model, schema: DatabaseSchema, connector: DatabaseConnector, engine_name: str, allow_write: bool = False):
        self._schema = schema
        self._engine_name = engine_name

        lookup_tool = make_schema_lookup_tool(schema)
        validate_tool = make_sql_validation_tool(engine_name, allow_write)
        execute_tool = make_query_execution_tool(connector, engine_name, allow_write)

        self._tools_by_name = {
            lookup_tool.name: lookup_tool,
            validate_tool.name: validate_tool,
            execute_tool.name: execute_tool,
        }
        self._model = chat_model.bind_tools(list(self._tools_by_name.values()))

    def generate(
        self,
        *,
        question: str,
        schema_text: str,
        previous_sql: Optional[str] = None,
        previous_error: Optional[str] = None,
        conversation_turns: Optional[list] = None,
    ) -> AgenticGenerationResult:
        chat_messages = PromptBuilder.build(
            question=question,
            schema_text=schema_text,
            engine_name=self._engine_name,
            previous_sql=previous_sql,
            previous_error=previous_error,
            conversation_turns=conversation_turns,
        )
        messages = self._to_langchain_messages(chat_messages)
        # Let the model know tools are available for it to use before
        # finalizing - the base SYSTEM_PROMPT doesn't mention them, since
        # it's shared with the non-agentic single-shot path.
        messages[0] = SystemMessage(
            content=messages[0].content
            + "\n\nYou have tools available: look up a table's full schema, "
              "validate a candidate SQL statement, or run a small exploratory "
              "query. Use them if they would help, then give your final answer "
              "as a single ```sql code block."
        )

        tool_calls_made = 0
        last_response: Optional[AIMessage] = None

        for _ in range(_MAX_TOOL_ITERATIONS):
            response = self._model.invoke(messages)
            last_response = response
            messages.append(response)

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                break

            for call in tool_calls:
                tool_calls_made += 1
                tool_fn = self._tools_by_name.get(call["name"])
                if tool_fn is None:
                    result_text = f"Unknown tool: {call['name']}"
                else:
                    result_text = tool_fn.invoke(call["args"])
                messages.append(ToolMessage(content=str(result_text), tool_call_id=call["id"]))

        raw_text = last_response.content if last_response is not None else ""
        parsed = ResponseParser.parse(raw_text)

        if parsed.sql is None:
            return AgenticGenerationResult(
                sql=None, cannot_answer_reason=parsed.cannot_answer_reason,
                raw_response=raw_text, tool_calls_made=tool_calls_made,
            )

        cleaned = SQLPostprocessor.clean(parsed.sql)
        return AgenticGenerationResult(
            sql=cleaned, cannot_answer_reason=None, raw_response=raw_text, tool_calls_made=tool_calls_made,
        )

    @staticmethod
    def _to_langchain_messages(chat_messages: List[dict]):
        converted = []
        for m in chat_messages:
            if m["role"] == "system":
                converted.append(SystemMessage(content=m["content"]))
            elif m["role"] == "assistant":
                converted.append(AIMessage(content=m["content"]))
            else:
                converted.append(HumanMessage(content=m["content"]))
        return converted
