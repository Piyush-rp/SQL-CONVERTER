"""
Pluggable secrets provider: environment variables (default) or HashiCorp
Vault. This exists so SECRET_KEY / GROQ_API_KEY can
live in a real secrets manager instead of a .env file, for deployments
that require it - without changing how
anything else in the app reads `settings.*`.

Only these three fields are ever sourced from Vault; everything else
(non-sensitive config, and target-database credentials, which are
encrypted at rest per-connection - see app/core/crypto.py) is unaffected.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.utils.retry import retry_with_backoff

if TYPE_CHECKING:
    from app.core.config import Settings


class SecretsProvider(Protocol):
    def get(self, key: str, default: str = "") -> str: ...


class EnvSecretsProvider:
    """No-op passthrough - env vars are already loaded into Settings by
    pydantic-settings, so this just returns what's already there."""

    def __init__(self, settings_obj: "Settings"):
        self._settings = settings_obj

    def get(self, key: str, default: str = "") -> str:
        return getattr(self._settings, key, default)


class VaultSecretsProvider:
    """Reads from Vault's KV v2 secrets engine, at a single path holding
    all of this app's secrets as a flat key-value map (e.g. a `vault kv put
    secret/sqlcopilot SECRET_KEY=... GROQ_API_KEY=...`). Fails safe: any
    error talking to Vault falls back to the caller-supplied default rather
    than crashing startup, since a misconfigured/unreachable Vault
    shouldn't take down the whole app if env vars also happen to be set as
    a fallback."""

    def __init__(self, vault_addr: str, vault_token: str, mount_point: str, secret_path: str):
        import hvac

        self._client = hvac.Client(url=vault_addr, token=vault_token)
        self._mount_point = mount_point
        self._secret_path = secret_path
        self._cache: dict[str, str] | None = None

    def _load(self) -> dict:
        if self._cache is not None:
            return self._cache
        try:
            if not self._client.is_authenticated():
                self._cache = {}
                return self._cache
            self._cache = self._read_secret_with_retry()
        except Exception:
            self._cache = {}
        return self._cache

    @retry_with_backoff(max_attempts=3, base_delay_seconds=0.5, exceptions=(ConnectionError, TimeoutError, OSError))
    def _read_secret_with_retry(self) -> dict:
        response = self._client.secrets.kv.v2.read_secret_version(
            path=self._secret_path, mount_point=self._mount_point, raise_on_deleted_version=True
        )
        return response["data"]["data"]

    def get(self, key: str, default: str = "") -> str:
        return self._load().get(key, default)


def get_secrets_provider(settings_obj: "Settings") -> SecretsProvider:
    if settings_obj.SECRETS_PROVIDER == "vault":
        return VaultSecretsProvider(
            vault_addr=settings_obj.VAULT_ADDR,
            vault_token=settings_obj.VAULT_TOKEN,
            mount_point=settings_obj.VAULT_MOUNT_POINT,
            secret_path=settings_obj.VAULT_SECRET_PATH,
        )
    return EnvSecretsProvider(settings_obj)
