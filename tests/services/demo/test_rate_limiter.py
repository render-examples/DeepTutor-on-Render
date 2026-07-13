"""Unit tests for the demo-mode per-IP rate limiter.

The limiter's clock is injectable, so window behaviour is exercised by advancing
a fake clock rather than sleeping. Limits are passed to the constructor directly
so these tests don't depend on the process environment.
"""

from __future__ import annotations

import pytest

from deeptutor.services.demo.rate_limiter import (
    DemoRateLimiter,
    RateDecision,
    client_ip,
)


class _FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _limiter(clock: _FakeClock, *, per_min: int = 3, per_hour: int = 100) -> DemoRateLimiter:
    return DemoRateLimiter(
        enabled=True, per_min=per_min, per_hour=per_hour, time_fn=clock
    )


def test_allows_within_per_minute_then_denies_next():
    clock = _FakeClock()
    limiter = _limiter(clock, per_min=3)

    assert [limiter.hit("1.2.3.4").allowed for _ in range(3)] == [True, True, True]

    denied = limiter.hit("1.2.3.4")
    assert denied.allowed is False
    assert denied.retry_after > 0


def test_minute_window_resets_after_60s():
    clock = _FakeClock()
    limiter = _limiter(clock, per_min=2)

    assert limiter.hit("ip").allowed
    assert limiter.hit("ip").allowed
    assert not limiter.hit("ip").allowed

    clock.advance(60)
    assert limiter.hit("ip").allowed


def test_per_hour_cap_denies_even_when_minute_would_allow():
    clock = _FakeClock()
    # Generous per-minute, tight per-hour: sustained abuse across many minutes.
    limiter = _limiter(clock, per_min=100, per_hour=5)

    allowed = 0
    for _ in range(10):
        for _ in range(3):
            if limiter.hit("ip").allowed:
                allowed += 1
        clock.advance(60)  # roll the minute window so per-min never bites

    assert allowed == 5  # capped by the hourly limit


def test_hour_window_resets_after_3600s():
    clock = _FakeClock()
    limiter = _limiter(clock, per_min=100, per_hour=2)

    assert limiter.hit("ip").allowed
    assert limiter.hit("ip").allowed
    assert not limiter.hit("ip").allowed

    clock.advance(3600)
    assert limiter.hit("ip").allowed


def test_per_ip_isolation():
    clock = _FakeClock()
    limiter = _limiter(clock, per_min=1)

    assert limiter.hit("a").allowed
    assert not limiter.hit("a").allowed
    # A different IP has its own bucket.
    assert limiter.hit("b").allowed


def test_disabled_always_allows():
    clock = _FakeClock()
    limiter = DemoRateLimiter(enabled=False, per_min=1, per_hour=1, time_fn=clock)
    assert limiter.enabled is False
    assert all(limiter.hit("ip").allowed for _ in range(50))


def test_disabled_by_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    limiter = DemoRateLimiter()  # reads env: DEMO_MODE unset -> disabled
    assert limiter.enabled is False
    assert limiter.hit("ip").allowed


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "On"])
def test_env_truthy_enables(monkeypatch, value):
    monkeypatch.setenv("DEMO_MODE", value)
    assert DemoRateLimiter().enabled is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "maybe"])
def test_env_falsy_disables(monkeypatch, value):
    monkeypatch.setenv("DEMO_MODE", value)
    assert DemoRateLimiter().enabled is False


def test_env_limits_parsed(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_MIN", "2")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "9")
    clock = _FakeClock()
    limiter = DemoRateLimiter(time_fn=clock)
    assert limiter.hit("ip").allowed
    assert limiter.hit("ip").allowed
    assert not limiter.hit("ip").allowed


def test_env_bad_limits_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_MIN", "not-an-int")
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_HOUR", "-5")
    limiter = DemoRateLimiter(time_fn=_FakeClock())
    # Default per-min is 15: the 16th within the window is the first denial.
    allowed = [limiter.hit("ip").allowed for _ in range(16)]
    assert allowed[:15] == [True] * 15
    assert allowed[15] is False


def test_fail_open_on_internal_error(monkeypatch):
    clock = _FakeClock()
    limiter = _limiter(clock)

    def boom(_ip):
        raise RuntimeError("bucket exploded")

    monkeypatch.setattr(limiter, "_hit", boom)
    assert limiter.hit("ip") == RateDecision(allowed=True)


def test_stale_ip_pruning_keeps_dict_bounded():
    clock = _FakeClock()
    limiter = _limiter(clock, per_min=1_000_000, per_hour=1_000_000)

    # Touch many distinct IPs long enough ago to be stale, then keep going so a
    # prune sweep runs (prune cadence is every 256 calls).
    for i in range(300):
        limiter.hit(f"stale-{i}")
    clock.advance(3601)  # every touched bucket is now older than the hour window
    for i in range(300):
        limiter.hit(f"fresh-{i}")

    # Stale buckets were dropped; the dict is far smaller than 600.
    assert len(limiter._buckets) <= 300


# --- client_ip -------------------------------------------------------------


class _Headers:
    """Minimal case-insensitive header lookup like Starlette's Headers."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._m = {k.lower(): v for k, v in mapping.items()}

    def get(self, key: str, default=None):
        return self._m.get(key.lower(), default)


def test_client_ip_uses_first_forwarded_hop():
    headers = _Headers({"X-Forwarded-For": "203.0.113.7, 10.0.0.1, 10.0.0.2"})
    assert client_ip(headers, "10.0.0.1") == "203.0.113.7"


def test_client_ip_single_forwarded():
    headers = _Headers({"x-forwarded-for": "198.51.100.9"})
    assert client_ip(headers, "10.0.0.1") == "198.51.100.9"


def test_client_ip_falls_back_to_client_host_when_header_absent():
    assert client_ip(_Headers({}), "192.0.2.5") == "192.0.2.5"


def test_client_ip_unknown_when_nothing_available():
    assert client_ip(_Headers({}), None) == "unknown"


def test_client_ip_ignores_blank_forwarded_and_falls_back():
    headers = _Headers({"x-forwarded-for": "   "})
    assert client_ip(headers, "192.0.2.5") == "192.0.2.5"
