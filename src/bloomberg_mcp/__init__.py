"""Bloomberg MCP - Data access layer for Bloomberg Terminal.

This package provides a clean Python interface to Bloomberg's API (blpapi)
for retrieving market data, reference data, and historical data.

Quick Start:
    from bloomberg_mcp.tools import get_reference_data, get_historical_data

    # Get current prices
    data = get_reference_data(["AAPL US Equity"], ["PX_LAST", "PE_RATIO"])

    # Get historical data
    hist = get_historical_data(["SPY US Equity"], ["PX_LAST"], "20240101", "20241231")

Morning Notes:
    from bloomberg_mcp.tools import get_us_session_snapshot, get_japan_overnight_snapshot

    us = get_us_session_snapshot()
    jp = get_japan_overnight_snapshot()

Dynamic Screening:
    from bloomberg_mcp.tools.dynamic_screening import (
        DynamicScreen, FieldSets, F, MorningNoteScreens
    )

    # Build and run a custom screen
    result = (
        DynamicScreen("High RVOL ADRs")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.RVOL + FieldSets.MOMENTUM)
        .filter(F.rvol > 2.0, F.CHG_PCT_1D > 0)
        .rank_by("rvol", descending=True)
        .top(10)
        .run()
    )

    # Or use pre-configured screens
    result = MorningNoteScreens.high_rvol_adrs().run()

Historical Context:
    from bloomberg_mcp.tools.morning_note import (
        get_historical_context,
        find_similar_sessions,
        store_session_snapshot,
    )

    ctx = get_historical_context()
    similar = find_similar_sessions({"breadth_spread": {"gt": 0.8}})

See CLAUDE.md for full API reference and usage patterns.
"""

from .core import (
    BloombergSession,
    SecurityData,
    HistoricalData,
    HistoricalDataPoint,
    IntradayBar,
    IntradayBarData,
    ScreenResult,
    BloombergCapacityError,
)

from .tools import (
    get_reference_data,
    get_historical_data,
    get_intraday_bars,
    get_intraday_ticks,
    search_securities,
    search_fields,
    get_field_info,
    run_screen,
    # Morning note tools
    get_us_session_snapshot,
    get_japan_overnight_snapshot,
    get_japan_watchlist,
)

# Morning note models (for type hints)
from .tools.morning_note import (
    USSessionSnapshot,
    JapanOvernightSnapshot,
    # Historical context
    HistoricalContext,
    get_historical_context,
    find_similar_sessions,
    query_sessions,
    store_session_snapshot,
    init_database,
)

# Dynamic screening (lazy import to avoid circular deps)
# Use: from bloomberg_mcp.tools.dynamic_screening import DynamicScreen, F, FieldSets

__version__ = "1.2.1"

__all__ = [
    # Session management
    "BloombergSession",
    # Exceptions
    "BloombergCapacityError",
    # Data types
    "SecurityData",
    "HistoricalData",
    "HistoricalDataPoint",
    "IntradayBar",
    "IntradayBarData",
    "ScreenResult",
    # Tools (convenience re-export)
    "get_reference_data",
    "get_historical_data",
    "get_intraday_bars",
    "get_intraday_ticks",
    "search_securities",
    "search_fields",
    "get_field_info",
    "run_screen",
    # Morning note tools
    "get_us_session_snapshot",
    "get_japan_overnight_snapshot",
    "get_japan_watchlist",
    # Morning note models
    "USSessionSnapshot",
    "JapanOvernightSnapshot",
    # Historical context
    "HistoricalContext",
    "get_historical_context",
    "find_similar_sessions",
    "query_sessions",
    "store_session_snapshot",
    "init_database",
]
