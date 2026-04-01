"""Core Bloomberg API functionality.

This module provides low-level Bloomberg API interaction:
- BloombergSession: Singleton connection manager
- Response dataclasses: SecurityData, HistoricalData, IntradayBar, etc.
- Parse functions: Convert blpapi Messages to Python objects
- CircuitBreaker: Three-state failure protection
- RequestThrottle: Rate limiting
- Validators: Response quality gates
- Logging: Structured JSON logging with metrics

For most use cases, import from bloomberg_mcp.tools instead.
"""

from .session import BloombergSession
from .cache import BloombergCache, CacheTTL
from .circuit_breaker import CircuitBreaker, BloombergCircuitOpenError
from .middleware import RequestThrottle, ThrottleExceededError
from .validators import (
    validate_field_count,
    validate_reference_response,
    validate_historical_response,
    validate_bulk_response,
    ValidationWarning,
)
from .logging import setup_logging, log_tool_call, ToolCallMetrics
from .responses import (
    # Exceptions
    BloombergCapacityError,
    # Data types
    SecurityData,
    HistoricalData,
    HistoricalDataPoint,
    IntradayBar,
    IntradayBarData,
    ScreenResult,
    StudyDataPoint,
    StudyResult,
    # Parse functions
    parse_reference_data_response,
    parse_historical_data_response,
    parse_intraday_bar_response,
    parse_intraday_tick_response,
    parse_instrument_search_response,
    parse_field_search_response,
    parse_field_info_response,
    parse_beqs_response,
    parse_study_response,
)

__all__ = [
    # Session
    "BloombergSession",
    # Cache
    "BloombergCache",
    "CacheTTL",
    # Circuit breaker
    "CircuitBreaker",
    "BloombergCircuitOpenError",
    # Throttle
    "RequestThrottle",
    "ThrottleExceededError",
    # Validators
    "validate_field_count",
    "validate_reference_response",
    "validate_historical_response",
    "validate_bulk_response",
    "ValidationWarning",
    # Logging
    "setup_logging",
    "log_tool_call",
    "ToolCallMetrics",
    # Exceptions
    "BloombergCapacityError",
    # Data types
    "SecurityData",
    "HistoricalData",
    "HistoricalDataPoint",
    "IntradayBar",
    "IntradayBarData",
    "ScreenResult",
    "StudyDataPoint",
    "StudyResult",
    # Parse functions
    "parse_reference_data_response",
    "parse_historical_data_response",
    "parse_intraday_bar_response",
    "parse_intraday_tick_response",
    "parse_instrument_search_response",
    "parse_field_search_response",
    "parse_field_info_response",
    "parse_beqs_response",
    "parse_study_response",
]
