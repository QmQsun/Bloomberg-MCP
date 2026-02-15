"""Earnings Calendar tool for Bloomberg MCP.

Provides earnings calendar data for morning note context, including
recently reported companies and upcoming earnings events.
"""

from .models import (
    EarningsMode,
    ReportTiming,
    EarningsEvent,
    EarningsCalendarOutput,
    EarningsCalendarInput,
    EARNINGS_UNIVERSES,
    EARNINGS_FIELDS,
    EARNINGS_FIELDS_MINIMAL,
    resolve_universe,
)
from .calendar import (
    get_earnings_calendar,
    format_earnings_for_morning_note,
    TICKER_NAMES,
)

__all__ = [
    # Enums
    "EarningsMode",
    "ReportTiming",
    # Models
    "EarningsEvent",
    "EarningsCalendarOutput",
    "EarningsCalendarInput",
    # Constants
    "EARNINGS_UNIVERSES",
    "EARNINGS_FIELDS",
    "EARNINGS_FIELDS_MINIMAL",
    "TICKER_NAMES",
    # Functions
    "get_earnings_calendar",
    "format_earnings_for_morning_note",
    "resolve_universe",
]
