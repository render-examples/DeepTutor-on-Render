"""Tests for FastAPI CORS settings."""

from __future__ import annotations

from fastapi.testclient import TestClient

from deeptutor.api import main as api_main


def _reset_cors_env(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    monkeypatch.delenv("CORS_ORIGIN", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOW_ALL", raising=False)


def test_cors_explicit_by_default(monkeypatch) -> None:
    """Fresh deploy: no wildcard, only localhost is trusted out of the box."""
    _reset_cors_env(monkeypatch)
    monkeypatch.setenv("FRONTEND_PORT", "3782")

    settings = api_main._build_cors_settings()

    assert settings["allow_origin_regex"] is None
    assert settings["mode"] == "explicit"
    assert "http://localhost:3782" in settings["allow_origins"]
    assert "http://127.0.0.1:3782" in settings["allow_origins"]


def test_cors_allows_all_origins_when_opted_in(monkeypatch) -> None:
    """CORS_ALLOW_ALL restores the permissive LAN behavior on demand."""
    _reset_cors_env(monkeypatch)
    monkeypatch.setenv("FRONTEND_PORT", "3782")
    monkeypatch.setenv("CORS_ALLOW_ALL", "true")

    settings = api_main._build_cors_settings()

    assert settings["allow_origin_regex"] == r"https?://.*"
    assert settings["mode"] == "permissive"
    assert "http://localhost:3782" in settings["allow_origins"]


def test_cors_uses_explicit_origins(monkeypatch) -> None:
    _reset_cors_env(monkeypatch)
    monkeypatch.setenv("CORS_ORIGIN", "https://app.example.com/")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://foo.example.com, https://bar.example.com\nhttps://foo.example.com",
    )

    settings = api_main._build_cors_settings()

    assert settings["allow_origin_regex"] is None
    assert "https://app.example.com" in settings["allow_origins"]
    assert "https://foo.example.com" in settings["allow_origins"]
    assert "https://bar.example.com" in settings["allow_origins"]
    assert settings["allow_origins"].count("https://foo.example.com") == 1


def test_cors_normalizes_common_origin_input_mistakes(monkeypatch) -> None:
    _reset_cors_env(monkeypatch)
    monkeypatch.setenv(
        "CORS_ORIGIN",
        "172.26.0.10:3782; https://learn.example.com/app/",
    )
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000;api.example.com")

    settings = api_main._build_cors_settings()

    assert settings["allow_origin_regex"] is None
    assert "http://172.26.0.10:3782" in settings["allow_origins"]
    assert "https://learn.example.com" in settings["allow_origins"]
    assert "http://api.example.com" in settings["allow_origins"]


def test_cors_preflight_allows_partner_patch_save() -> None:
    client = TestClient(api_main.app)

    response = client.options(
        "/api/v1/partners/partner",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    allowed_methods = {
        method.strip() for method in response.headers["access-control-allow-methods"].split(",")
    }
    assert "PATCH" in allowed_methods
