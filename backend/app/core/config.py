"""
Application configuration.

Settings are loaded from environment variables / a .env file. Nothing here
is hard-coded so the same image can run in dev, staging and prod by only
changing environment variables (12-factor).
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"



class Settings(BaseSettings):
    # --- App metadata -----------------------------------------------------
    APP_NAME: str = "AI SQL Copilot"
    VERSION: str = "1.0.0"
    ENVIRONMENT: Environment = Environment.DEV
    API_PREFIX: str = "/api/v1"

    # --- Metadata database (users, saved connections, query history) ------
    # This is Copilot's OWN database, separate from the customer databases
    # users connect to and query in natural language.
    DATABASE_URL: str = "sqlite:///./app_metadata.db"

    # --- Auth ---------------------------------------------------------------
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 2880  # 2 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # --- LLM providers (pluggable) -------------------------------------------
    DEFAULT_LLM_PROVIDER: LLMProvider = LLMProvider.OPENAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_RETRIES: int = 2
    LLM_REQUEST_TIMEOUT_SECONDS: int = 30

    # --- Query execution safety guards --------------------------------------
    MAX_ROWS_RETURNED: int = 1000
    QUERY_TIMEOUT_SECONDS: int = 15
    ALLOW_WRITE_QUERIES: bool = False  # INSERT/UPDATE/DELETE/DDL blocked unless True
    MAX_AGENT_RETRIES: int = 2  # SQL-generation self-correction attempts

    # --- Schema cache ---------------------------------------------------------
    SCHEMA_CACHE_TTL_SECONDS: int = 300

    # --- Schema search strategy for narrowing large schemas to the LLM prompt --
    # "keyword": exact token overlap between the question and table/column
    #   names (app.database.schema_loader.relevant_subset) - zero setup cost,
    #   works well for small-to-medium schemas.
    # "vector": TF-IDF + FAISS embedding search (app.vectorstore) - better
    #   recall on large schemas where the question's wording doesn't share
    #   exact tokens with a relevant table's name (see docs/roadmap.md item 12).
    SCHEMA_SEARCH_STRATEGY: str = "keyword"

    # --- Agentic tool-calling generation (app.tools) ---------------------------
    # When enabled, SQL generation binds schema-lookup/validate/exploratory-
    # query tools to the model and runs a bounded tool-call loop instead of
    # a single-shot prompt. Requires a tool-calling-capable model (both
    # OpenAI and Anthropic's current chat models qualify). Off by default -
    # it's a real quality upgrade on complex/ambiguous questions but costs
    # extra round-trips, so it's opt-in rather than forced on every request.
    ENABLE_TOOL_CALLING: bool = False
    MAX_TOOL_CALL_ITERATIONS: int = 5

    # --- Redis (optional) -----------------------------------------------------
    # If set, the schema cache and rate limiter use Redis instead of an
    # in-process dict, so multiple backend replicas share one consistent
    # view instead of each tracking its own (see docs/scaling.md). Leave
    # unset for a single-instance deployment - everything still works,
    # just without cross-instance consistency.
    REDIS_URL: str = ""

    # --- Secrets provider (optional) -------------------------------------------
    # "env" (default) reads SECRET_KEY/OPENAI_API_KEY/ANTHROPIC_API_KEY from
    # environment variables/.env, same as everything else in this file.
    # "vault" overlays those specific fields from HashiCorp Vault's KV v2
    # engine after startup (see app/core/secrets.py) - enable for
    # deployments that centralize secrets instead of using env vars/.env
    # files directly (see docs/roadmap.md item 3).
    SECRETS_PROVIDER: str = "env"
    VAULT_ADDR: str = ""
    VAULT_TOKEN: str = ""
    VAULT_MOUNT_POINT: str = "secret"
    VAULT_SECRET_PATH: str = "sqlcopilot"

    # --- CORS -----------------------------------------------------------------
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- Rate limiting ----------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Logging ------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False
    LOG_TO_FILE: bool = True  # writes to logs/app.log in addition to stdout - see app/core/logger.py

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set_in_prod(cls, v: str, info):
        # In prod, refuse to boot on the placeholder secret.
        env = info.data.get("ENVIRONMENT")
        if env == Environment.PROD and v == "CHANGE_ME_IN_PRODUCTION":
            raise ValueError(
                "SECRET_KEY must be overridden via environment variable in production"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    settings_obj = Settings()

    # Env vars/.env are always the baseline (so a partially-configured Vault
    # never leaves a field silently empty) - Vault, when enabled, overlays
    # just the sensitive fields on top. See app/core/secrets.py.
    if settings_obj.SECRETS_PROVIDER == "vault":
        from app.core.secrets import get_secrets_provider

        provider = get_secrets_provider(settings_obj)
        settings_obj.SECRET_KEY = provider.get("SECRET_KEY", settings_obj.SECRET_KEY)
        settings_obj.OPENAI_API_KEY = provider.get("OPENAI_API_KEY", settings_obj.OPENAI_API_KEY)
        settings_obj.ANTHROPIC_API_KEY = provider.get("ANTHROPIC_API_KEY", settings_obj.ANTHROPIC_API_KEY)

    return settings_obj


settings = get_settings()
