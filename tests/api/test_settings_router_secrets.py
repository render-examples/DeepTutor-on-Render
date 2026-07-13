"""Settings router never leaks a key and surfaces env-var indicators."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from deeptutor.api import main as api_main
from deeptutor.api.routers import settings as settings_router
from deeptutor.services.config.model_catalog import ModelCatalogService


@pytest.fixture
def client() -> TestClient:
    return TestClient(api_main.app)


@pytest.fixture
def tmp_catalog(tmp_path: Path, monkeypatch) -> ModelCatalogService:
    svc = ModelCatalogService(tmp_path / "model_catalog.json")
    monkeypatch.setattr(settings_router, "get_model_catalog_service", lambda: svc)
    return svc


def _seed(svc: ModelCatalogService) -> None:
    catalog = svc.load()
    catalog["services"]["llm"] = {
        "active_profile_id": "p1",
        "active_model_id": "m1",
        "profiles": [
            {"id": "p1", "binding": "openai", "models": [{"id": "m1", "model": "gpt-4o-mini"}]}
        ],
    }
    svc.save(catalog)


def test_get_catalog_has_no_key_but_has_indicators(client, tmp_catalog, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live")
    _seed(tmp_catalog)

    resp = client.get("/api/v1/settings/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert "sk-live" not in json.dumps(body)
    profile = body["catalog"]["services"]["llm"]["profiles"][0]
    assert "api_key" not in profile
    assert profile["api_key_set"] is True
    assert profile["api_key_env_var"] == "OPENAI_API_KEY"


def test_get_catalog_indicator_false_when_env_unset(client, tmp_catalog, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _seed(tmp_catalog)

    body = client.get("/api/v1/settings/catalog").json()
    profile = body["catalog"]["services"]["llm"]["profiles"][0]
    assert profile["api_key_set"] is False
    assert profile["api_key_env_var"] == "OPENAI_API_KEY"


def test_put_catalog_with_body_key_stores_none(client, tmp_catalog) -> None:
    payload = {
        "catalog": {
            "version": 1,
            "services": {
                "llm": {
                    "active_profile_id": "p1",
                    "active_model_id": "m1",
                    "profiles": [
                        {
                            "id": "p1",
                            "binding": "openai",
                            "api_key": "sk-SMUGGLE",
                            "models": [{"id": "m1", "model": "gpt-4o-mini"}],
                        }
                    ],
                }
            },
        }
    }
    resp = client.put("/api/v1/settings/catalog", json=payload)
    assert resp.status_code == 200
    # Response never echoes the key...
    assert "sk-SMUGGLE" not in json.dumps(resp.json())
    # ...and nothing was written to disk.
    assert "sk-SMUGGLE" not in tmp_catalog.path.read_text(encoding="utf-8")
    assert "api_key" not in tmp_catalog.path.read_text(encoding="utf-8")
