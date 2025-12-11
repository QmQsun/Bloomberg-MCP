"""Intraday data tools for Bloomberg API.

Provides functions to retrieve intraday bars and tick data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.session import BloombergSession
from ..core.requests import build_intraday_bar_request, build_intraday_tick_request
from ..core.responses import IntradayBar, parse_intraday_bar_response, parse_intraday_tick_response


def get_intraday_bars(
    security: str,
    start: datetime,
    end: datetime,
    interval: int = 5,
    event_type: str = "TRADE",
) -> List[IntradayBar]:
    """Get intraday OHLCV bars.

    Args:
        security: Security identifier (e.g., "IBM US Equity")
        start: Start datetime (converted to GMT internally)
        end: End datetime (converted to GMT internally)
        interval: Bar interval in minutes (1, 5, 15, 30, 60, etc.)
        event_type: Event type - "TRADE", "BID", "ASK", "BEST_BID", "BEST_ASK"

    Returns:
        List of IntradayBar objects with OHLCV data

    Example:
        >>> from datetime import datetime, timezone
        >>> bars = get_intraday_bars(
        ...     security="IBM US Equity",
        ...     start=datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
        ...     end=datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc),
        ...     interval=5,
        ...     event_type="TRADE",
        ... )
        >>> for bar in bars:
        ...     print(f"{bar.time}: O={bar.open} H={bar.high} L={bar.low} C={bar.close} V={bar.volume}")
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the reference data service
    service = session.get_service("//blp/refdata")

    # Build the intraday bar request
    request = build_intraday_bar_request(
        service=service,
        security=security,
        start=start,
        end=end,
        interval=interval,
        event_type=event_type,
    )

    # Send the request and get response (with parser)
    results = session.send_request(
        request,
        service_name="//blp/refdata",
        parse_func=parse_intraday_bar_response
    )

    return results


def get_intraday_ticks(
    security: str,
    start: datetime,
    end: datetime,
    event_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Get tick-by-tick data.

    Args:
        security: Security identifier (e.g., "IBM US Equity")
        start: Start datetime (converted to GMT internally)
        end: End datetime (converted to GMT internally)
        event_types: List of event types to include (e.g., ["TRADE", "BID", "ASK"])
                    If None, defaults to ["TRADE"]

    Returns:
        List of tick dictionaries with time, type, value, and size information

    Example:
        >>> from datetime import datetime, timezone
        >>> ticks = get_intraday_ticks(
        ...     security="IBM US Equity",
        ...     start=datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc),
        ...     end=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
        ...     event_types=["TRADE"],
        ... )
        >>> for tick in ticks[:10]:  # First 10 ticks
        ...     print(f"{tick['time']}: {tick['type']} @ {tick['value']}")
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the reference data service
    service = session.get_service("//blp/refdata")

    # Build the intraday tick request
    request = build_intraday_tick_request(
        service=service,
        security=security,
        start=start,
        end=end,
        event_types=event_types,
    )

    # Send the request and get response (with parser)
    results = session.send_request(
        request,
        service_name="//blp/refdata",
        parse_func=parse_intraday_tick_response
    )

    return results
