"""Demo mode isolates chat history per browser visitor.

The demo serves a single process to every anonymous visitor. Before this fix
``get_sqlite_session_store`` returned one shared in-memory store for the whole
process, so ``list_sessions`` surfaced *every* visitor's chats to *everyone*
(reproduced by opening the demo in a second browser/incognito window). The fix
keys the demo store by a per-visitor id carried in a ContextVar, so each visitor
gets a physically separate in-memory DB. These tests pin that isolation and
assert the non-demo path still ignores the visitor id entirely.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.services.demo import reset_visitor_id, set_visitor_id
import deeptutor.services.demo.rate_limiter as rate_limiter
from deeptutor.services.path_service import PathService
from deeptutor.services.session import sqlite_store
from deeptutor.services.session.sqlite_store import get_sqlite_session_store


@pytest.fixture
def demo_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Reset the memoised limiter + store instances and point paths at a tmp dir."""
    monkeypatch.setattr(rate_limiter, "_limiter", None)
    monkeypatch.setattr(sqlite_store, "_instances", {})

    service = PathService.get_instance()
    saved = (service._project_root, service._user_data_dir)
    service._project_root = tmp_path.resolve()
    service._user_data_dir = (tmp_path / "data" / "user").resolve()
    try:
        yield service
    finally:
        (service._project_root, service._user_data_dir) = saved


@pytest.mark.asyncio
async def test_history_isolated_between_visitors(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    # Visitor A starts a chat.
    token_a = set_visitor_id("visitor-a")
    store_a = get_sqlite_session_store()
    await store_a.create_session(title="A's private chat")
    reset_visitor_id(token_a)

    # Visitor B (e.g. an incognito window) must see none of A's history.
    token_b = set_visitor_id("visitor-b")
    store_b = get_sqlite_session_store()
    assert store_b is not store_a
    assert await store_b.list_sessions() == []
    reset_visitor_id(token_b)

    # Visitor A comes back to the same store and still sees their own chat.
    token_a2 = set_visitor_id("visitor-a")
    store_a2 = get_sqlite_session_store()
    assert store_a2 is store_a
    assert len(await store_a2.list_sessions()) == 1
    reset_visitor_id(token_a2)


def test_same_visitor_reuses_one_store(demo_env, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    token = set_visitor_id("visitor-a")
    try:
        assert get_sqlite_session_store() is get_sqlite_session_store()
    finally:
        reset_visitor_id(token)


def test_non_demo_ignores_visitor_id(demo_env, monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)

    token_a = set_visitor_id("visitor-a")
    store_a = get_sqlite_session_store()
    reset_visitor_id(token_a)

    token_b = set_visitor_id("visitor-b")
    store_b = get_sqlite_session_store()
    reset_visitor_id(token_b)

    # Off demo, the store is the single on-disk store regardless of visitor.
    assert store_a is store_b
    assert store_a.in_memory is False
