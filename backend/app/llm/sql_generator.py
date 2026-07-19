"""
The actual NL -> SQL model call: builds the prompt, invokes the configured
LLM, parses and postprocesses the result. This is deliberately provider-
agnostic (works with whatever llm_factory hands back) and framework-thin -
agents call this, not langchain directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import settings
from app.core.exceptions import LLMProviderError
from app.llm.llm_config import LLMConfig
from app.llm.llm_factory import get_chat_model
from app.prompts.builder import ChatMessage, PromptBuilder
from app.llm.response_parser import ResponseParser
from app.llm.sql_postprocessor import SQLPostprocessor


@dataclass
class GeneratedSQL:
    sql: Optional[str]
    cannot_answer_reason: Optional[str]
    raw_response: str


def _to_langchain_messages(messages: List[ChatMessage]):
    converted = []
    for m in messages:
        if m["role"] == "system":
            converted.append(SystemMessage(content=m["content"]))
        elif m["role"] == "assistant":
            converted.append(AIMessage(content=m["content"]))
        else:
            converted.append(HumanMessage(content=m["content"]))
    return converted


class SQLGenerator:
    def __init__(self, llm_config: Optional[LLMConfig] = None):
        self.llm_config = llm_config or LLMConfig()

    def generate(
        self,
        *,
        question: str,
        schema_text: str,
        engine_name: str,
        previous_sql: Optional[str] = None,
        previous_error: Optional[str] = None,
        conversation_turns: Optional[list] = None,
        full_schema=None,
        connector=None,
        allow_write: bool = False,
    ) -> GeneratedSQL:
        model = get_chat_model(self.llm_config)

        # Agentic tool-calling path: only usable when the caller supplied
        # both the full DatabaseSchema and a live connector (the tools need
        # both - see app.tools). Falls back to the single-shot path
        # otherwise, so this is purely additive - nothing regresses when
        # the feature is off or the caller doesn't have those available.
        if settings.ENABLE_TOOL_CALLING and full_schema is not None and connector is not None:
            return self._generate_agentic(
                model=model, question=question, schema_text=schema_text, engine_name=engine_name,
                previous_sql=previous_sql, previous_error=previous_error, conversation_turns=conversation_turns,
                full_schema=full_schema, connector=connector, allow_write=allow_write,
            )

        messages = PromptBuilder.build(
            question=question,
            schema_text=schema_text,
            engine_name=engine_name,
            previous_sql=previous_sql,
            previous_error=previous_error,
            conversation_turns=conversation_turns,
        )

        try:
            response = model.invoke(_to_langchain_messages(messages))
        except Exception as exc:  # network/auth/rate-limit errors from the provider SDK
            raise LLMProviderError(f"LLM call failed: {exc}") from exc

        raw_text = response.content if hasattr(response, "content") else str(response)
        parsed = ResponseParser.parse(raw_text)

        if parsed.sql is None:
            return GeneratedSQL(sql=None, cannot_answer_reason=parsed.cannot_answer_reason, raw_response=raw_text)

        cleaned = SQLPostprocessor.clean(parsed.sql)
        capped = SQLPostprocessor.enforce_row_cap(cleaned, engine_name, settings.MAX_ROWS_RETURNED)
        return GeneratedSQL(sql=capped, cannot_answer_reason=None, raw_response=raw_text)

    @staticmethod
    def _generate_agentic(
        *, model, question, schema_text, engine_name, previous_sql, previous_error,
        conversation_turns, full_schema, connector, allow_write,
    ) -> GeneratedSQL:
        from app.tools.agentic_sql_generator import AgenticSQLGenerator

        try:
            generator = AgenticSQLGenerator(
                chat_model=model, schema=full_schema, connector=connector,
                engine_name=engine_name, allow_write=allow_write,
            )
            result = generator.generate(
                question=question, schema_text=schema_text,
                previous_sql=previous_sql, previous_error=previous_error, conversation_turns=conversation_turns,
            )
        except Exception as exc:
            raise LLMProviderError(f"LLM tool-calling call failed: {exc}") from exc

        if result.sql is None:
            return GeneratedSQL(sql=None, cannot_answer_reason=result.cannot_answer_reason, raw_response=result.raw_response)

        capped = SQLPostprocessor.enforce_row_cap(result.sql, engine_name, settings.MAX_ROWS_RETURNED)
        return GeneratedSQL(sql=capped, cannot_answer_reason=None, raw_response=result.raw_response)
