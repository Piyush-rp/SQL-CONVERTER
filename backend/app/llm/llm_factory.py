"""
Pluggable LLM factory. Every agent asks this factory for a chat model instead
of importing langchain_openai/langchain_anthropic directly, so switching
providers - per deployment, per connection, or even per request - is a
config change, not a code change.
"""
from __future__ import annotations

from typing import Any

from app.core.config import LLMProvider, settings
from app.core.exceptions import LLMProviderError
from app.llm.llm_config import LLMConfig


def get_chat_model(config: LLMConfig) -> Any:
    """Returns a LangChain-compatible chat model (implements .invoke())."""
    if config.provider == LLMProvider.OPENAI:
        if not settings.OPENAI_API_KEY:
            raise LLMProviderError("OPENAI_API_KEY is not configured")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.resolved_model(),
            temperature=config.temperature,
            api_key=settings.OPENAI_API_KEY,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        )

    if config.provider == LLMProvider.ANTHROPIC:
        if not settings.ANTHROPIC_API_KEY:
            raise LLMProviderError("ANTHROPIC_API_KEY is not configured")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=config.resolved_model(),
            temperature=config.temperature,
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        )

    if config.provider == LLMProvider.GROQ:
        if not settings.GROQ_API_KEY:
            raise LLMProviderError("GROQ_API_KEY is not configured")
        from langchain_openai import ChatOpenAI

        # Groq's API is fully OpenAI-compatible - no separate SDK/LangChain
        # integration needed, just point ChatOpenAI at Groq's base_url with
        # a Groq API key instead of an OpenAI one.
        return ChatOpenAI(
            model=config.resolved_model(),
            temperature=config.temperature,
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
        )

    raise LLMProviderError(f"Unknown LLM provider: {config.provider}")
