from __future__ import annotations

from types import SimpleNamespace

import pytest

from deeptutor.api.routers import system as system_router


def _stub_status(monkeypatch, *, api_key: str, provider_mode: str = "standard") -> None:
    monkeypatch.setattr(system_router, "get_current_user", lambda: SimpleNamespace(is_admin=True))
    monkeypatch.setattr(
        system_router,
        "get_llm_config",
        lambda: SimpleNamespace(model="gpt-4o-mini", api_key=api_key, provider_mode=provider_mode),
    )
    monkeypatch.setattr(
        system_router,
        "get_embedding_config",
        lambda: SimpleNamespace(model="embed-test"),
    )
    monkeypatch.setattr(
        system_router,
        "resolve_search_runtime_config",
        lambda: SimpleNamespace(
            requested_provider="none",
            provider="none",
            unsupported_provider=False,
            deprecated_provider=False,
            missing_credentials=False,
            fallback_reason=None,
        ),
    )


@pytest.mark.asyncio
async def test_status_not_configured_when_llm_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_status(monkeypatch, api_key="")

    result = await system_router.get_system_status()

    assert result["llm"]["status"] == "not_configured"
    assert result["llm"]["testable"] is False


@pytest.mark.asyncio
async def test_status_configured_when_llm_key_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_status(monkeypatch, api_key="sk-real")

    result = await system_router.get_system_status()

    assert result["llm"]["status"] == "configured"
    assert result["llm"]["testable"] is True


@pytest.mark.asyncio
async def test_status_configured_for_oauth_provider_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # OAuth providers legitimately carry no API key; status must not claim they
    # are unconfigured.
    _stub_status(monkeypatch, api_key="", provider_mode="oauth")

    result = await system_router.get_system_status()

    assert result["llm"]["status"] == "configured"


@pytest.mark.asyncio
async def test_embeddings_connection_uses_batch_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, list[str]] = {}

    class _FakeClient:
        async def embed(self, texts: list[str]):
            captured["texts"] = texts
            return [[0.1, 0.2], [0.3, 0.4]]

    monkeypatch.setattr(
        system_router,
        "get_embedding_config",
        lambda: SimpleNamespace(model="embed-test", binding="openai"),
    )
    monkeypatch.setattr(system_router, "get_embedding_client", lambda: _FakeClient())

    response = await system_router.test_embeddings_connection()

    assert response.success is True
    assert captured["texts"] == ["test", "retrieval batch probe"]


@pytest.mark.asyncio
async def test_embeddings_connection_rejects_partial_batch_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        async def embed(self, texts: list[str]):
            return [[0.1, 0.2]]

    monkeypatch.setattr(
        system_router,
        "get_embedding_config",
        lambda: SimpleNamespace(model="embed-test", binding="openai"),
    )
    monkeypatch.setattr(system_router, "get_embedding_client", lambda: _FakeClient())

    response = await system_router.test_embeddings_connection()

    assert response.success is False
    assert response.message == "Embeddings connection failed: Invalid response"
