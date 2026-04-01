"""Three-state circuit breaker for Bloomberg API session.

Prevents cascading failures when Bloomberg Terminal is down or
at daily capacity. States:

    CLOSED    — Normal operation
    OPEN      — Fast-fail all requests (Bloomberg is down)
    HALF_OPEN — Allow one probe request to test recovery

Capacity errors (-4001) get a longer cooldown than transient failures.
"""

import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class BloombergCircuitOpenError(RuntimeError):
    """Raised when circuit breaker is OPEN and requests are being fast-failed."""

    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class CircuitBreaker:
    """Thread-safe three-state circuit breaker.

    Usage::

        breaker = CircuitBreaker.get_instance()
        result = breaker.call(session.send_request, request, service)
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    _instance: Optional["CircuitBreaker"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        capacity_cooldown: float = 300.0,
        half_open_max: int = 1,
    ):
        """
        Args:
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Seconds before OPEN -> HALF_OPEN (transient errors)
            capacity_cooldown: Seconds before OPEN -> HALF_OPEN (capacity errors)
            half_open_max: Max concurrent probes in HALF_OPEN state
        """
        self._state = self.CLOSED
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._capacity_cooldown = capacity_cooldown
        self._half_open_max = half_open_max
        self._half_open_count = 0
        self._last_failure_time = 0.0
        self._is_capacity_error = False
        self._state_lock = threading.RLock()

    @classmethod
    def get_instance(cls, **kwargs) -> "CircuitBreaker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    @property
    def state(self) -> str:
        with self._state_lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def seconds_until_recovery(self) -> float:
        with self._state_lock:
            if self._state != self.OPEN:
                return 0.0
            timeout = self._capacity_cooldown if self._is_capacity_error else self._recovery_timeout
            remaining = timeout - (time.time() - self._last_failure_time)
            return max(0.0, remaining)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func through the circuit breaker.

        Raises:
            BloombergCircuitOpenError: If circuit is OPEN
            Any exception from func (and may trip the breaker)
        """
        with self._state_lock:
            self._maybe_transition_to_half_open()

            if self._state == self.OPEN:
                remaining = self.seconds_until_recovery
                raise BloombergCircuitOpenError(
                    f"Bloomberg circuit breaker OPEN. "
                    f"Retry in {remaining:.0f}s. "
                    f"Cached data may still be available.",
                    retry_after=remaining,
                )

            if self._state == self.HALF_OPEN:
                if self._half_open_count >= self._half_open_max:
                    raise BloombergCircuitOpenError(
                        "Circuit breaker HALF_OPEN — probe in progress, "
                        "please wait.",
                        retry_after=5.0,
                    )
                self._half_open_count += 1

        # Execute outside the lock
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise

    def _on_success(self) -> None:
        with self._state_lock:
            if self._state == self.HALF_OPEN:
                logger.info(
                    "Circuit breaker recovered: HALF_OPEN -> CLOSED",
                    extra={"circuit_state": self.CLOSED},
                )
            self._state = self.CLOSED
            self._failure_count = 0
            self._half_open_count = 0
            self._is_capacity_error = False

    def _on_failure(self, exc: Exception) -> None:
        from bloomberg_mcp.core.responses import BloombergCapacityError

        is_capacity = isinstance(exc, BloombergCapacityError)

        with self._state_lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if is_capacity:
                self._is_capacity_error = True
                # Capacity error -> immediately open
                self._state = self.OPEN
                logger.warning(
                    "Circuit breaker OPEN: Bloomberg daily capacity reached",
                    extra={"circuit_state": self.OPEN},
                )
            elif self._state == self.HALF_OPEN:
                # Probe failed -> back to OPEN
                self._state = self.OPEN
                self._half_open_count = 0
                logger.warning(
                    "Circuit breaker probe failed: HALF_OPEN -> OPEN",
                    extra={"circuit_state": self.OPEN},
                )
            elif self._failure_count >= self._failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    "Circuit breaker tripped after %d failures: CLOSED -> OPEN",
                    self._failure_count,
                    extra={"circuit_state": self.OPEN},
                )

    def _maybe_transition_to_half_open(self) -> None:
        """Check if enough time has passed to allow a probe. Call with lock held."""
        if self._state != self.OPEN:
            return
        timeout = self._capacity_cooldown if self._is_capacity_error else self._recovery_timeout
        if time.time() - self._last_failure_time >= timeout:
            self._state = self.HALF_OPEN
            self._half_open_count = 0
            logger.info(
                "Circuit breaker timeout elapsed: OPEN -> HALF_OPEN",
                extra={"circuit_state": self.HALF_OPEN},
            )
