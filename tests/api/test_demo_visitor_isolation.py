"""Integration test: the demo visitor id survives the request lifecycle.

The store-level isolation is covered by
``tests/services/demo/test_demo_visitor_isolation.py``. This test pins the part
that unit tests can't: that the real ``bind_demo_visitor`` dependency actually
sets the visitor ContextVar in a way the endpoint sees. That is exactly the
regression class behind issue #481 (a sync dependency's ContextVar set runs in a
worker thread and is discarded), so we exercise it through the ASGI stack with
``TestClient``, mirroring the minimal-app style of ``test_demo_rate_limit.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from deeptutor.api.routers.auth import bind_demo_visitor
import deeptutor.services.demo.rate_limiter as rate_limiter
from deeptutor.services.path_service import PathService
from deeptutor.services.session import sqlite_store
from deeptutor.services.session.sqlite_store import get_sqlite_session_store


@pytest.fixture
def demo_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(rate_limiter, "_limiter", None)
    monkeypatch.setattr(sqlite_store, "_instances", {})

    service = PathService.get_instance()
    saved = (service._project_root, service._user_data_dir)
    service._project_root = tmp_path.resolve()
    service._user_data_dir = (tmp_path / "data" / "user").resolve()

    app = FastAPI(dependencies=[Depends(bind_demo_visitor)])

    @app.post("/sessions")
    async def create(title: str):
        await get_sqlite_session_store().create_session(title=title)
        return {"ok": True}

    @app.get("/sessions")
    async def listing():
        rows = await get_sqlite_session_store().list_sessions()
        return {"titles": [r["title"] for r in rows]}

    try:
        yield TestClient(app)
    finally:
        (service._project_root, service._user_data_dir) = saved


def _h(visitor: str) -> dict[str, str]:
    return {"X-Demo-Visitor": visitor}


def test_visitors_do_not_see_each_others_history(demo_client):
    demo_client.post("/sessions", params={"title": "alice chat"}, headers=_h("alice"))

    # Bob (a second browser / incognito) sees none of Alice's history.
    assert demo_client.get("/sessions", headers=_h("bob")).json()["titles"] == []
    # Alice still sees her own.
    assert demo_client.get("/sessions", headers=_h("alice")).json()["titles"] == ["alice chat"]


def test_missing_header_does_not_inherit_previous_visitor(demo_client):
    """A request with no visitor id must not leak into another's bucket."""
    demo_client.post("/sessions", params={"title": "alice chat"}, headers=_h("alice"))

    # No header → default bucket, which is empty (not Alice's).
    assert demo_client.get("/sessions").json()["titles"] == []


@pytest.mark.asyncio
async def test_ws_require_auth_binds_visitor_from_query_param(monkeypatch):
    """The chat WebSocket carries the visitor id as a query param (WS upgrades
    can't set custom headers), and ``ws_require_auth`` must bind it."""
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(rate_limiter, "_limiter", None)

    from deeptutor.api.routers.auth import ws_require_auth
    from deeptutor.services.demo import get_visitor_id

    class _FakeWS:
        # AUTH is disabled by default, so ws_require_auth only touches query_params.
        query_params = {"visitor": "alice"}
        cookies: dict[str, str] = {}

    await ws_require_auth(_FakeWS())
    assert get_visitor_id() == "alice"
