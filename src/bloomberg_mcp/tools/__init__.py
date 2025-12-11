"""High-level Bloomberg API tools.

This module provides convenient, typed interfaces for common Bloomberg operations.
All functions auto-connect to Bloomberg if not already connected.

Reference Data:
    get_reference_data - Current field values for securities

Historical Data:
    get_historical_data - Time series data with configurable periodicity

Intraday Data:
    get_intraday_bars - OHLCV bar data at specified intervals
    get_intraday_ticks - Raw tick-level trade/quote data

Discovery:
    search_securities - Find securities by name/ticker
    search_fields - Discover Bloomberg field mnemonics
    get_field_info - Detailed metadata for specific fields
"""

from .reference import get_reference_data
from .historical import get_historical_data
from .intraday import get_intraday_bars, get_intraday_ticks
from .search import search_securities, search_fields, get_field_info

__all__ = [
    # Reference data
    "get_reference_data",
    # Historical data
    "get_historical_data",
    # Intraday data
    "get_intraday_bars",
    "get_intraday_ticks",
    # Discovery
    "search_securities",
    "search_fields",
    "get_field_info",
]
