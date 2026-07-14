"""Demo-mode safety features (per-IP rate limiting for a public demo)."""

from .rate_limiter import (
    DemoRateLimiter,
    RateDecision,
    client_ip,
    get_demo_limiter,
    is_demo_mode,
)
from .visitor import (
    get_visitor_id,
    reset_visitor_id,
    sanitize_visitor_id,
    set_visitor_id,
)

__all__ = [
    "DemoRateLimiter",
    "RateDecision",
    "client_ip",
    "get_demo_limiter",
    "get_visitor_id",
    "is_demo_mode",
    "reset_visitor_id",
    "sanitize_visitor_id",
    "set_visitor_id",
]
