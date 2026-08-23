"""Per-IP request rate limiting for the chat API."""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request

REQUESTS_PER_MINUTE = 30
WINDOW_SECONDS = 60.0

_lock = threading.Lock()
_requests: dict[str, deque[float]] = {}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _purge_old(timestamps: deque[float], now: float) -> None:
    cutoff = now - WINDOW_SECONDS
    while timestamps and timestamps[0] <= cutoff:
        timestamps.popleft()


def check_rate_limit(request: Request) -> None:
    """Raise HTTP 429 when the client exceeds the per-minute request quota."""
    client_ip = _client_ip(request)
    now = time.time()

    with _lock:
        timestamps = _requests.setdefault(client_ip, deque())
        _purge_old(timestamps, now)

        if len(timestamps) >= REQUESTS_PER_MINUTE:
            retry_after = max(1, int(WINDOW_SECONDS - (now - timestamps[0])))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)


def reset_rate_limits() -> None:
    """Clear tracked request timestamps (for tests)."""
    with _lock:
        _requests.clear()
