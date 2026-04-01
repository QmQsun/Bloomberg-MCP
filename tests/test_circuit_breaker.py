"""Tests for circuit breaker — simulates Bloomberg failure modes."""

import time
import pytest

from bloomberg_mcp.core.circuit_breaker import CircuitBreaker, BloombergCircuitOpenError


@pytest.fixture(autouse=True)
def reset_breaker():
    """Reset singleton before each test."""
    CircuitBreaker.reset_instance()
    yield
    CircuitBreaker.reset_instance()


class TestCircuitBreakerStates:
    """Test the three-state circuit breaker transitions."""

    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitBreaker.CLOSED

    def test_stays_closed_on_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitBreaker.CLOSED

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(_always_fail)

        assert cb.state == CircuitBreaker.OPEN

    def test_open_rejects_immediately(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)

        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(_always_fail)

        with pytest.raises(BloombergCircuitOpenError) as exc_info:
            cb.call(lambda: "should not execute")

        assert "OPEN" in str(exc_info.value)
        assert exc_info.value.retry_after > 0

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(_always_fail)

        assert cb.state == CircuitBreaker.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        assert cb.state == CircuitBreaker.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(_always_fail)

        time.sleep(0.15)

        # Probe should succeed and close circuit
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitBreaker.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(_always_fail)

        time.sleep(0.15)

        # Probe fails -> back to OPEN
        with pytest.raises(ValueError):
            cb.call(_always_fail)

        assert cb.state == CircuitBreaker.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)

        # 2 failures (below threshold)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(_always_fail)

        # 1 success resets count
        cb.call(lambda: "ok")

        # 2 more failures should NOT open (count was reset)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(_always_fail)

        assert cb.state == CircuitBreaker.CLOSED


class TestCapacityError:
    """Test Bloomberg-specific capacity error handling."""

    def test_capacity_error_immediately_opens(self):
        from bloomberg_mcp.core.responses import BloombergCapacityError

        cb = CircuitBreaker(failure_threshold=5, capacity_cooldown=0.2)

        # Single capacity error should immediately open
        with pytest.raises(BloombergCapacityError):
            cb.call(_capacity_fail)

        assert cb.state == CircuitBreaker.OPEN

    def test_capacity_error_uses_longer_cooldown(self):
        from bloomberg_mcp.core.responses import BloombergCapacityError

        cb = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=0.05,     # 50ms for normal
            capacity_cooldown=0.2,     # 200ms for capacity
        )

        with pytest.raises(BloombergCapacityError):
            cb.call(_capacity_fail)

        # After 50ms (normal timeout), should still be OPEN
        time.sleep(0.08)
        assert cb.state == CircuitBreaker.OPEN

        # After 200ms (capacity timeout), should be HALF_OPEN
        time.sleep(0.15)
        assert cb.state == CircuitBreaker.HALF_OPEN


class TestSingleton:
    """Test singleton pattern."""

    def test_get_instance_returns_same_object(self):
        a = CircuitBreaker.get_instance()
        b = CircuitBreaker.get_instance()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = CircuitBreaker.get_instance()
        CircuitBreaker.reset_instance()
        b = CircuitBreaker.get_instance()
        assert a is not b


def _always_fail():
    raise ValueError("simulated failure")


def _capacity_fail():
    from bloomberg_mcp.core.responses import BloombergCapacityError
    raise BloombergCapacityError("Daily capacity reached")
