"""Sliding-window rate limiter for sensitive endpoints (login, registration)."""

from __future__ import annotations

import collections
import threading
import time
from typing import DefaultDict, Deque, Optional, Tuple


class SlidingWindowRateLimiter:
    """In-memory thread-safe sliding window rate limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: DefaultDict[str, Deque[float]] = collections.defaultdict(collections.deque)

    def check(self, key: str, max_requests: int, window_seconds: float) -> Tuple[bool, int]:
        """Check if request is allowed under the rate limit.

        Returns (allowed, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            queue = self._buckets[key]
            # Discard timestamps outside the current window
            while queue and queue[0] < cutoff:
                queue.popleft()

            if len(queue) >= max_requests:
                earliest = queue[0]
                retry_after = max(1, int(earliest + window_seconds - now))
                return False, retry_after

            queue.append(now)
            return True, 0

    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limit buckets (useful for test isolation)."""
        with self._lock:
            if key is not None:
                self._buckets.pop(key, None)
            else:
                self._buckets.clear()


login_limiter = SlidingWindowRateLimiter()
global_rate_limiter = login_limiter
