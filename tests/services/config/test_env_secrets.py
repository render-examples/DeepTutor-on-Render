"""Tests for the environment-only secret choke point."""

from __future__ import annotations

from deeptutor.services.config import env_secrets


def test_llm_env_vars_openai() -> None:
    assert env_secrets.llm_env_vars("openai") == ["OPENAI_API_KEY"]


def test_llm_env_vars_walks_env_extras_for_zhipu() -> None:
    # zhipu is the one registry provider with env_extras.
    assert env_secrets.llm_env_vars("zhipu") == ["ZAI_API_KEY", "ZHIPUAI_API_KEY"]


def test_llm_env_vars_alias_resolves() -> None:
    # "claude" is an alias for anthropic.
    assert env_secrets.llm_env_vars("claude") == ["ANTHROPIC_API_KEY"]


def test_llm_env_vars_local_and_oauth_are_empty() -> None:
    assert env_secrets.llm_env_vars("ollama") == []
    assert env_secrets.llm_env_vars("vllm") == []
    assert env_secrets.llm_env_vars("lm_studio") == []
    assert env_secrets.llm_env_vars("openai_codex") == []
    assert env_secrets.llm_env_vars("github_copilot") == []


def test_llm_env_vars_unknown_provider() -> None:
    assert env_secrets.llm_env_vars("totally-made-up") == []
    assert env_secrets.llm_env_vars(None) == []


def test_generic_env_var_known_table() -> None:
    assert env_secrets.generic_env_var_for("tavily") == "TAVILY_API_KEY"
    assert env_secrets.generic_env_var_for("cohere") == "COHERE_API_KEY"


def test_generic_env_var_unknown_falls_back_to_convention() -> None:
    assert env_secrets.generic_env_var_for("acme") == "ACME_API_KEY"


def test_generic_env_var_collision_collapses_onto_llm_env_key() -> None:
    # A name that is also an LLM provider prefers the registry env key, so one
    # OPENAI_API_KEY covers LLM + embeddings + TTS.
    assert env_secrets.generic_env_var_for("openai") == "OPENAI_API_KEY"
    assert env_secrets.generic_env_var_for("gemini") == "GEMINI_API_KEY"


def test_resolve_secret_first_non_empty(monkeypatch) -> None:
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.setenv("ZHIPUAI_API_KEY", "z-second")
    assert env_secrets.resolve_secret("ZAI_API_KEY", "ZHIPUAI_API_KEY") == "z-second"


def test_resolve_secret_none_set(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert env_secrets.resolve_secret("OPENAI_API_KEY") == ""
    assert env_secrets.resolve_secret() == ""


def test_secret_is_set(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert env_secrets.secret_is_set("OPENAI_API_KEY") is True
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert env_secrets.secret_is_set("OPENAI_API_KEY") is False


def test_env_vars_for_and_display_name() -> None:
    assert env_secrets.env_vars_for("llm", {"binding": "zhipu"}) == [
        "ZAI_API_KEY",
        "ZHIPUAI_API_KEY",
    ]
    assert env_secrets.env_var_name_for("llm", {"binding": "zhipu"}) == "ZAI_API_KEY"
    assert env_secrets.env_vars_for("search", {"provider": "tavily"}) == ["TAVILY_API_KEY"]
    assert env_secrets.env_vars_for("embedding", {"binding": "openai"}) == ["OPENAI_API_KEY"]
    # Local LLM provider → no env var to display.
    assert env_secrets.env_var_name_for("llm", {"binding": "ollama"}) == ""


def test_env_vars_for_keyless_search_providers() -> None:
    # duckduckgo/searxng are keyless and "none" is disabled — no fabricated var.
    assert env_secrets.env_vars_for("search", {"provider": "duckduckgo"}) == []
    assert env_secrets.env_vars_for("search", {"provider": "SearXNG"}) == []
    assert env_secrets.env_vars_for("search", {"provider": "none"}) == []
    assert env_secrets.env_var_name_for("search", {"provider": "duckduckgo"}) == ""
