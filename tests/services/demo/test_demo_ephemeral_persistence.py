"""Demo mode keeps chat history ephemeral across *every* per-turn disk write.

Gating the session-store factory (see ``test_session_store_demo.py``) makes the
chat-history DB in-memory, but the turn runtime and the memory subsystem write
conversation-derived state to disk through other paths. In demo mode those must
be skipped too, otherwise history is still persisted on disk. Each test below
pins the culprit write path and asserts it is a no-op when ``DEMO`` is on
and still writes when it is off.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

import deeptutor.services.demo.rate_limiter as rate_limiter
from deeptutor.services.memory import store as memory_store
from deeptutor.services.memory import trace as memory_trace
from deeptutor.services.memory.paths import trace_file
from deeptutor.services.path_service import PathService
from deeptutor.services.session.turn_runtime import TurnRuntimeManager, _TurnExecution


@pytest.fixture
def tmp_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point every persistence root at a tmp dir and reset the demo limiter."""
    monkeypatch.setattr(rate_limiter, "_limiter", None)

    service = PathService.get_instance()
    saved = (service._workspace_root, service._project_root, service._user_data_dir)
    service._workspace_root = (tmp_path / "data").resolve()
    service._project_root = tmp_path.resolve()
    service._user_data_dir = (tmp_path / "data" / "user").resolve()
    try:
        yield service
    finally:
        (service._workspace_root, service._project_root, service._user_data_dir) = saved


def _execution() -> _TurnExecution:
    return _TurnExecution(
        turn_id="turn_abc",
        session_id="sess_1",
        capability="chat",
        payload={},
    )


def test_workspace_event_mirror_skipped_in_demo(tmp_paths, monkeypatch):
    monkeypatch.setenv("DEMO", "true")

    TurnRuntimeManager._mirror_event_to_workspace(
        _execution(), {"type": "assistant", "content": "secret history"}
    )

    event_file = tmp_paths.get_task_workspace("chat", "turn_abc") / "events.jsonl"
    assert not event_file.exists()


def test_workspace_event_mirror_written_when_demo_off(tmp_paths, monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)

    TurnRuntimeManager._mirror_event_to_workspace(
        _execution(), {"type": "assistant", "content": "kept history"}
    )

    event_file = tmp_paths.get_task_workspace("chat", "turn_abc") / "events.jsonl"
    assert event_file.exists()
    assert "kept history" in event_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_memory_trace_append_skipped_in_demo(tmp_paths, monkeypatch):
    monkeypatch.setenv("DEMO", "true")

    await memory_trace.append(
        memory_trace.TraceEvent.new("chat", "preference_stated", {"text": "likes X"})
    )

    day = datetime.now(tz=timezone.utc).date()
    assert not trace_file("chat", day).exists()


@pytest.mark.asyncio
async def test_memory_trace_append_written_when_demo_off(tmp_paths, monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)

    await memory_trace.append(
        memory_trace.TraceEvent.new("chat", "preference_stated", {"text": "likes X"})
    )

    day = datetime.now(tz=timezone.utc).date()
    assert trace_file("chat", day).exists()


@pytest.mark.asyncio
async def test_write_preference_skipped_in_demo(tmp_paths, monkeypatch):
    monkeypatch.setenv("DEMO", "true")

    store = memory_store.MemoryStore()
    report = await store.write_preference(
        op="add", text="prefers dark mode", trace_id=memory_trace.new_trace_id("chat")
    )

    from deeptutor.services.memory.paths import l3_file

    assert not l3_file("preferences").exists()
    assert report.accepted is False


@pytest.mark.asyncio
async def test_write_preference_written_when_demo_off(tmp_paths, monkeypatch):
    monkeypatch.delenv("DEMO", raising=False)

    store = memory_store.MemoryStore()
    report = await store.write_preference(
        op="add", text="prefers dark mode", trace_id=memory_trace.new_trace_id("chat")
    )

    from deeptutor.services.memory.paths import l3_file

    assert report.accepted is True
    assert l3_file("preferences").exists()
