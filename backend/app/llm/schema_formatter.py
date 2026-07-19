"""Bridges the database layer's schema serializer into the LLM prompt,
narrowing to the relevant subset for large schemas (see schema_loader -
either keyword or vector-search strategy, per settings.SCHEMA_SEARCH_STRATEGY)."""
from __future__ import annotations

from app.core.logger import log
from app.database.introspector import DatabaseSchema
from app.database.schema_loader import get_relevant_tables
from app.database.schema_serializer import serialize_for_llm
from app.utils.text import estimate_token_count

_SCHEMA_TOKEN_BUDGET_WARNING_THRESHOLD = 6000


def format_schema_for_question(
    schema: DatabaseSchema, question: str, *, connection_id: str = "", max_tables: int = 12
) -> str:
    subset = get_relevant_tables(connection_id, schema, question, max_tables=max_tables)
    schema_text = serialize_for_llm(schema, only_tables=subset)

    estimated_tokens = estimate_token_count(schema_text)
    if estimated_tokens > _SCHEMA_TOKEN_BUDGET_WARNING_THRESHOLD:
        log.warning(
            f"Narrowed schema prompt for connection={connection_id} is still large "
            f"(~{estimated_tokens} tokens across {len(subset)} tables) - consider lowering "
            f"max_tables, switching SCHEMA_SEARCH_STRATEGY to 'vector', or excluding "
            f"rarely-queried tables from this connection."
        )

    return schema_text
