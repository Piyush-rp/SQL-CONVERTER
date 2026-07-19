"""Composes the final message list sent to the chat model: system prompt
(with schema + dialect rules) + few-shot examples + prior conversation
turns for this session (if any) + the user's question, and optionally a
retry suffix carrying the previous attempt's validation error."""
from __future__ import annotations

from typing import List, Optional, TypedDict

from app.prompts.examples import FEW_SHOT_EXAMPLES
from app.prompts.templates import CONVERSATION_CONTEXT_PREFIX, RETRY_SYSTEM_SUFFIX, SYSTEM_PROMPT

_DIALECT_DISPLAY = {
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mssql": "SQL Server (T-SQL)",
    "sqlite": "SQLite",
}


class ChatMessage(TypedDict):
    role: str
    content: str


class PromptBuilder:
    @staticmethod
    def build(
        *,
        question: str,
        schema_text: str,
        engine_name: str,
        previous_sql: Optional[str] = None,
        previous_error: Optional[str] = None,
        include_examples: bool = True,
        conversation_turns: Optional[list] = None,
    ) -> List[ChatMessage]:
        dialect_display = _DIALECT_DISPLAY.get(engine_name, engine_name)
        system = SYSTEM_PROMPT.format(dialect=dialect_display, schema=schema_text)

        if previous_sql and previous_error:
            system += RETRY_SYSTEM_SUFFIX.format(previous_sql=previous_sql, error=previous_error)

        messages: List[ChatMessage] = [{"role": "system", "content": system}]

        if include_examples:
            for ex in FEW_SHOT_EXAMPLES:
                messages.append({"role": "user", "content": ex["question"]})
                messages.append({"role": "assistant", "content": f"```sql\n{ex['sql']}\n```"})

        if conversation_turns:
            # Real prior turns from THIS conversation, distinct from the
            # generic few-shot examples above - these give the model actual
            # context to resolve "and by region?" against, e.g. what "it"
            # or an implied subject refers to from the previous question.
            messages.append({"role": "system", "content": CONVERSATION_CONTEXT_PREFIX})
            for turn in conversation_turns:
                messages.append({"role": "user", "content": turn.question})
                if turn.sql:
                    messages.append({"role": "assistant", "content": f"```sql\n{turn.sql}\n```"})

        messages.append({"role": "user", "content": question})
        return messages
