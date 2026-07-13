"""render.yaml must declare every provider env var the registry knows about."""

from __future__ import annotations

from pathlib import Path

import yaml

from deeptutor.services.provider_registry import PROVIDERS

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RENDER_YAML = _REPO_ROOT / "render.yaml"


def _render_env_keys() -> set[str]:
    doc = yaml.safe_load(_RENDER_YAML.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for service in doc.get("services", []):
        for var in service.get("envVars", []):
            if "key" in var:
                keys.add(var["key"])
    return keys


def _registry_env_vars() -> set[str]:
    names: set[str] = set()
    for spec in PROVIDERS:
        if spec.env_key and not (spec.is_local or spec.is_oauth):
            names.add(spec.env_key)
        for extra_name, _template in spec.env_extras:
            if extra_name:
                names.add(extra_name)
    return names


def test_render_yaml_exists() -> None:
    assert _RENDER_YAML.is_file(), "render.yaml missing at repo root"


def test_every_registry_env_var_is_declared() -> None:
    declared = _render_env_keys()
    missing = sorted(_registry_env_vars() - declared)
    assert not missing, f"render.yaml is missing provider env vars: {missing}"


def test_declared_secrets_use_sync_false() -> None:
    doc = yaml.safe_load(_RENDER_YAML.read_text(encoding="utf-8"))
    registry = _registry_env_vars()
    for service in doc.get("services", []):
        for var in service.get("envVars", []):
            if var.get("key") in registry:
                assert var.get("sync") is False, (
                    f"{var['key']} must be sync: false (never committed)"
                )
