"""Core Bloomberg API functionality.

This module provides low-level Bloomberg API interaction:
- BloombergSession: Singleton connection manager
- Response dataclasses: SecurityData, HistoricalData, IntradayBar, etc.
- Parse functions: Convert blpapi Messages to Python objects

For most use cases, import from bloomberg_mcp.tools instead.
"""

from .session import BloombergSession
from .cache import BloombergCache, CacheTTL
from .responses import (
    # Data types
    SecurityData,
    HistoricalData,
    HistoricalDataPoint,
    IntradayBar,
    IntradayBarData,
    ScreenResult,
    # Parse functions
    parse_reference_data_response,
    parse_historical_data_response,
    parse_intraday_bar_response,
    parse_intraday_tick_response,
    parse_instrument_search_response,
    parse_field_search_response,
    parse_field_info_response,
    parse_beqs_response,
)

__all__ = [
    # Session
    "BloombergSession",
    # Cache
    "BloombergCache",
    "CacheTTL",
    # Data types
    "SecurityData",
    "HistoricalData",
    "HistoricalDataPoint",
    "IntradayBar",
    "IntradayBarData",
    "ScreenResult",
    # Parse functions
    "parse_reference_data_response",
    "parse_historical_data_response",
    "parse_intraday_bar_response",
    "parse_intraday_tick_response",
    "parse_instrument_search_response",
    "parse_field_search_response",
    "parse_field_info_response",
    "parse_beqs_response",
]
