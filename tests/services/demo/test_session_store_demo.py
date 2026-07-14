"""The session-store factory swaps in an ephemeral in-memory store in demo mode.

Every chat-history read/write for the web demo funnels through
``get_session_store()`` -> ``get_sqlite_session_store()`` (PocketBase off is the
demo default), so gating the factory is enough to make the whole demo surface
ephemeral. See ``plan.md`` "no persisted history in demo mode".
"""

from __future__ import annotations

from pathlib import Path

import pytest

import deeptutor.services.demo.rate_limiter as rate_limiter
from deeptutor.services.path_service import PathService
from deeptutor.services.session import get_session_store
import deeptutor.services.session.sqlite_store as sqlite_store
from deeptutor.services.session.sqlite_store import get_sqlite_session_store


@pytest.fixture
def reset_singletons(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Isolate the memoised limiter and store instances per test."""
    monkeypatch.setattr(rate_limiter, "_limiter", None)
    monkeypatch.setattr(sqlite_store, "_instances", {})

    service = PathService.get_instance()
    original_root = service._project_root
    original_user_dir = service._user_data_dir
    service._project_root = tmp_path
    service._user_data_dir = tmp_path / "data" / "user"
    try:
        yield service
    finally:
        service._project_root = original_root
        service._user_data_dir = original_user_dir


def test_demo_mode_returns_in_memory_store(reset_singletons, monkeypatch):
    monkeypatch.setenv("DEMO", "true")

    store = get_sqlite_session_store()

    assert store.in_memory is True
    assert not reset_singletons.get_chat_history_db().exists()
    # get_session_store() (what routers/turn-runtime call) returns the same one.
    assert get_session_store() is store


def test_demo_mode_off_returns_on_disk_store(reset_singletons, monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)

    store = get_sqlite_session_store()

    assert store.in_memory is False
    assert isinstance(store.db_path, Path)
    assert store.db_path.exists()
