"""Request throttling middleware for Bloomberg MCP.

Prevents runaway LLM agents from exceeding Bloomberg API capacity
by enforcing per-minute and per-hour rate limits on tool calls.
"""

import logging
import threading
import time
from collections import deque
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ThrottleExceededError(RuntimeError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class RequestThrottle:
    """Sliding-window rate limiter for Bloomberg API requests.

    Tracks requests in two windows (per-minute and per-hour).
    Thread-safe via internal lock.

    Usage::

        throttle = RequestThrottle.get_instance()
        throttle.check_and_record()  # raises ThrottleExceededError if over limit
    """

    _instance: Optional["RequestThrottle"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        max_per_minute: int = 60,
        max_per_hour: int = 500,
    ):
        self._max_per_minute = max_per_minute
        self._max_per_hour = max_per_hour
        self._minute_window: deque = deque()
        self._hour_window: deque = deque()
        self._access_lock = threading.Lock()

    @classmethod
    def get_instance(cls, **kwargs) -> "RequestThrottle":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def check_and_record(self) -> None:
        """Check rate limits and record the request if allowed.

        Raises:
            ThrottleExceededError: If either limit is exceeded
        """
        now = time.time()

        with self._access_lock:
            # Prune expired entries
            minute_ago = now - 60
            hour_ago = now - 3600
            while self._minute_window and self._minute_window[0] < minute_ago:
                self._minute_window.popleft()
            while self._hour_window and self._hour_window[0] < hour_ago:
                self._hour_window.popleft()

            # Check limits
            if len(self._minute_window) >= self._max_per_minute:
                oldest = self._minute_window[0]
                retry_after = 60 - (now - oldest)
                raise ThrottleExceededError(
                    f"Rate limit exceeded: {self._max_per_minute} requests/minute. "
                    f"Retry in {retry_after:.0f}s.",
                    retry_after=max(0, retry_after),
                )

            if len(self._hour_window) >= self._max_per_hour:
                oldest = self._hour_window[0]
                retry_after = 3600 - (now - oldest)
                raise ThrottleExceededError(
                    f"Rate limit exceeded: {self._max_per_hour} requests/hour. "
                    f"Retry in {retry_after:.0f}s.",
                    retry_after=max(0, retry_after),
                )

            # Record
            self._minute_window.append(now)
            self._hour_window.append(now)

    @property
    def remaining(self) -> Dict[str, int]:
        """Return remaining quota for each window."""
        now = time.time()
        with self._access_lock:
            minute_ago = now - 60
            hour_ago = now - 3600
            minute_count = sum(1 for t in self._minute_window if t >= minute_ago)
            hour_count = sum(1 for t in self._hour_window if t >= hour_ago)
            return {
                "minute": max(0, self._max_per_minute - minute_count),
                "hour": max(0, self._max_per_hour - hour_count),
            }
