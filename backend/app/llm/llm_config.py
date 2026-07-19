"""Runtime-selectable LLM configuration. A connection (or a single request)
can pick OpenAI or Anthropic independently of the deployment default."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import LLMProvider, settings


@dataclass
class LLMConfig:
    provider: LLMProvider = settings.DEFAULT_LLM_PROVIDER
    model: Optional[str] = None
    temperature: float = settings.LLM_TEMPERATURE
    max_retries: int = settings.LLM_MAX_RETRIES
    timeout_seconds: int = settings.LLM_REQUEST_TIMEOUT_SECONDS

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        if self.provider == LLMProvider.OPENAI:
            return settings.OPENAI_MODEL
        if self.provider == LLMProvider.GROQ:
            return settings.GROQ_MODEL
        return settings.ANTHROPIC_MODEL