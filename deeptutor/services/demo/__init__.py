"""Demo-mode safety features (per-IP rate limiting for a public demo)."""

from .rate_limiter import (
    DemoRateLimiter,
    RateDecision,
    client_ip,
    get_demo_limiter,
    is_demo_mode,
)

__all__ = [
    "DemoRateLimiter",
    "RateDecision",
    "client_ip",
    "get_demo_limiter",
    "is_demo_mode",
]
