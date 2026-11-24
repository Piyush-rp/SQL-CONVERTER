"""Runtime LLM configuration. Groq is the only provider; a request can still
override the model, temperature, retries or timeout."""
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
        return self.model or settings.GROQ_MODEL
