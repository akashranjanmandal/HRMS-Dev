"""A minimal in-process rate limiter for the sign-in endpoints.

In-memory and per-process, matching the existing style of
``app.services.mailer.OUTBOX`` elsewhere in this codebase — fine for a
single-worker deployment. Scaling to multiple worker processes (or
machines) would need a shared store (e.g. Redis) instead, since each
worker would otherwise keep its own independent counters; revisit this
if/when the deployment moves to multiple workers.
"""
import time
from collections import defaultdict

from fastapi import HTTPException, status

# key -> list of attempt timestamps (seconds) within the current window
_attempts: dict[str, list[float]] = defaultdict(list)


def _prune(key: str, window_seconds: float) -> list[float]:
    cutoff = time.monotonic() - window_seconds
    _attempts[key] = [t for t in _attempts[key] if t > cutoff]
    return _attempts[key]


def check_and_record(key: str, *, max_attempts: int, window_seconds: float) -> None:
    """Raise 429 if ``key`` has already made ``max_attempts`` within the
    window; otherwise record this attempt and allow it through."""
    recent = _prune(key, window_seconds)
    if len(recent) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a few minutes and try again.",
        )
    recent.append(time.monotonic())


def reset(key: str) -> None:
    """Clear a key's attempt history — called on a successful sign-in so
    a legitimate user who mistyped their password a couple of times isn't
    still partway through the window next time."""
    _attempts.pop(key, None)
