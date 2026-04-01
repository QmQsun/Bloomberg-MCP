"""Tests for request throttle middleware."""

import pytest

from bloomberg_mcp.core.middleware import RequestThrottle, ThrottleExceededError


@pytest.fixture(autouse=True)
def reset_throttle():
    """Reset singleton before each test."""
    RequestThrottle.reset_instance()
    yield
    RequestThrottle.reset_instance()


class TestRequestThrottle:
    def test_allows_requests_within_limit(self):
        throttle = RequestThrottle(max_per_minute=5, max_per_hour=100)
        for _ in range(5):
            throttle.check_and_record()

    def test_rejects_over_minute_limit(self):
        throttle = RequestThrottle(max_per_minute=3, max_per_hour=100)
        for _ in range(3):
            throttle.check_and_record()

        with pytest.raises(ThrottleExceededError) as exc_info:
            throttle.check_and_record()

        assert "requests/minute" in str(exc_info.value)
        assert exc_info.value.retry_after > 0

    def test_rejects_over_hour_limit(self):
        throttle = RequestThrottle(max_per_minute=1000, max_per_hour=5)
        for _ in range(5):
            throttle.check_and_record()

        with pytest.raises(ThrottleExceededError) as exc_info:
            throttle.check_and_record()

        assert "requests/hour" in str(exc_info.value)

    def test_remaining_quota(self):
        throttle = RequestThrottle(max_per_minute=10, max_per_hour=100)
        assert throttle.remaining == {"minute": 10, "hour": 100}

        for _ in range(3):
            throttle.check_and_record()

        assert throttle.remaining == {"minute": 7, "hour": 97}

    def test_singleton_pattern(self):
        a = RequestThrottle.get_instance()
        b = RequestThrottle.get_instance()
        assert a is b
