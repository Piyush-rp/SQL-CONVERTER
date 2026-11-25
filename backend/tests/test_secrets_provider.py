"""
Tests for the pluggable secrets provider. The env-based provider is tested
directly; the Vault provider is tested against a MOCKED hvac client rather
than a real Vault server - there's no Vault instance available to test
against here (unlike Postgres/MySQL/Redis, which really were installed and
tested live - see test_live_databases.py / test_redis_scaling.py). This
proves the integration *logic* is correct; a live Vault round-trip still
needs to be verified against your actual Vault deployment before relying
on it.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.secrets import EnvSecretsProvider, VaultSecretsProvider


class FakeSettings:
    SECRET_KEY = "env-secret"
    OPENAI_API_KEY = "env-openai-key"
    ANTHROPIC_API_KEY = ""


def test_env_provider_reads_from_settings():
    provider = EnvSecretsProvider(FakeSettings())
    assert provider.get("SECRET_KEY") == "env-secret"
    assert provider.get("ANTHROPIC_API_KEY", "fallback") == ""  # empty string IS the value, not missing
    assert provider.get("NONEXISTENT_FIELD", "fallback") == "fallback"


def test_vault_provider_fetches_and_caches_secrets():
    fake_hvac_client = MagicMock()
    fake_hvac_client.is_authenticated.return_value = True
    fake_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"SECRET_KEY": "vault-secret-key", "OPENAI_API_KEY": "vault-openai-key"}}
    }

    with patch("hvac.Client", return_value=fake_hvac_client):
        provider = VaultSecretsProvider(
            vault_addr="http://vault.internal:8200", vault_token="test-token",
            mount_point="secret", secret_path="sqlcopilot",
        )
        assert provider.get("SECRET_KEY") == "vault-secret-key"
        assert provider.get("OPENAI_API_KEY") == "vault-openai-key"
        assert provider.get("ANTHROPIC_API_KEY", "default-fallback") == "default-fallback"

        # cached after first read - a second call must not hit Vault again
        provider.get("SECRET_KEY")
        assert fake_hvac_client.secrets.kv.v2.read_secret_version.call_count == 1


def test_vault_provider_fails_safe_when_unauthenticated():
    fake_hvac_client = MagicMock()
    fake_hvac_client.is_authenticated.return_value = False

    with patch("hvac.Client", return_value=fake_hvac_client):
        provider = VaultSecretsProvider(
            vault_addr="http://vault.internal:8200", vault_token="bad-token",
            mount_point="secret", secret_path="sqlcopilot",
        )
        # never raises - falls back to the caller's default instead of
        # crashing app startup over an auth failure
        assert provider.get("SECRET_KEY", "fallback-key") == "fallback-key"


def test_vault_provider_fails_safe_on_connection_error():
    fake_hvac_client = MagicMock()
    fake_hvac_client.is_authenticated.side_effect = ConnectionError("Vault unreachable")

    with patch("hvac.Client", return_value=fake_hvac_client):
        provider = VaultSecretsProvider(
            vault_addr="http://unreachable:8200", vault_token="x",
            mount_point="secret", secret_path="sqlcopilot",
        )
        assert provider.get("SECRET_KEY", "fallback-key") == "fallback-key"


def test_get_secrets_provider_factory_selects_env_by_default():
    from app.core.secrets import get_secrets_provider

    fake_settings = FakeSettings()
    fake_settings.SECRETS_PROVIDER = "env"
    provider = get_secrets_provider(fake_settings)
    assert isinstance(provider, EnvSecretsProvider)


def test_get_secrets_provider_factory_selects_vault_when_configured():
    from app.core.secrets import get_secrets_provider

    fake_settings = FakeSettings()
    fake_settings.SECRETS_PROVIDER = "vault"
    fake_settings.VAULT_ADDR = "http://vault.internal:8200"
    fake_settings.VAULT_TOKEN = "token"
    fake_settings.VAULT_MOUNT_POINT = "secret"
    fake_settings.VAULT_SECRET_PATH = "sqlcopilot"

    with patch("hvac.Client", return_value=MagicMock()):
        provider = get_secrets_provider(fake_settings)
        assert isinstance(provider, VaultSecretsProvider)
