"""Economic Calendar tool for Bloomberg MCP.

Provides week-ahead economic event calendar data for morning note generation.
"""

from .models import (
    EconomicEvent,
    EconomicCalendarInput,
    EconomicCalendarOutput,
    CalendarMode,
    EventCategory,
    EventImportance,
    INDICATOR_REGISTRY,
    get_indicators_by_filter,
)
from .calendar import (
    get_economic_calendar,
    format_calendar_for_morning_note,
    ECO_FIELDS,
)

__all__ = [
    # Models
    "EconomicEvent",
    "EconomicCalendarInput",
    "EconomicCalendarOutput",
    "CalendarMode",
    "EventCategory",
    "EventImportance",
    "INDICATOR_REGISTRY",
    "get_indicators_by_filter",
    # Calendar functions
    "get_economic_calendar",
    "format_calendar_for_morning_note",
    "ECO_FIELDS",
]
