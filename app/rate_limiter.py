"""Rate limiter backends for the Task Registry service."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Protocol

try:
    import redis
except ImportError:  # pragma: no cover - redis optional
    redis = None  # type: ignore


class RateLimiter(Protocol):
    """Protocol describing limiter behaviour."""

    def allow(self, key: str) -> bool:  # pragma: no cover - protocol definition
        ...

    def reset(self) -> None:  # pragma: no cover - protocol definition
        ...


@dataclass
class SlidingWindowRateLimiter:
    """In-memory sliding window limiter suitable for single-instance deployments."""

    limit: int
    window_seconds: float = 60.0
    burst: int = 0

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.window_seconds <= 0:
            raise ValueError("window must be positive")
        self._entries: dict[str, Deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            timestamps = self._entries.setdefault(key, deque())
            while timestamps and now - timestamps[0] > self.window_seconds:
                timestamps.popleft()

            effective_limit = self.limit + self.burst
            if len(timestamps) >= effective_limit:
                return False

            timestamps.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


class RedisSlidingWindowRateLimiter:
    """Redis-backed limiter that supports horizontally scaled deployments."""

    def __init__(
        self,
        client: "redis.Redis",
        *,
        limit: int,
        window_seconds: float = 60.0,
        burst: int = 0,
        key_prefix: str = "rate:limit",
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window must be positive")
        self.client = client
        self.limit = limit
        self.window_seconds = window_seconds
        self.burst = burst
        self.key_prefix = key_prefix

    def _full_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def allow(self, key: str) -> bool:
        now_ms = int(time.time() * 1000)
        window_start = now_ms - int(self.window_seconds * 1000)
        redis_key = self._full_key(key)

        pipe = self.client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        pipe.expire(redis_key, int(self.window_seconds) + 1)
        removed, count, _ = pipe.execute()

        if count >= self.limit + self.burst:
            return False

        self.client.zadd(redis_key, {str(now_ms): now_ms})
        self.client.expire(redis_key, int(self.window_seconds) + 1)
        return True

    def reset(self) -> None:
        pattern = f"{self.key_prefix}:*"
        for key in self.client.scan_iter(match=pattern):
            self.client.delete(key)


def get_rate_limiter(
    *,
    backend: str,
    limit: int,
    window_seconds: float,
    burst: int,
    redis_url: str | None = None,
) -> RateLimiter:
    """Factory returning the appropriate limiter backend."""

    backend = backend.lower()
    if backend == "redis":
        if redis is None:
            raise RuntimeError("redis library not installed but redis backend requested")
        if not redis_url:
            raise RuntimeError("redis_url must be provided when using redis backend")
        client = redis.Redis.from_url(redis_url)
        return RedisSlidingWindowRateLimiter(
            client, limit=limit, window_seconds=window_seconds, burst=burst
        )

    return SlidingWindowRateLimiter(limit=limit, window_seconds=window_seconds, burst=burst)
