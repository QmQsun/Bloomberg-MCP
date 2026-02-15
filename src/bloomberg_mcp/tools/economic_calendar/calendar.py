"""Economic Calendar implementation using Bloomberg API.

Queries ECO_RELEASE_DT, ECO_RELEASE_TIME, OBSERVATION_PERIOD, and PX_LAST
for economic indicator tickers to build a week-ahead calendar.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from .models import (
    CalendarMode,
    EconomicCalendarInput,
    EconomicCalendarOutput,
    EconomicEvent,
    EventImportance,
    INDICATOR_REGISTRY,
    get_indicators_by_filter,
)


# Bloomberg fields for economic calendar
ECO_FIELDS = [
    "ECO_RELEASE_DT",      # Next release date
    "ECO_RELEASE_TIME",    # Release time (local)
    "OBSERVATION_PERIOD",  # Period covered (e.g., "Dec", "4Q")
    "PX_LAST",             # Prior/current value
]


def get_economic_calendar(params: EconomicCalendarInput) -> EconomicCalendarOutput:
    """
    Get economic calendar events for the specified period.

    This function queries Bloomberg for upcoming economic releases using
    the ECO_RELEASE_DT and related fields on economic indicator tickers.

    Args:
        params: Calendar query parameters including mode, regions, categories, importance

    Returns:
        EconomicCalendarOutput with list of upcoming events
    """
    from ...core.session import BloombergSession

    # Calculate date range based on mode
    today = date.today()

    if params.mode == CalendarMode.TODAY:
        start_date = today
        end_date = today
    elif params.mode == CalendarMode.WEEK_AHEAD:
        start_date = today
        end_date = today + timedelta(days=params.days_ahead)
    elif params.mode == CalendarMode.RECENT:
        # Look back 24 hours for recent releases
        start_date = today - timedelta(days=1)
        end_date = today
    elif params.mode == CalendarMode.CENTRAL_BANK:
        # Central bank decisions can be scheduled far out
        start_date = today
        end_date = today + timedelta(days=30)
    elif params.mode == CalendarMode.CUSTOM:
        start_date = today
        end_date = today + timedelta(days=params.days_ahead)
    else:
        start_date = today
        end_date = today + timedelta(days=7)

    # Get filtered indicators
    categories = params.categories
    if params.mode == CalendarMode.CENTRAL_BANK:
        # Override categories for central bank mode
        categories = ["central_bank"]

    indicators = get_indicators_by_filter(
        regions=params.regions,
        categories=categories,
        importance=params.importance,
    )

    if not indicators:
        return EconomicCalendarOutput(
            mode=params.mode.value,
            query_date=today,
            date_range_start=start_date,
            date_range_end=end_date,
            total_events=0,
            events=[],
        )

    # Build list of tickers to query
    tickers = [ind.ticker for ind in indicators]
    ticker_metadata = {ind.ticker: ind for ind in indicators}

    # Connect to Bloomberg and fetch data
    session = BloombergSession.get_instance()
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Query reference data for economic indicators
    from ..reference import get_reference_data

    data = get_reference_data(
        securities=tickers,
        fields=ECO_FIELDS,
    )

    # Parse results into events
    events: List[EconomicEvent] = []

    for sec in data:
        ticker = sec.security
        meta = ticker_metadata.get(ticker)
        if not meta:
            continue

        # Extract release date
        release_dt_raw = sec.fields.get("ECO_RELEASE_DT")
        if not release_dt_raw:
            continue

        # Parse release date (Bloomberg returns as datetime or string)
        if isinstance(release_dt_raw, datetime):
            release_date = release_dt_raw.date()
        elif isinstance(release_dt_raw, date):
            release_date = release_dt_raw
        elif isinstance(release_dt_raw, str):
            try:
                release_date = datetime.strptime(release_dt_raw, "%Y-%m-%d").date()
            except ValueError:
                try:
                    release_date = datetime.strptime(release_dt_raw, "%Y%m%d").date()
                except ValueError:
                    continue
        else:
            continue

        # Filter by date range
        if release_date < start_date or release_date > end_date:
            continue

        # Extract other fields
        release_time = sec.fields.get("ECO_RELEASE_TIME")
        if release_time:
            # Format time string (Bloomberg may return as datetime or string)
            if isinstance(release_time, datetime):
                release_time = release_time.strftime("%H:%M")
            elif isinstance(release_time, str):
                # Keep as-is if already formatted
                pass
            else:
                release_time = str(release_time)

        observation_period = sec.fields.get("OBSERVATION_PERIOD")
        if observation_period:
            observation_period = str(observation_period)

        prior_value = sec.fields.get("PX_LAST")
        if prior_value is not None:
            try:
                prior_value = float(prior_value)
            except (ValueError, TypeError):
                prior_value = None

        # Create event
        event = EconomicEvent(
            ticker=ticker,
            name=meta.name,
            short_name=meta.short_name,
            region=meta.region,
            category=meta.category.value,
            importance=meta.importance.value,
            release_date=release_date,
            release_time=release_time,
            observation_period=observation_period,
            prior_value=prior_value,
            unit=meta.unit,
        )
        events.append(event)

    # Sort events by date and importance
    importance_order = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e.release_date, importance_order.get(e.importance, 3)))

    return EconomicCalendarOutput(
        mode=params.mode.value,
        query_date=today,
        date_range_start=start_date,
        date_range_end=end_date,
        total_events=len(events),
        events=events,
    )


def format_calendar_for_morning_note(output: EconomicCalendarOutput) -> str:
    """
    Format economic calendar for inclusion in morning note.

    Returns a condensed markdown format suitable for the morning note template.
    """
    if not output.events:
        return "No major economic events scheduled."

    lines = ["## Week-Ahead Economic Calendar", ""]

    # Group events by date
    events_by_date: dict = {}
    for event in output.events:
        date_key = event.release_date
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    for event_date in sorted(events_by_date.keys()):
        date_str = event_date.strftime("%A, %b %d")
        lines.append(f"### {date_str}")

        for event in events_by_date[event_date]:
            time_str = event.release_time or "TBD"
            prior_str = f"{event.prior_value}{event.unit}" if event.prior_value is not None else ""
            period_str = f"({event.observation_period})" if event.observation_period else ""

            # Format based on importance
            if event.importance == "high":
                lines.append(f"- **{event.short_name}** {period_str} @ {time_str} | Prior: {prior_str}")
            else:
                lines.append(f"- {event.short_name} {period_str} @ {time_str} | Prior: {prior_str}")

        lines.append("")

    return "\n".join(lines)


__all__ = [
    "get_economic_calendar",
    "format_calendar_for_morning_note",
    "ECO_FIELDS",
]
