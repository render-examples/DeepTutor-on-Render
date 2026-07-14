"""Per-IP rate limiting for a public DeepTutor demo.

Why this exists
---------------
When the maintainer hosts a **public demo URL**, every visitor's chat runs
against the maintainer's *own* provider key. Unbounded use means runaway spend.
Demo mode caps per-visitor usage so the demo is safe to leave open.

What it protects
----------------
Runaway key spend only — *not* general DoS hardening or per-visitor fairness.
The requests that actually spend the key are mostly **WebSocket message loops**
(``/chat`` and ``/ws``), where a single long-lived socket sends unlimited LLM
turns. A conventional HTTP rate-limit library only sees the socket *open*, not
the individual messages, so this limiter is invoked from inside those message
loops as well as from an HTTP catch-all middleware.

Configuration (read once from the environment)
-----------------------------------------------
* ``DEMO_MODE`` — bool, default ``false``. Truthy values (case-insensitive):
  ``1``, ``true``, ``yes``, ``on``. **Off by default**, so local and private
  forks are unaffected; only the public demo service sets ``DEMO_MODE=true``.
* ``DEMO_RATE_LIMIT_PER_MIN`` — int, default ``15``.
* ``DEMO_RATE_LIMIT_PER_HOUR`` — int, default ``200``.

Out of scope (v1)
-----------------
Buckets are **in-memory, per-process**. This is fine for a single-instance
demo. If the demo runs multiple instances, each holds its own buckets, so the
effective limit is multiplied by the instance count. A shared store (e.g.
Redis) would be the upgrade path — not implemented here. Secondary spenders
(``/question/*``, ``/book``, notebook summaries, co_writer, voice) are not yet
demo-guarded.

Design
------
* Fixed-window counters, one per IP, for the minute and hour windows.
* ``client_ip`` reads ``X-Forwarded-For`` (first hop) because Render runs behind
  a reverse proxy — ``client.host`` would otherwise be the shared proxy IP.
* The clock is injectable so window logic is deterministically testable without
  real sleeps. ``time.monotonic`` is used in production.
* **Fail-open**: any unexpected internal error yields ``allowed=True``. A
  rate-limit bug must never take the app down.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Callable

_TRUTHY = {"1", "true", "yes", "on"}

_MINUTE = 60.0
_HOUR = 3600.0

# Opportunistic pruning cadence: every N ``hit`` calls, drop buckets untouched
# for longer than the longest window so the dict can't grow unbounded.
_PRUNE_EVERY = 256


@dataclass(frozen=True)
class RateDecision:
    """Outcome of a limiter check."""

    allowed: bool
    retry_after: int = 0  # seconds until the caller may retry (0 when allowed)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return value if value > 0 else default


def client_ip(headers: object, client_host: str | None) -> str:
    """Best-effort visitor IP, proxy-aware.

    Reads the first hop of ``X-Forwarded-For`` (the original client, since
    Render appends its proxy IP), falling back to ``client_host`` and finally
    ``"unknown"``. ``headers`` is anything with a case-insensitive ``get`` —
    a Starlette ``Headers`` (for both ``Request`` and ``WebSocket``).
    """
    try:
        getter = getattr(headers, "get", None)
        forwarded = getter("x-forwarded-for") if getter else None
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    except Exception:
        pass
    if client_host:
        return client_host
    return "unknown"


class _Bucket:
    """Fixed-window counters for one IP across the minute and hour windows."""

    __slots__ = ("minute_start", "minute_count", "hour_start", "hour_count", "last_seen")

    def __init__(self, now: float) -> None:
        self.minute_start = now
        self.minute_count = 0
        self.hour_start = now
        self.hour_count = 0
        self.last_seen = now


class DemoRateLimiter:
    """In-memory per-IP token/window limiter. Fail-open, single-process."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        per_min: int | None = None,
        per_hour: int | None = None,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._enabled = _env_bool("DEMO_MODE") if enabled is None else enabled
        self._per_min = _env_int("DEMO_RATE_LIMIT_PER_MIN", 15) if per_min is None else per_min
        self._per_hour = _env_int("DEMO_RATE_LIMIT_PER_HOUR", 200) if per_hour is None else per_hour
        self._time_fn = time_fn
        self._buckets: dict[str, _Bucket] = {}
        self._calls_since_prune = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def hit(self, ip: str) -> RateDecision:
        """Record one request for ``ip`` and decide whether it is allowed.

        Always allows when disabled. Never raises: any internal error is
        swallowed and treated as allowed (fail-open).
        """
        if not self._enabled:
            return RateDecision(allowed=True)
        try:
            return self._hit(ip)
        except Exception:  # pragma: no cover - defensive fail-open
            return RateDecision(allowed=True)

    def _hit(self, ip: str) -> RateDecision:
        now = self._time_fn()
        self._maybe_prune(now)

        bucket = self._buckets.get(ip)
        if bucket is None:
            bucket = _Bucket(now)
            self._buckets[ip] = bucket
        bucket.last_seen = now

        # Roll windows that have fully elapsed.
        if now - bucket.minute_start >= _MINUTE:
            bucket.minute_start = now
            bucket.minute_count = 0
        if now - bucket.hour_start >= _HOUR:
            bucket.hour_start = now
            bucket.hour_count = 0

        # Deny (without consuming) if either window is already at its cap.
        if bucket.minute_count >= self._per_min:
            retry = _ceil(_MINUTE - (now - bucket.minute_start))
            return RateDecision(allowed=False, retry_after=retry)
        if bucket.hour_count >= self._per_hour:
            retry = _ceil(_HOUR - (now - bucket.hour_start))
            return RateDecision(allowed=False, retry_after=retry)

        bucket.minute_count += 1
        bucket.hour_count += 1
        return RateDecision(allowed=True)

    def _maybe_prune(self, now: float) -> None:
        self._calls_since_prune += 1
        if self._calls_since_prune < _PRUNE_EVERY:
            return
        self._calls_since_prune = 0
        stale = [ip for ip, b in self._buckets.items() if now - b.last_seen > _HOUR]
        for ip in stale:
            del self._buckets[ip]


def _ceil(seconds: float) -> int:
    """Whole seconds until a window frees up, at least 1."""
    return max(1, int(seconds) + (1 if seconds > int(seconds) else 0))


_limiter: DemoRateLimiter | None = None


def get_demo_limiter() -> DemoRateLimiter:
    """Process-wide shared limiter so every enforcement point shares state."""
    global _limiter
    if _limiter is None:
        _limiter = DemoRateLimiter()
    return _limiter


def is_demo_mode() -> bool:
    """True when ``DEMO_MODE`` is enabled.

    Shared guard for the demo's "history stays ephemeral" contract: any code
    path that would otherwise write conversation-derived state to disk checks
    this and skips the write. Reuses the process-wide limiter so the answer is
    consistent everywhere and honours test overrides of ``_limiter``.
    """
    return get_demo_limiter().enabled
