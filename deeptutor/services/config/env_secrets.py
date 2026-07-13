"""Environment-only secret resolution — the single choke point for API keys.

DeepTutor sources every provider secret **exclusively** from environment
variables. No secret is ever read from, or written to, the on-disk config
(``model_catalog.json`` and friends), and no secret is ever returned to the
browser. This module maps a provider to its env-var name(s) and reads the
value from ``os.environ``.

Design note: this module imports only ``provider_registry`` (never
``provider_runtime``) to avoid an import cycle — ``provider_runtime`` imports
from here.
"""

from __future__ import annotations

import os

from deeptutor.services.provider_registry import (
    canonical_provider_name,
    find_by_name,
)

# Known env-var names for non-LLM providers (embeddings, search, tts/stt, …)
# that are NOT in the LLM ProviderSpec registry. Names that DO appear in the
# LLM registry are resolved via the registry first (see generic_env_var_for),
# so a single OPENAI_API_KEY covers LLM + embeddings + TTS + image gen.
_GENERIC_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cohere": "COHERE_API_KEY",
    "jina": "JINA_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "brave": "BRAVE_API_KEY",
    "exa": "EXA_API_KEY",
    "serper": "SERPER_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
}

# Search providers that never take an API key (keyless engines and the disabled
# sentinel). For these the read-only UI indicator should show nothing rather
# than a fabricated ``{NAME}_API_KEY``. This mirrors the keyless entries in
# ``provider_runtime.SUPPORTED_SEARCH_PROVIDERS``; it is duplicated here (rather
# than imported) because ``provider_runtime`` imports from this module.
_KEYLESS_SEARCH_PROVIDERS: frozenset[str] = frozenset({"duckduckgo", "searxng", "none"})


def llm_env_vars(provider: str | None) -> list[str]:
    """Env-var names that supply an LLM provider's key.

    Returns ``spec.env_key`` followed by the names in ``env_extras``, skipping
    blanks. Local (ollama/vllm/lm_studio) and OAuth (openai_codex/
    github_copilot) providers do not use an API key from the environment, so
    they return ``[]``.
    """
    spec = find_by_name(provider)
    if spec is None:
        return []
    if spec.is_local or spec.is_oauth:
        return []
    names: list[str] = []
    if spec.env_key:
        names.append(spec.env_key)
    for extra_name, _template in spec.env_extras:
        if extra_name and extra_name not in names:
            names.append(extra_name)
    return names


def generic_env_var_for(provider: str | None) -> str | None:
    """The single env-var name for a non-LLM provider (embedding/search/…).

    Collision rule: if the provider is also a known LLM provider with an
    ``env_key``, prefer that env key so one OPENAI_API_KEY covers every
    OpenAI-backed service. Otherwise use the known-provider table, falling
    back to the ``{NAME}_API_KEY`` convention.
    """
    canonical = canonical_provider_name(provider)
    if not canonical:
        return None
    spec = find_by_name(canonical)
    if spec is not None and spec.env_key and not (spec.is_local or spec.is_oauth):
        return spec.env_key
    if canonical in _GENERIC_ENV_VARS:
        return _GENERIC_ENV_VARS[canonical]
    return f"{canonical.upper()}_API_KEY"


def resolve_secret(*env_vars: str | None) -> str:
    """Return the first non-empty value among the given env vars, else ``""``."""
    for name in env_vars:
        if not name:
            continue
        value = os.environ.get(name, "")
        if value:
            return value
    return ""


def secret_is_set(*env_vars: str | None) -> bool:
    """True if any of the given env vars holds a non-empty value."""
    return bool(resolve_secret(*env_vars))


def env_vars_for(service: str, profile: dict | None) -> list[str]:
    """All env-var names that supply a profile's secret.

    ``service`` is one of ``llm``/``embedding``/``tts``/``stt``/``imagegen``/
    ``videogen``/``search``. LLM profiles key on ``binding`` and use the LLM
    registry (which may return several names, e.g. zhipu); search profiles key
    on ``provider``; everything else keys on ``binding`` via the generic
    convention. Returns ``[]`` when no env var applies (e.g. a local provider).
    """
    profile = profile or {}
    if service == "llm":
        return llm_env_vars(profile.get("binding"))
    if service == "search":
        provider = profile.get("provider")
        # Keyless engines (duckduckgo/searxng) and the disabled sentinel never
        # use a key, so report no env var instead of a fabricated one.
        if (provider or "").strip().lower() in _KEYLESS_SEARCH_PROVIDERS:
            return []
    else:
        provider = profile.get("binding")
    name = generic_env_var_for(provider)
    return [name] if name else []


def env_var_name_for(service: str, profile: dict | None) -> str:
    """The single display env-var name for the read-only UI indicator.

    Returns ``""`` when no env var applies (e.g. a local LLM provider).
    """
    names = env_vars_for(service, profile)
    return names[0] if names else ""
