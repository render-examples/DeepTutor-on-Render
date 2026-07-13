"""Runtime settings are sealed: secrets resolve from env, never hit disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.services.config.runtime_settings import RuntimeSettingsService

# (loader, env var, secret field) for each env-only secret.
_CASES = [
    ("load_mineru", "MINERU_API_TOKEN", "api_token"),
    ("load_pageindex", "PAGEINDEX_API_KEY", "api_key"),
    ("load_auth", "AUTH_PASSWORD_HASH", "password_hash"),
    ("load_integrations", "POCKETBASE_ADMIN_PASSWORD", "pocketbase_admin_password"),
]


@pytest.mark.parametrize("loader,env_var,field", _CASES)
def test_secret_resolves_from_env_and_disk_stays_empty(
    tmp_path: Path, loader: str, env_var: str, field: str
) -> None:
    svc = RuntimeSettingsService(tmp_path, process_env={env_var: "ZZ-SECRET-ZZ"})
    payload = getattr(svc, loader)()
    assert payload[field] == "ZZ-SECRET-ZZ"
    for file in tmp_path.glob("*.json"):
        assert "ZZ-SECRET-ZZ" not in file.read_text(encoding="utf-8")


@pytest.mark.parametrize("loader,env_var,field", _CASES)
def test_secret_resolves_even_with_process_overrides_disabled(
    tmp_path: Path, loader: str, env_var: str, field: str
) -> None:
    # Docker/Render set DEEPTUTOR_IGNORE_PROCESS_ENV_OVERRIDES=1 to keep the
    # non-secret runtime config JSON-driven; secrets must still resolve.
    env = {"DEEPTUTOR_IGNORE_PROCESS_ENV_OVERRIDES": "1", env_var: "ZZ-SECRET-ZZ"}
    svc = RuntimeSettingsService(tmp_path, process_env=env)
    assert getattr(svc, loader)()[field] == "ZZ-SECRET-ZZ"


def test_save_never_persists_a_secret(tmp_path: Path) -> None:
    svc = RuntimeSettingsService(tmp_path, process_env={})
    svc.save_pageindex({"api_key": "SMUGGLE-PI", "api_base_url": "https://x"})
    svc.save_mineru({"api_token": "SMUGGLE-TOK"})
    svc.save_auth({"password_hash": "SMUGGLE-HASH"})
    svc.save_integrations({"pocketbase_admin_password": "SMUGGLE-PB"})
    for file in tmp_path.glob("*.json"):
        text = file.read_text(encoding="utf-8")
        for smuggled in ("SMUGGLE-PI", "SMUGGLE-TOK", "SMUGGLE-HASH", "SMUGGLE-PB"):
            assert smuggled not in text
