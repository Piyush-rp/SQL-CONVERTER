"""
LLM factory. Every agent asks this factory for a chat model instead of
building one directly, so model/provider settings live in one place.

Groq is the only provider. Its API is OpenAI-compatible, so the model is a
LangChain ChatOpenAI client pointed at Groq's base URL with a Groq API key -
no OpenAI account or key is involved.
"""
from __future__ import annotations

from typing import Any

from app.core.config import LLMProvider, settings
from app.core.exceptions import LLMProviderError
from app.llm.llm_config import LLMConfig

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def get_chat_model(config: LLMConfig) -> Any:
    """Returns a LangChain-compatible chat model (implements .invoke())."""
    if config.provider != LLMProvider.GROQ:
        raise LLMProviderError(f"Unknown LLM provider: {config.provider}")
    if not settings.GROQ_API_KEY:
        raise LLMProviderError("GROQ_API_KEY is not configured")

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=config.resolved_model(),
        temperature=config.temperature,
        api_key=settings.GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )
