"""Tests for the ephemeral in-memory mode of ``SQLiteSessionStore``.

Demo mode must never write chat history to disk (see ``plan.md`` follow-up).
In-memory mode keeps a shared-cache SQLite DB alive for the store's lifetime
so per-operation connections still see each other's writes, while nothing
touches the on-disk chat-history file.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from deeptutor.services.path_service import PathService
from deeptutor.services.session.sqlite_store import SQLiteSessionStore


def test_in_memory_store_round_trips_within_process() -> None:
    store = SQLiteSessionStore(in_memory=True)

    session = asyncio.run(store.create_session(title="Ephemeral"))
    sid = session["id"]
    asyncio.run(store.add_message(sid, "user", "hello"))
    asyncio.run(store.add_message(sid, "assistant", "hi there"))

    messages = asyncio.run(store.get_messages(sid))
    assert [m["content"] for m in messages] == ["hello", "hi there"]


def test_in_memory_store_is_isolated_between_instances() -> None:
    # Each in-memory store gets its own shared-cache namespace, so two stores
    # never leak sessions into each other.
    store_a = SQLiteSessionStore(in_memory=True)
    store_b = SQLiteSessionStore(in_memory=True)

    session = asyncio.run(store_a.create_session(title="A"))
    assert asyncio.run(store_b.get_session(session["id"])) is None


def test_in_memory_store_does_not_create_on_disk_db(tmp_path: Path) -> None:
    service = PathService.get_instance()
    original_root = service._project_root
    original_user_dir = service._user_data_dir
    try:
        service._project_root = tmp_path
        service._user_data_dir = tmp_path / "data" / "user"

        store = SQLiteSessionStore(in_memory=True)
        session = asyncio.run(store.create_session(title="Ephemeral"))
        asyncio.run(store.add_message(session["id"], "user", "hello"))

        chat_history_db = service.get_chat_history_db()
        assert not chat_history_db.exists()
    finally:
        service._project_root = original_root
        service._user_data_dir = original_user_dir
