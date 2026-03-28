"""Enum types for Bloomberg MCP tools."""

from enum import Enum


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class EconomicCalendarModeInput(str, Enum):
    """Calendar query mode."""
    WEEK_AHEAD = "week_ahead"
    TODAY = "today"
    RECENT = "recent"
    CENTRAL_BANK = "central_bank"


class EarningsModeInput(str, Enum):
    """Earnings calendar query mode."""
    OVERNIGHT = "overnight"
    TODAY = "today"
    WEEK_AHEAD = "week_ahead"
