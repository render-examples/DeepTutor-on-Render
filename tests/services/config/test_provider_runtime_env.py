"""Catalog-sourced secrets resolve from the environment, not the profile."""

from __future__ import annotations

from deeptutor.services.config.provider_runtime import (
    resolve_embedding_runtime_config,
    resolve_llm_runtime_config,
    resolve_search_runtime_config,
)


def _llm_catalog(binding: str = "openai", model: str = "gpt-4o-mini") -> dict:
    return {
        "version": 1,
        "services": {
            "llm": {
                "active_profile_id": "p1",
                "active_model_id": "m1",
                "profiles": [
                    {
                        "id": "p1",
                        "binding": binding,
                        # A stale key on the profile must be ignored entirely.
                        "api_key": "sk-DISK-IGNORED",
                        "models": [{"id": "m1", "model": model}],
                    }
                ],
            }
        },
    }


def test_llm_key_comes_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    cfg = resolve_llm_runtime_config(_llm_catalog())
    assert cfg.api_key == "sk-from-env"


def test_llm_key_empty_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = resolve_llm_runtime_config(_llm_catalog())
    assert cfg.api_key == ""


def test_azure_openai_llm_key_comes_from_env(monkeypatch) -> None:
    # Azure OpenAI is a direct provider whose key must resolve from
    # AZURE_OPENAI_API_KEY (regression: the spec previously had a blank env_key,
    # so an Azure LLM binding silently resolved to no key).
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-from-env")
    catalog = _llm_catalog(binding="azure_openai", model="gpt-4o")
    catalog["services"]["llm"]["profiles"][0]["base_url"] = "https://example.openai.azure.com"
    cfg = resolve_llm_runtime_config(catalog)
    assert cfg.api_key == "azure-from-env"


def test_local_llm_still_gets_no_key_required(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    catalog = _llm_catalog(binding="ollama", model="llama3")
    catalog["services"]["llm"]["profiles"][0]["base_url"] = "http://localhost:11434/v1"
    cfg = resolve_llm_runtime_config(catalog)
    assert cfg.api_key == "sk-no-key-required"


def test_empty_catalog_llm_key_resolves_openai_from_env(monkeypatch) -> None:
    # Regression: with no configured profile the resolver defaults to
    # openai/gpt-5.6-luna by model name but must still read OPENAI_API_KEY for
    # the *resolved* provider instead of leaving the key empty (which fell back
    # to the "sk-no-key-required" sentinel and 401'd against platform.openai.com).
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-real")
    empty = {
        "version": 1,
        "services": {
            "llm": {"active_profile_id": None, "active_model_id": None, "profiles": []}
        },
    }
    cfg = resolve_llm_runtime_config(empty)
    assert cfg.provider_name == "openai"
    assert cfg.api_key == "sk-env-real"


def test_empty_catalog_llm_key_never_sentinel_for_openai(monkeypatch) -> None:
    # With no env key and no profile, openai (non-local) must not receive the
    # local-only sentinel — it stays empty so the failure is an honest "no key".
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    empty = {
        "version": 1,
        "services": {
            "llm": {"active_profile_id": None, "active_model_id": None, "profiles": []}
        },
    }
    cfg = resolve_llm_runtime_config(empty)
    assert cfg.provider_name == "openai"
    assert cfg.api_key == ""


def test_embedding_key_resolves_resolved_provider_from_env(monkeypatch) -> None:
    # A profile without an explicit binding still resolves to openai by model
    # keyword; the key must come from OPENAI_API_KEY for that resolved provider.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-emb-env")
    catalog = {
        "version": 1,
        "services": {
            "embedding": {
                "active_profile_id": "e1",
                "active_model_id": "em1",
                "profiles": [
                    {
                        "id": "e1",
                        "binding": "",
                        "models": [{"id": "em1", "model": "text-embedding-3-small"}],
                    }
                ],
            }
        },
    }
    cfg = resolve_embedding_runtime_config(catalog)
    assert cfg.provider_name == "openai"
    assert cfg.api_key == "sk-emb-env"


def test_search_key_comes_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-from-env")
    catalog = {
        "version": 1,
        "services": {
            "search": {
                "active_profile_id": "s1",
                "profiles": [
                    {"id": "s1", "provider": "tavily", "api_key": "DISK-IGNORED", "models": []}
                ],
            }
        },
    }
    cfg = resolve_search_runtime_config(catalog)
    assert cfg.api_key == "tvly-from-env"
