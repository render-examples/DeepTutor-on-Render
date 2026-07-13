"""Model catalog is sealed: never persists or exposes an API key."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from deeptutor.services.config.model_catalog import ModelCatalogService


def _legacy_catalog_with_key() -> dict:
    return {
        "version": 1,
        "services": {
            "llm": {
                "active_profile_id": "p1",
                "active_model_id": "m1",
                "profiles": [
                    {
                        "id": "p1",
                        "name": "LLM",
                        "binding": "openai",
                        "api_key": "sk-LEGACY-SECRET",
                        "models": [{"id": "m1", "name": "m", "model": "gpt-4o"}],
                    }
                ],
            }
        },
    }


def test_load_strips_legacy_key_warns_and_resaves(tmp_path: Path, caplog) -> None:
    path = tmp_path / "model_catalog.json"
    path.write_text(json.dumps(_legacy_catalog_with_key()), encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        catalog = ModelCatalogService(path).load()

    # In-memory catalog carries no key...
    assert "api_key" not in catalog["services"]["llm"]["profiles"][0]
    # ...and the file was rewritten clean (hard-cut migration).
    on_disk = path.read_text(encoding="utf-8")
    assert "sk-LEGACY-SECRET" not in on_disk
    assert "api_key" not in on_disk
    # ...and a one-time warning was logged.
    assert any("Stripped a raw API key" in rec.message for rec in caplog.records)


def test_save_never_writes_api_key(tmp_path: Path) -> None:
    path = tmp_path / "model_catalog.json"
    svc = ModelCatalogService(path)
    catalog = svc.load()
    # Smuggle a key into a profile and save.
    catalog["services"]["llm"]["profiles"] = [
        {
            "id": "p1",
            "binding": "openai",
            "api_key": "sk-SMUGGLE",
            "models": [{"id": "m1", "model": "gpt-4o"}],
        }
    ]
    svc.save(catalog)
    assert "sk-SMUGGLE" not in path.read_text(encoding="utf-8")
    assert "api_key" not in path.read_text(encoding="utf-8")


def test_fresh_catalog_has_no_api_key(tmp_path: Path) -> None:
    path = tmp_path / "model_catalog.json"
    ModelCatalogService(path).load()
    assert "api_key" not in path.read_text(encoding="utf-8")
