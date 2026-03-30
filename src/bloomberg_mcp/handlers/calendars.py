"""Economic and earnings calendar tool handlers."""

import json
import logging

from bloomberg_mcp._mcp_instance import mcp
from bloomberg_mcp.models import EconomicCalendarToolInput, EarningsCalendarToolInput, ResponseFormat

logger = logging.getLogger(__name__)


@mcp.tool(
    name="bloomberg_get_economic_calendar",
    annotations={
        "title": "Get Economic Calendar",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_economic_calendar(params: EconomicCalendarToolInput) -> str:
    """
    Get upcoming economic events and data releases.

    Returns a calendar of scheduled economic releases for major economies.
    Essential for morning note generation to understand week-ahead catalysts.

    MODES:
    - week_ahead: Next 7 days of scheduled releases (default)
    - today: Today's releases only
    - recent: Releases from last 24 hours
    - central_bank: Central bank decisions (30-day window)

    REGIONS:
    - US: Fed, CPI, NFP, GDP, ISM, etc.
    - Japan: BoJ, CPI, Tankan, trade data, etc.
    - Europe: ECB, BoE, Eurozone CPI/GDP
    - China: PBoC, CPI, GDP, PMI

    CATEGORIES:
    - central_bank: Rate decisions (FOMC, BoJ, ECB, BoE)
    - inflation: CPI, PPI, PCE deflators
    - employment: NFP, unemployment, jobless claims
    - growth: GDP, retail sales
    - manufacturing: ISM, PMI, Tankan
    - trade: Trade balance, exports

    IMPORTANCE LEVELS:
    - high: Market-moving events (NFP, CPI, central bank)
    - medium: Notable releases (PMI, retail sales)
    - low: Minor releases
    - all: Include everything

    Args:
        params: EconomicCalendarToolInput with mode, regions, categories, importance

    Returns:
        Markdown table or JSON of upcoming economic events

    Example:
        mode="week_ahead", regions=["US", "Japan"], importance="high"
    """
    try:
        from bloomberg_mcp.tools.economic_calendar import (
            get_economic_calendar,
            format_calendar_for_morning_note,
            EconomicCalendarInput,
            CalendarMode,
            EventImportance,
        )

        mode_map = {
            "week_ahead": CalendarMode.WEEK_AHEAD,
            "today": CalendarMode.TODAY,
            "recent": CalendarMode.RECENT,
            "central_bank": CalendarMode.CENTRAL_BANK,
        }
        importance_map = {
            "high": EventImportance.HIGH,
            "medium": EventImportance.MEDIUM,
            "low": EventImportance.LOW,
            "all": EventImportance.ALL,
        }

        calendar_input = EconomicCalendarInput(
            mode=mode_map.get(params.mode.value, CalendarMode.WEEK_AHEAD),
            regions=params.regions,
            categories=params.categories,
            importance=importance_map.get(params.importance.lower(), EventImportance.HIGH),
            days_ahead=params.days_ahead,
            response_format=params.response_format.value,
        )

        result = get_economic_calendar(calendar_input)

        if params.response_format == ResponseFormat.MARKDOWN:
            return format_calendar_for_morning_note(result)
        else:
            return json.dumps(result.to_dict(), indent=2)

    except Exception as e:
        logger.exception("Error fetching economic calendar")
        return f"Error fetching economic calendar: {str(e)}"


@mcp.tool(
    name="bloomberg_get_earnings_calendar",
    annotations={
        "title": "Get Earnings Calendar",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_earnings_calendar(params: EarningsCalendarToolInput) -> str:
    """
    Get upcoming and recent earnings announcements.

    Returns an earnings calendar showing what reported overnight (for morning
    context) and what reports in the coming days. Essential for understanding
    potential catalysts and sector read-throughs.

    MODES:
    - overnight: What reported in last 24 hours (key for morning notes)
    - today: Companies reporting today
    - week_ahead: Next 7 days of earnings (default)

    NAMED UNIVERSES:
    - MORNING_NOTE: Combined universe for Japan morning note context
    - MEGA_CAP_TECH: FAANG + MSFT, NVDA, TSLA
    - SEMI_LEADERS: NVDA, AMD, TSM, ASML, AMAT, LRCX, MU, AVGO, etc.
    - JAPAN_ADRS: TM, HMC, SONY, MUFG, SMFG, NMR, NTDOY
    - US_FINANCIALS: JPM, BAC, GS, MS, C, WFC
    - CONSUMER: WMT, COST, TGT, HD, NKE
    - INDUSTRIALS: CAT, DE, BA, FDX, UPS, GE, HON

    OUTPUT STRUCTURE:
    - reported_recently: Companies that reported in last 24h (with price move)
    - reports_today: Companies reporting today (with estimates)
    - reports_this_week: Upcoming earnings by date

    JAPAN TRADING CONTEXT:
    Use this to understand:
    1. What US earnings moved markets overnight (affects Japan ADRs/related)
    2. Semiconductor earnings \u2192 read-through to 8035, 6857, 6920
    3. Financial earnings \u2192 read-through to 8306, 8411

    Args:
        params: EarningsCalendarToolInput with mode, universe, days_ahead

    Returns:
        Markdown or JSON with earnings events grouped by timing

    Example:
        mode="week_ahead", universe="SEMI_LEADERS", days_ahead=7
    """
    try:
        from bloomberg_mcp.tools.earnings_calendar import (
            get_earnings_calendar,
            format_earnings_for_morning_note,
            EarningsCalendarInput,
            EarningsMode,
        )

        mode_map = {
            "overnight": EarningsMode.OVERNIGHT,
            "today": EarningsMode.TODAY,
            "week_ahead": EarningsMode.WEEK_AHEAD,
        }

        calendar_input = EarningsCalendarInput(
            mode=mode_map.get(params.mode.value, EarningsMode.WEEK_AHEAD),
            universe=params.universe,
            days_ahead=params.days_ahead,
            include_estimates=params.include_estimates,
            response_format=params.response_format.value,
        )

        result = get_earnings_calendar(calendar_input)

        if params.response_format == ResponseFormat.MARKDOWN:
            return format_earnings_for_morning_note(result)
        else:
            return json.dumps(result.to_dict(), indent=2)

    except Exception as e:
        logger.exception("Error fetching earnings calendar")
        return f"Error fetching earnings calendar: {str(e)}"
