"""Per-visitor identity for the public demo.

Why this exists
---------------
DeepTutor is single-user by design: sessions carry no owner column, and every
anonymous demo visitor resolves to the same ``local_admin_user``. In demo mode
the session store is one shared in-memory DB for the whole process, so a naive
``list_sessions`` surfaces *every* visitor's chats to *everyone* — reproduced by
opening the demo in a second browser or incognito window.

This module carries a per-visitor id (minted client-side and sent as the
``X-Demo-Visitor`` header on HTTP and the ``visitor`` query param on the chat
WebSocket) through a request-local :class:`~contextvars.ContextVar`, mirroring
``multi_user.context``'s ``_current_user``. ``get_sqlite_session_store`` reads
it to hand each visitor a physically separate in-memory store, so history stays
both isolated between visitors and ephemeral (in-memory, gone on restart).

It is **isolation, not authentication**: the id is an opaque client-chosen
token, not a security boundary. It only partitions the demo's ephemeral store.
Non-demo deployments never set it, so the value is inert outside the demo.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
import re

# Request-local visitor id. Empty string means "no visitor id supplied" — such
# callers share a single default bucket (see ``get_sqlite_session_store``).
_visitor_id: ContextVar[str] = ContextVar("deeptutor_demo_visitor_id", default="")

# Client-chosen ids are opaque, but they become dict keys for live in-memory
# stores, so bound both the character set and the length to keep a hostile or
# buggy client from minting pathological keys.
_MAX_LEN = 64
_ALLOWED = re.compile(r"[^A-Za-z0-9_-]")


def sanitize_visitor_id(raw: str | None) -> str:
    """Normalise an untrusted visitor id to ``[A-Za-z0-9_-]{1,64}`` or ``""``."""
    if not raw:
        return ""
    cleaned = _ALLOWED.sub("", raw)[:_MAX_LEN]
    return cleaned


def set_visitor_id(value: str | None) -> Token[str]:
    """Bind the current visitor id (sanitized). Returns a reset token.

    Follows the same lifetime rules as ``multi_user.context.set_current_user``:
    HTTP callers may ignore the token (the request task's context is discarded
    when it ends), while long-lived WebSocket handlers keep it and call
    :func:`reset_visitor_id` in their ``finally`` block.
    """
    return _visitor_id.set(sanitize_visitor_id(value))


def reset_visitor_id(token: Token[str]) -> None:
    _visitor_id.reset(token)


def get_visitor_id() -> str:
    """The current visitor id, or ``""`` when none was supplied."""
    return _visitor_id.get()
