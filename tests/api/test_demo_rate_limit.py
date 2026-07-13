"""Integration tests for demo-mode rate limiting at the ASGI layer.

Mirrors the minimal-app style of ``test_selective_access_log.py``: a small
FastAPI app wires the *real* ``DemoRateLimiter`` (with an injected clock) into
the same middleware/WS shapes used in ``main.py``, ``chat.py`` and
``unified_ws.py``, so the enforcement contract is exercised without booting the
full application.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from deeptutor.services.demo.rate_limiter import DemoRateLimiter, client_ip

_DEMO_EXEMPT_PREFIXES = ("/api/outputs",)


def _build_app(limiter: DemoRateLimiter) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def demo_rate_limit(request, call_next):
        if limiter.enabled:
            path = request.url.path
            if path != "/" and not path.startswith(_DEMO_EXEMPT_PREFIXES):
                ip = client_ip(request.headers, request.client.host if request.client else None)
                decision = limiter.hit(ip)
                if not decision.allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded. Try again shortly."},
                        headers={"Retry-After": str(decision.retry_after)},
                    )
        return await call_next(request)

    @app.get("/")
    async def root():
        return {"ok": True}

    @app.get("/api/outputs/thing")
    async def static_like():
        return {"ok": True}

    @app.get("/api/v1/chat/sessions")
    async def api_route():
        return {"ok": True}

    @app.websocket("/chat")
    async def chat(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                data = await ws.receive_json()
                if not data.get("message", "").strip():
                    await ws.send_json({"type": "error", "message": "Message is required"})
                    continue
                if limiter.enabled:
                    ip = client_ip(ws.headers, ws.client.host if ws.client else None)
                    if not limiter.hit(ip).allowed:
                        await ws.send_json(
                            {"type": "error", "message": "Rate limit exceeded. Please slow down."}
                        )
                        continue
                await ws.send_json({"type": "result", "content": "ok"})
        except WebSocketDisconnect:
            pass

    return app


def test_http_returns_429_after_limit_with_retry_after():
    limiter = DemoRateLimiter(enabled=True, per_min=2, per_hour=100)
    client = TestClient(_build_app(limiter))

    assert client.get("/api/v1/chat/sessions").status_code == 200
    assert client.get("/api/v1/chat/sessions").status_code == 200

    resp = client.get("/api/v1/chat/sessions")
    assert resp.status_code == 429
    assert resp.json()["detail"] == "Rate limit exceeded. Try again shortly."
    assert int(resp.headers["Retry-After"]) > 0


def test_exempt_paths_never_429():
    limiter = DemoRateLimiter(enabled=True, per_min=1, per_hour=1)
    client = TestClient(_build_app(limiter))

    # Health check and static mount stay open no matter how many times hit.
    for _ in range(5):
        assert client.get("/").status_code == 200
        assert client.get("/api/outputs/thing").status_code == 200


def test_disabled_never_limits():
    limiter = DemoRateLimiter(enabled=False, per_min=1, per_hour=1)
    client = TestClient(_build_app(limiter))
    for _ in range(10):
        assert client.get("/api/v1/chat/sessions").status_code == 200


def test_chat_ws_emits_error_frame_after_limit_socket_stays_open():
    limiter = DemoRateLimiter(enabled=True, per_min=2, per_hour=100)
    client = TestClient(_build_app(limiter))

    with client.websocket_connect("/chat") as ws:
        ws.send_json({"message": "hi"})
        assert ws.receive_json()["type"] == "result"
        ws.send_json({"message": "hi"})
        assert ws.receive_json()["type"] == "result"

        # Third message within the window is rejected, socket stays usable.
        ws.send_json({"message": "hi"})
        rejected = ws.receive_json()
        assert rejected["type"] == "error"
        assert rejected["message"] == "Rate limit exceeded. Please slow down."

        # Empty-message guard still works after a rate-limit rejection.
        ws.send_json({"message": "   "})
        assert ws.receive_json()["message"] == "Message is required"
