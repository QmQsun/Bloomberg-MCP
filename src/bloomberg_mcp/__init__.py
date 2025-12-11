"""Bloomberg MCP - Data access layer for Bloomberg Terminal.

This package provides a clean Python interface to Bloomberg's API (blpapi)
for retrieving market data, reference data, and historical data.

Quick Start:
    from bloomberg_mcp.tools import get_reference_data, get_historical_data

    # Get current prices
    data = get_reference_data(["AAPL US Equity"], ["PX_LAST", "PE_RATIO"])

    # Get historical data
    hist = get_historical_data(["SPY US Equity"], ["PX_LAST"], "20240101", "20241231")

See CLAUDE.md for full API reference and usage patterns.
"""

from .core import (
    BloombergSession,
    SecurityData,
    HistoricalData,
    HistoricalDataPoint,
    IntradayBar,
    IntradayBarData,
)

from .tools import (
    get_reference_data,
    get_historical_data,
    get_intraday_bars,
    get_intraday_ticks,
    search_securities,
    search_fields,
    get_field_info,
)

__version__ = "0.1.0"

__all__ = [
    # Session management
    "BloombergSession",
    # Data types
    "SecurityData",
    "HistoricalData",
    "HistoricalDataPoint",
    "IntradayBar",
    "IntradayBarData",
    # Tools (convenience re-export)
    "get_reference_data",
    "get_historical_data",
    "get_intraday_bars",
    "get_intraday_ticks",
    "search_securities",
    "search_fields",
    "get_field_info",
]
