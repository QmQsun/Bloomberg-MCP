"""Common handler infrastructure: throttle, circuit breaker, cache fallback.

Every handler calls `pre_request()` before hitting Bloomberg and
`fallback_or_error()` when Bloomberg is unavailable.
"""

import logging
from typing import Any, List, Optional, Dict

from bloomberg_mcp.core.circuit_breaker import CircuitBreaker, BloombergCircuitOpenError
from bloomberg_mcp.core.middleware import RequestThrottle, ThrottleExceededError
from bloomberg_mcp.core.cache import BloombergCache

logger = logging.getLogger(__name__)


def pre_request() -> None:
    """Run before every Bloomberg API call.

    Checks rate limit and circuit breaker state.
    Raises ThrottleExceededError or BloombergCircuitOpenError.
    """
    RequestThrottle.get_instance().check_and_record()
    # Circuit breaker is checked inside breaker.call(), not here.
    # But we can pre-check state to give a better error message.
    state = CircuitBreaker.get_instance().state
    if state == CircuitBreaker.OPEN:
        remaining = CircuitBreaker.get_instance().seconds_until_recovery
        raise BloombergCircuitOpenError(
            f"Bloomberg circuit breaker OPEN. Retry in {remaining:.0f}s.",
            retry_after=remaining,
        )


def fallback_or_error(
    error: Exception,
    tool_name: str,
    cache_key_args: Optional[Dict[str, Any]] = None,
) -> str:
    """Handle Bloomberg errors with cache fallback.

    For circuit breaker / throttle errors, try to return stale cached data.
    For other errors, return the error message.
    """
    is_infra_error = isinstance(error, (BloombergCircuitOpenError, ThrottleExceededError))

    if is_infra_error and cache_key_args:
        cache = BloombergCache.get_instance()
        stale = cache.get_stale(**cache_key_args)
        if stale is not None:
            value, age_seconds = stale
            age_min = age_seconds / 60
            logger.info(
                "Serving stale cache for %s (age: %.1f min)",
                tool_name, age_min,
            )
            if isinstance(value, str):
                return (
                    f"**Note: Bloomberg unavailable — showing cached data "
                    f"(age: {age_min:.0f} min)**\n\n{value}"
                )
            # If the cached value is structured data, we can't easily prepend a warning.
            # Return the error with a hint.
            return (
                f"Bloomberg temporarily unavailable ({error}). "
                f"Stale cached data is available but in non-string format."
            )

    return f"Error in {tool_name}: {error}"
