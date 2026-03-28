"""Intraday bars and ticks tool handlers."""

import json
from datetime import datetime

from bloomberg_mcp.server import mcp
from bloomberg_mcp.models import IntradayBarsInput, IntradayTicksInput, ResponseFormat
from bloomberg_mcp.utils import _truncate_response


@mcp.tool(
    name="bloomberg_get_intraday_bars",
    annotations={
        "title": "Get Intraday Bars",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_intraday_bars(params: IntradayBarsInput) -> str:
    """
    Get intraday OHLCV bar data for a single security.

    Fetches candlestick/bar data at specified intervals (1, 5, 15, 30, 60 min).
    Note: Times must be in GMT timezone.

    Args:
        params: IntradayBarsInput containing security, datetime range, and interval

    Returns:
        JSON or Markdown formatted bar data with open, high, low, close, volume

    Example:
        security="AAPL US Equity", start_datetime="2024-12-10T14:30:00",
        end_datetime="2024-12-10T21:00:00", interval=60
    """
    try:
        from bloomberg_mcp.tools import get_intraday_bars

        start = datetime.fromisoformat(params.start_datetime)
        end = datetime.fromisoformat(params.end_datetime)

        bars = get_intraday_bars(
            security=params.security,
            start=start,
            end=end,
            interval=params.interval,
            event_type=params.event_type
        )

        if not bars:
            return "No intraday bar data returned for the specified parameters."

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"## Intraday Bars: {params.security}", ""]
            lines.append("| Time | Open | High | Low | Close | Volume |")
            lines.append("|------|------|------|-----|-------|--------|")
            for bar in bars[:100]:
                time_str = bar.time.strftime("%H:%M") if hasattr(bar.time, "strftime") else str(bar.time)
                lines.append(f"| {time_str} | {bar.open:.2f} | {bar.high:.2f} | {bar.low:.2f} | {bar.close:.2f} | {bar.volume:,} |")
            if len(bars) > 100:
                lines.append(f"\n*... and {len(bars) - 100} more bars*")
            result = "\n".join(lines)
        else:
            result = json.dumps([{
                "time": str(bar.time),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "num_events": bar.num_events
            } for bar in bars], indent=2)

        return _truncate_response(result)

    except Exception as e:
        return f"Error fetching intraday bars: {str(e)}"


@mcp.tool(
    name="bloomberg_get_intraday_ticks",
    annotations={
        "title": "Get Intraday Ticks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_intraday_ticks(params: IntradayTicksInput) -> str:
    """
    Get raw tick-level data for a single security.

    Fetches individual trade or quote ticks. Use sparingly as this can
    return large amounts of data. Times must be in GMT timezone.

    Args:
        params: IntradayTicksInput containing security, datetime range, and event types

    Returns:
        JSON or Markdown formatted tick data

    Example:
        security="AAPL US Equity", start_datetime="2024-12-10T14:30:00",
        end_datetime="2024-12-10T14:35:00", event_types=["TRADE"]
    """
    try:
        from bloomberg_mcp.tools import get_intraday_ticks

        start = datetime.fromisoformat(params.start_datetime)
        end = datetime.fromisoformat(params.end_datetime)

        ticks = get_intraday_ticks(
            security=params.security,
            start=start,
            end=end,
            event_types=params.event_types
        )

        if not ticks:
            return "No tick data returned for the specified parameters."

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"## Tick Data: {params.security}", f"**Total ticks**: {len(ticks)}", ""]
            for tick in ticks[:50]:
                lines.append(f"- {tick.get('time', 'N/A')}: {tick.get('value', 'N/A')} (size: {tick.get('size', 'N/A')})")
            if len(ticks) > 50:
                lines.append(f"\n*... and {len(ticks) - 50} more ticks*")
            result = "\n".join(lines)
        else:
            result = json.dumps(ticks[:1000], indent=2, default=str)
            if len(ticks) > 1000:
                result += f"\n// ... and {len(ticks) - 1000} more ticks (truncated)"

        return _truncate_response(result)

    except Exception as e:
        return f"Error fetching intraday ticks: {str(e)}"
