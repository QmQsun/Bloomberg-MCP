"""Earnings Calendar implementation using Bloomberg API.

Queries EXPECTED_REPORT_DT and earnings-related fields to build
an earnings calendar for morning note context.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Union

from .models import (
    EarningsMode,
    EarningsCalendarInput,
    EarningsCalendarOutput,
    EarningsEvent,
    ReportTiming,
    EARNINGS_FIELDS,
    EARNINGS_FIELDS_MINIMAL,
    resolve_universe,
)


# Company name mapping for cleaner output
TICKER_NAMES: Dict[str, str] = {
    "AAPL US Equity": "Apple",
    "MSFT US Equity": "Microsoft",
    "GOOGL US Equity": "Alphabet",
    "AMZN US Equity": "Amazon",
    "META US Equity": "Meta",
    "NVDA US Equity": "NVIDIA",
    "TSLA US Equity": "Tesla",
    "AMD US Equity": "AMD",
    "INTC US Equity": "Intel",
    "TSM US Equity": "TSMC",
    "ASML US Equity": "ASML",
    "AMAT US Equity": "Applied Materials",
    "LRCX US Equity": "Lam Research",
    "KLAC US Equity": "KLA",
    "MU US Equity": "Micron",
    "MRVL US Equity": "Marvell",
    "AVGO US Equity": "Broadcom",
    "QCOM US Equity": "Qualcomm",
    "TXN US Equity": "Texas Instruments",
    "ADI US Equity": "Analog Devices",
    "TM US Equity": "Toyota",
    "HMC US Equity": "Honda",
    "SONY US Equity": "Sony",
    "MUFG US Equity": "MUFG",
    "SMFG US Equity": "SMFG",
    "NMR US Equity": "Nomura",
    "NTDOY US Equity": "Nintendo",
    "JPM US Equity": "JPMorgan",
    "BAC US Equity": "BofA",
    "GS US Equity": "Goldman",
    "MS US Equity": "Morgan Stanley",
    "C US Equity": "Citi",
    "WFC US Equity": "Wells Fargo",
    "WMT US Equity": "Walmart",
    "COST US Equity": "Costco",
    "TGT US Equity": "Target",
    "HD US Equity": "Home Depot",
    "NKE US Equity": "Nike",
    "CAT US Equity": "Caterpillar",
    "DE US Equity": "Deere",
    "BA US Equity": "Boeing",
    "FDX US Equity": "FedEx",
    "UPS US Equity": "UPS",
    "GE US Equity": "GE Aerospace",
    "HON US Equity": "Honeywell",
}


def get_earnings_calendar(params: EarningsCalendarInput) -> EarningsCalendarOutput:
    """
    Get earnings calendar for the specified universe and time period.

    This function queries Bloomberg for upcoming and recent earnings
    announcements, providing context for morning note generation.

    Args:
        params: Calendar query parameters including mode, universe, days_ahead

    Returns:
        EarningsCalendarOutput with events grouped by timing relevance
    """
    from ...core.session import BloombergSession
    from ..reference import get_reference_data

    today = date.today()

    # Resolve universe
    universe_name, securities = resolve_universe(params.universe)

    if not securities:
        return EarningsCalendarOutput(
            mode=params.mode.value,
            query_date=today,
            universe_name=universe_name,
            universe_size=0,
        )

    # Calculate date windows based on mode
    if params.mode == EarningsMode.OVERNIGHT:
        # Last 24 hours + today
        lookback_start = today - timedelta(days=1)
        lookahead_end = today
    elif params.mode == EarningsMode.TODAY:
        lookback_start = today
        lookahead_end = today
    elif params.mode == EarningsMode.WEEK_AHEAD:
        lookback_start = today - timedelta(days=1)  # Include yesterday for overnight
        lookahead_end = today + timedelta(days=params.days_ahead)
    else:  # CUSTOM
        lookback_start = today - timedelta(days=1)
        lookahead_end = today + timedelta(days=params.days_ahead)

    # Select fields based on include_estimates
    fields = EARNINGS_FIELDS if params.include_estimates else EARNINGS_FIELDS_MINIMAL

    # Connect to Bloomberg and fetch data
    session = BloombergSession.get_instance()
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Query reference data
    data = get_reference_data(
        securities=securities,
        fields=fields,
    )

    # Parse results into events
    reported_recently: List[EarningsEvent] = []
    reports_today: List[EarningsEvent] = []
    reports_this_week: List[EarningsEvent] = []

    for sec in data:
        ticker = sec.security
        name = TICKER_NAMES.get(ticker, ticker.split()[0])

        # Get expected report date
        expected_dt = sec.fields.get("EXPECTED_REPORT_DT")
        announcement_dt = sec.fields.get("ANNOUNCEMENT_DT")

        # Parse dates
        report_date = _parse_date(expected_dt)
        last_reported = _parse_date(announcement_dt)

        if not report_date:
            continue

        # Create event
        event = EarningsEvent(
            ticker=ticker.split()[0],  # Just the symbol
            name=name,
            report_date=report_date,
            is_confirmed=True,  # Bloomberg dates are generally confirmed
            timing=ReportTiming.UNKNOWN,  # Would need additional field for timing
            last_reported=last_reported,
            eps_estimate=_safe_float(sec.fields.get("BEST_EPS")),
            eps_growth=_safe_float(sec.fields.get("EPS_GROWTH")),
            sales_estimate=_safe_float(sec.fields.get("BEST_SALES")),
            analyst_rating=_safe_float(sec.fields.get("BEST_ANALYST_RATING")),
            num_analysts=_safe_int(sec.fields.get("TOT_ANALYST_REC")),
            target_price=_safe_float(sec.fields.get("BEST_TARGET_PRICE")),
            current_price=_safe_float(sec.fields.get("PX_LAST")),
            change_1d=_safe_float(sec.fields.get("CHG_PCT_1D")),
        )

        # Categorize by timing
        if last_reported and last_reported >= lookback_start and last_reported <= today:
            # Recently reported
            event.report_date = last_reported  # Show actual report date
            reported_recently.append(event)
        elif report_date == today:
            reports_today.append(event)
        elif report_date > today and report_date <= lookahead_end:
            reports_this_week.append(event)

    # Sort each list
    reported_recently.sort(key=lambda e: e.report_date, reverse=True)
    reports_today.sort(key=lambda e: e.name)
    reports_this_week.sort(key=lambda e: e.report_date)

    return EarningsCalendarOutput(
        mode=params.mode.value,
        query_date=today,
        universe_name=universe_name,
        universe_size=len(securities),
        reported_recently=reported_recently,
        reports_today=reports_today,
        reports_this_week=reports_this_week,
    )


def _parse_date(value: Any) -> Optional[date]:
    """Parse a date value from Bloomberg."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # Try common formats
        for fmt in ["%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"]:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Safely convert to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def format_earnings_for_morning_note(output: EarningsCalendarOutput) -> str:
    """
    Format earnings calendar for inclusion in morning note.

    Returns a condensed format optimized for LLM consumption.
    """
    lines = []

    # Recently reported (most important for morning note)
    if output.reported_recently:
        lines.append("### Earnings Reported Overnight")
        for event in output.reported_recently[:5]:
            chg = f"{event.change_1d:+.1f}%" if event.change_1d else ""
            lines.append(f"- **{event.name}** ({event.ticker}): {chg}")
        lines.append("")

    # Reports today
    if output.reports_today:
        lines.append("### Reports Today")
        for event in output.reports_today[:5]:
            eps = f"EPS est ${event.eps_estimate:.2f}" if event.eps_estimate else ""
            lines.append(f"- **{event.name}** ({event.ticker}): {eps}")
        lines.append("")

    # Week ahead summary
    if output.reports_this_week:
        lines.append("### Week-Ahead Earnings")
        # Group by date
        by_date: Dict[date, List[EarningsEvent]] = {}
        for event in output.reports_this_week:
            if event.report_date not in by_date:
                by_date[event.report_date] = []
            by_date[event.report_date].append(event)

        for report_date in sorted(by_date.keys())[:7]:
            events = by_date[report_date]
            date_str = report_date.strftime("%a %b %d")
            names = ", ".join(e.name for e in events[:4])
            if len(events) > 4:
                names += f" (+{len(events)-4} more)"
            lines.append(f"- **{date_str}**: {names}")
        lines.append("")

    if not lines:
        return "No significant earnings events in the selected period."

    return "\n".join(lines)


__all__ = [
    "get_earnings_calendar",
    "format_earnings_for_morning_note",
    "TICKER_NAMES",
]
