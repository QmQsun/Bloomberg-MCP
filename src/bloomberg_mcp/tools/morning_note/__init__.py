"""Morning note tools for structured market data.

This module provides specialized tools for generating Japan morning notes.
Each tool returns structured Pydantic models optimized for LLM reasoning
with pre-computed derived metrics.

LIVE DATA TOOLS:
    get_us_session_snapshot - Complete US session data (indexes, sectors, macro)
    get_japan_overnight_snapshot - Japan-relevant data (Nikkei, ADRs, watchlist)
    get_japan_watchlist - Lighter-weight watchlist only

HISTORICAL CONTEXT TOOLS (Structured):
    get_historical_context - Standard context for morning note generation
    get_sector_streaks - Current sector leadership/laggard streaks
    get_yesterday_themes - Prior note themes for continuity

HISTORICAL CONTEXT TOOLS (Exploratory):
    query_sessions - Flexible session history queries
    find_similar_sessions - Pattern matching for "last time X happened"
    query_sector_history - Deep dive into sector trends
    query_adr_history - ADR pattern analysis
    get_volume_trends - Weekly volume pattern analysis
    get_event_history - Historical event markers

STORAGE:
    store_session_snapshot - Save daily data to database
    archive_note - Archive generated notes

Example:
    >>> from bloomberg_mcp.tools.morning_note import (
    ...     get_us_session_snapshot,
    ...     get_japan_overnight_snapshot,
    ...     get_historical_context,
    ... )
    >>>
    >>> us = get_us_session_snapshot()
    >>> jp = get_japan_overnight_snapshot()
    >>> ctx = get_historical_context()
    >>>
    >>> print(f"SPX: {us.indexes['spx'].price.change_pct}%")
    >>> print(f"5-day return: {ctx.spx_5d_return}%")
    >>> print(f"Active streaks: {[s.sector for s in ctx.sector_streaks]}")
"""

from .us_session import get_us_session_snapshot
from .japan_overnight import get_japan_overnight_snapshot, get_japan_watchlist

# Historical context tools
from .historical import (
    # Structured tools
    get_historical_context,
    get_sector_streaks,
    get_yesterday_themes,
    # Exploratory tools
    query_sessions,
    find_similar_sessions,
    query_sector_history,
    query_adr_history,
    get_volume_trends,
    get_event_history,
    run_custom_query,
    # Models
    HistoricalContext,
    SessionSummary,
    SectorStreak,
    ExtremeEvent,
    ThematicRegime,
)

# Storage tools
from .storage import (
    store_session_snapshot,
    archive_note,
    update_session_character,
    add_thematic_regime,
    end_thematic_regime,
)

# Bootstrap utilities
from .bootstrap import (
    init_database,
    insert_sample_data,
)

# Re-export models for type hints
from .models import (
    # Building blocks
    PriceData,
    VolumeData,
    # Index/Sector
    IndexSnapshot,
    BreadthContext,
    SectorSnapshot,
    IndustrySnapshot,
    # Macro
    MacroInstrument,
    YieldCurve,
    MacroSnapshot,
    # Japan
    JapanProxySnapshot,
    ADRSnapshot,
    ADRSectorSummary,
    JPEquitySnapshot,
    # Complete snapshots
    USSessionSnapshot,
    JapanOvernightSnapshot,
)

# ADR screen tools
from .adr_screen import (
    get_adr_sector_summary,
    get_liquid_adrs_from_screen,
    classify_adr_sector,
)

# Dynamic screening tools
from .screening import (
    MorningNoteSignals,
    run_morning_screens,
    get_adr_signals,
    get_volume_leaders,
    get_momentum_extremes,
    calculate_sector_performance,
)

# Re-export config for customization
from .config import (
    US_INDEXES,
    SECTOR_ETFS,
    INDUSTRY_ETFS,
    JAPAN_PROXIES,
    JAPAN_ADRS,
    JAPAN_WATCHLIST,
    JAPAN_ADR_SCREEN,
    GICS_TO_SECTOR_MAP,
    GICS_SUBIND_TO_SECTOR_MAP,
)

__all__ = [
    # Live data tools
    "get_us_session_snapshot",
    "get_japan_overnight_snapshot",
    "get_japan_watchlist",
    # ADR screen tools
    "get_adr_sector_summary",
    "get_liquid_adrs_from_screen",
    "classify_adr_sector",
    # Dynamic screening tools
    "MorningNoteSignals",
    "run_morning_screens",
    "get_adr_signals",
    "get_volume_leaders",
    "get_momentum_extremes",
    "calculate_sector_performance",
    # Historical context - structured
    "get_historical_context",
    "get_sector_streaks",
    "get_yesterday_themes",
    # Historical context - exploratory
    "query_sessions",
    "find_similar_sessions",
    "query_sector_history",
    "query_adr_history",
    "get_volume_trends",
    "get_event_history",
    "run_custom_query",
    # Storage
    "store_session_snapshot",
    "archive_note",
    "update_session_character",
    "add_thematic_regime",
    "end_thematic_regime",
    # Bootstrap
    "init_database",
    "insert_sample_data",
    # Live data models
    "PriceData",
    "VolumeData",
    "IndexSnapshot",
    "BreadthContext",
    "SectorSnapshot",
    "IndustrySnapshot",
    "MacroInstrument",
    "YieldCurve",
    "MacroSnapshot",
    "JapanProxySnapshot",
    "ADRSnapshot",
    "ADRSectorSummary",
    "JPEquitySnapshot",
    "USSessionSnapshot",
    "JapanOvernightSnapshot",
    # Historical context models
    "HistoricalContext",
    "SessionSummary",
    "SectorStreak",
    "ExtremeEvent",
    "ThematicRegime",
    # Config
    "US_INDEXES",
    "SECTOR_ETFS",
    "INDUSTRY_ETFS",
    "JAPAN_PROXIES",
    "JAPAN_ADRS",
    "JAPAN_WATCHLIST",
    "JAPAN_ADR_SCREEN",
    "GICS_TO_SECTOR_MAP",
    "GICS_SUBIND_TO_SECTOR_MAP",
]
