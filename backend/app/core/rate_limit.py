"""Lightweight in-memory rate limiter for sensitive endpoints (signup/login).

Deliberately dependency-free (no Redis, no slowapi) — consistent with the
project's existing "no Redis" call for this scale. This is per-process only,
so it resets on restart and does not coordinate across multiple instances;
before running more than one backend instance behind a load balancer, swap
this for a Redis-backed limiter.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(max_requests: int, window_seconds: int):
    async def _dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{request.url.path}:{client_ip}"
        now = time.monotonic()
        hits = _hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again in a minute.")
        hits.append(now)

    return _dependency


def reset_for_tests() -> None:
    _hits.clear()
