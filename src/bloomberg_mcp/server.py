#!/usr/bin/env python3
"""
Bloomberg MCP Server - FastMCP wrapper for Bloomberg data access.

This server exposes Bloomberg data tools via MCP protocol, enabling
LLMs to fetch market data, reference data, and historical data.
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("bloomberg_mcp")

# Constants
CHARACTER_LIMIT = 50000
BLOOMBERG_HOST = os.environ.get("BLOOMBERG_HOST", "localhost")
BLOOMBERG_PORT = int(os.environ.get("BLOOMBERG_PORT", "8194"))


# Response format enum
class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ============================================================================
# Input Models
# ============================================================================

class ReferenceDataInput(BaseModel):
    """Input for fetching current field values for securities."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    securities: List[str] = Field(
        ...,
        description="List of security identifiers (e.g., ['AAPL US Equity', 'MSFT US Equity'])",
        min_length=1,
        max_length=100
    )
    fields: List[str] = Field(
        ...,
        description="List of Bloomberg field mnemonics (e.g., ['PX_LAST', 'PE_RATIO', 'VOLUME'])",
        min_length=1,
        max_length=50
    )
    overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional field overrides as key-value pairs"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' for structured data or 'markdown' for readable format"
    )


class HistoricalDataInput(BaseModel):
    """Input for fetching historical time series data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    securities: List[str] = Field(
        ...,
        description="List of security identifiers",
        min_length=1,
        max_length=50
    )
    fields: List[str] = Field(
        ...,
        description="List of Bloomberg field mnemonics",
        min_length=1,
        max_length=25
    )
    start_date: str = Field(
        ...,
        description="Start date in YYYYMMDD format (e.g., '20240101')",
        pattern=r"^\d{8}$"
    )
    end_date: str = Field(
        ...,
        description="End date in YYYYMMDD format (e.g., '20241231')",
        pattern=r"^\d{8}$"
    )
    periodicity: str = Field(
        default="DAILY",
        description="Data periodicity: DAILY, WEEKLY, MONTHLY, QUARTERLY, or YEARLY"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format"
    )

    @field_validator("periodicity")
    @classmethod
    def validate_periodicity(cls, v: str) -> str:
        valid = ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"]
        v = v.upper()
        if v not in valid:
            raise ValueError(f"periodicity must be one of {valid}")
        return v


class IntradayBarsInput(BaseModel):
    """Input for fetching intraday OHLCV bar data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    security: str = Field(
        ...,
        description="Single security identifier (e.g., 'AAPL US Equity')",
        min_length=1
    )
    start_datetime: str = Field(
        ...,
        description="Start datetime in ISO format (e.g., '2024-12-10T14:30:00'). Times are in GMT."
    )
    end_datetime: str = Field(
        ...,
        description="End datetime in ISO format (e.g., '2024-12-10T21:00:00'). Times are in GMT."
    )
    interval: int = Field(
        default=60,
        description="Bar interval in minutes: 1, 5, 15, 30, or 60",
        ge=1,
        le=60
    )
    event_type: str = Field(
        default="TRADE",
        description="Event type: TRADE, BID, or ASK"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format"
    )


class IntradayTicksInput(BaseModel):
    """Input for fetching raw tick data."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    security: str = Field(
        ...,
        description="Single security identifier",
        min_length=1
    )
    start_datetime: str = Field(
        ...,
        description="Start datetime in ISO format. Times are in GMT."
    )
    end_datetime: str = Field(
        ...,
        description="End datetime in ISO format. Times are in GMT."
    )
    event_types: List[str] = Field(
        default=["TRADE"],
        description="Event types to include: TRADE, BID, ASK"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format"
    )


class SearchSecuritiesInput(BaseModel):
    """Input for searching securities by name or ticker."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search query (e.g., 'Apple', 'AAPL', 'Microsoft')",
        min_length=1,
        max_length=100
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=50
    )
    yellow_key: Optional[str] = Field(
        default=None,
        description="Filter by asset class: Equity, Index, Comdty, Curncy, Corp, Govt, Mtge, Muni, Pfd"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class SearchFieldsInput(BaseModel):
    """Input for discovering Bloomberg field mnemonics."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search query for field names (e.g., 'price earnings', 'dividend', 'volume')",
        min_length=1,
        max_length=100
    )
    field_type: Optional[str] = Field(
        default=None,
        description="Filter by field type: Static, RealTime, or Historical"
    )
    max_results: int = Field(
        default=20,
        description="Maximum number of results",
        ge=1,
        le=100
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class FieldInfoInput(BaseModel):
    """Input for getting detailed field metadata."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    field_ids: List[str] = Field(
        ...,
        description="List of field mnemonics to look up (e.g., ['PX_LAST', 'PE_RATIO'])",
        min_length=1,
        max_length=25
    )
    return_documentation: bool = Field(
        default=True,
        description="Include detailed field documentation"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class RunScreenInput(BaseModel):
    """Input for running a Bloomberg equity screen (EQS)."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    screen_name: str = Field(
        ...,
        description="Name of the saved screen (e.g., 'Japan_ADR_Universe'). Must match exactly as saved in Bloomberg Terminal.",
        min_length=1,
        max_length=100
    )
    screen_type: str = Field(
        default="PRIVATE",
        description="Screen type: 'PRIVATE' for user-saved screens, 'GLOBAL' for Bloomberg example screens"
    )
    group: Optional[str] = Field(
        default=None,
        description="Optional folder/group name if screen is organized in folders"
    )
    max_results: Optional[int] = Field(
        default=None,
        description="Maximum number of securities to return (None for all)",
        ge=1,
        le=1000
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' for structured data or 'markdown' for readable format"
    )

    @field_validator("screen_type")
    @classmethod
    def validate_screen_type(cls, v: str) -> str:
        valid = ["PRIVATE", "GLOBAL"]
        v = v.upper()
        if v not in valid:
            raise ValueError(f"screen_type must be one of {valid}")
        return v


# ============================================================================
# Helper Functions
# ============================================================================

def _get_session():
    """Get Bloomberg session with configured host/port."""
    from bloomberg_mcp.core.session import BloombergSession

    # Reset singleton to use new host/port if needed
    session = BloombergSession.get_instance(host=BLOOMBERG_HOST, port=BLOOMBERG_PORT)

    if not session.is_connected():
        if not session.connect():
            raise RuntimeError(
                f"Failed to connect to Bloomberg Terminal at {BLOOMBERG_HOST}:{BLOOMBERG_PORT}. "
                "Ensure Bloomberg Terminal is running and the API is enabled."
            )
    return session


def _format_security_data(data, response_format: ResponseFormat) -> str:
    """Format SecurityData results."""
    if response_format == ResponseFormat.MARKDOWN:
        lines = []
        for sec in data:
            lines.append(f"## {sec.security}")
            if sec.errors:
                lines.append(f"**Errors**: {', '.join(sec.errors)}")
            for field, value in sec.fields.items():
                lines.append(f"- **{field}**: {value}")
            lines.append("")
        return "\n".join(lines) if lines else "No data returned."
    else:
        return json.dumps([{
            "security": sec.security,
            "fields": sec.fields,
            "errors": sec.errors
        } for sec in data], indent=2, default=str)


def _format_historical_data(data, response_format: ResponseFormat) -> str:
    """Format HistoricalData results."""
    if response_format == ResponseFormat.MARKDOWN:
        lines = []
        for hist in data:
            lines.append(f"## {hist.security}")
            if hist.errors:
                lines.append(f"**Errors**: {', '.join(hist.errors)}")
            lines.append(f"**Data points**: {len(hist.data)}")
            if hist.data:
                lines.append("\n| Date | " + " | ".join(k for k in hist.data[0].keys() if k != "date") + " |")
                lines.append("|---" * (len(hist.data[0])) + "|")
                for row in hist.data[:50]:  # Limit rows in markdown
                    date_str = row.get("date", "")
                    if hasattr(date_str, "strftime"):
                        date_str = date_str.strftime("%Y-%m-%d")
                    values = [str(v) for k, v in row.items() if k != "date"]
                    lines.append(f"| {date_str} | " + " | ".join(values) + " |")
                if len(hist.data) > 50:
                    lines.append(f"\n*... and {len(hist.data) - 50} more rows*")
            lines.append("")
        return "\n".join(lines) if lines else "No data returned."
    else:
        return json.dumps([{
            "security": hist.security,
            "data": hist.data,
            "errors": hist.errors
        } for hist in data], indent=2, default=str)


def _truncate_response(result: str) -> str:
    """Truncate response if it exceeds character limit."""
    if len(result) > CHARACTER_LIMIT:
        return result[:CHARACTER_LIMIT] + f"\n\n... Response truncated (exceeded {CHARACTER_LIMIT} characters)"
    return result


def _format_screen_result(result, response_format: ResponseFormat, max_results: Optional[int] = None) -> str:
    """Format ScreenResult for output."""
    from bloomberg_mcp.core import ScreenResult

    # Limit results if requested
    securities = result.securities
    field_data = result.field_data
    if max_results:
        securities = securities[:max_results]
        field_data = field_data[:max_results]

    if response_format == ResponseFormat.MARKDOWN:
        lines = [
            f"## Screen: {result.screen_name}",
            f"**Securities found**: {len(result.securities)}" + (f" (showing {len(securities)})" if max_results else ""),
            ""
        ]

        if result.errors:
            lines.append(f"**Errors**: {', '.join(result.errors)}")
            lines.append("")

        if result.columns:
            lines.append(f"**Columns**: {', '.join(result.columns)}")
            lines.append("")

        # Create table if we have field data
        if field_data:
            # Determine columns to show (limit width)
            show_cols = ["security"] + [c for c in result.columns if c != "Ticker"][:5]
            lines.append("| " + " | ".join(show_cols) + " |")
            lines.append("|" + "---|" * len(show_cols))

            for row in field_data[:100]:
                values = []
                for col in show_cols:
                    val = row.get(col, "")
                    if isinstance(val, float):
                        val = f"{val:.2f}"
                    values.append(str(val)[:20])
                lines.append("| " + " | ".join(values) + " |")

            if len(field_data) > 100:
                lines.append(f"\n*... and {len(field_data) - 100} more rows*")

        return "\n".join(lines)
    else:
        return json.dumps({
            "screen_name": result.screen_name,
            "total_securities": len(result.securities),
            "securities": securities,
            "field_data": field_data,
            "columns": result.columns,
            "errors": result.errors
        }, indent=2, default=str)


# ============================================================================
# Tools
# ============================================================================

@mcp.tool(
    name="bloomberg_get_reference_data",
    annotations={
        "title": "Get Reference Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_reference_data(params: ReferenceDataInput) -> str:
    """
    Get current field values for one or more securities from Bloomberg.

    This tool fetches real-time or static reference data for securities.
    Use it to get current prices, valuations, fundamentals, and other metrics.

    Common fields:
    - Price: PX_LAST, PX_BID, PX_ASK, PX_OPEN, PX_HIGH, PX_LOW, VOLUME
    - Valuation: PE_RATIO, PX_TO_BOOK_RATIO, EV_TO_EBITDA, DIVIDEND_YIELD
    - Fundamentals: RETURN_ON_EQUITY, GROSS_MARGIN, MARKET_CAP

    Args:
        params: ReferenceDataInput containing securities, fields, and options

    Returns:
        JSON or Markdown formatted data with field values for each security

    Example:
        securities=["AAPL US Equity"], fields=["PX_LAST", "PE_RATIO"]
    """
    try:
        from bloomberg_mcp.tools import get_reference_data

        data = get_reference_data(
            securities=params.securities,
            fields=params.fields,
            overrides=params.overrides
        )

        result = _format_security_data(data, params.response_format)
        return _truncate_response(result)

    except Exception as e:
        return f"Error fetching reference data: {str(e)}"


@mcp.tool(
    name="bloomberg_get_historical_data",
    annotations={
        "title": "Get Historical Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_historical_data(params: HistoricalDataInput) -> str:
    """
    Get historical time series data for securities from Bloomberg.

    Fetches historical price and fundamental data over a date range.
    Supports daily, weekly, monthly, quarterly, and yearly periodicity.

    Args:
        params: HistoricalDataInput containing securities, fields, date range, and periodicity

    Returns:
        JSON or Markdown formatted time series data

    Example:
        securities=["SPY US Equity"], fields=["PX_LAST"],
        start_date="20240101", end_date="20241231", periodicity="DAILY"
    """
    try:
        from bloomberg_mcp.tools import get_historical_data

        data = get_historical_data(
            securities=params.securities,
            fields=params.fields,
            start_date=params.start_date,
            end_date=params.end_date,
            periodicity=params.periodicity
        )

        result = _format_historical_data(data, params.response_format)
        return _truncate_response(result)

    except Exception as e:
        return f"Error fetching historical data: {str(e)}"


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


@mcp.tool(
    name="bloomberg_search_securities",
    annotations={
        "title": "Search Securities",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_search_securities(params: SearchSecuritiesInput) -> str:
    """
    Search for securities by name, ticker, or description.

    Use this to find the correct Bloomberg identifier for a security
    before fetching data. Returns security identifiers and descriptions.

    Args:
        params: SearchSecuritiesInput containing query and filters

    Returns:
        List of matching securities with their Bloomberg identifiers

    Example:
        query="Apple", yellow_key="Equity"
    """
    try:
        from bloomberg_mcp.tools import search_securities

        results = search_securities(
            query=params.query,
            max_results=params.max_results,
            yellow_key=params.yellow_key
        )

        if not results:
            return f"No securities found matching '{params.query}'"

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"## Security Search: '{params.query}'", ""]
            for r in results:
                lines.append(f"- **{r.get('security', 'N/A')}**: {r.get('description', 'N/A')}")
            result = "\n".join(lines)
        else:
            result = json.dumps(results, indent=2)

        return _truncate_response(result)

    except Exception as e:
        return f"Error searching securities: {str(e)}"


@mcp.tool(
    name="bloomberg_search_fields",
    annotations={
        "title": "Search Fields",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_search_fields(params: SearchFieldsInput) -> str:
    """
    Search for Bloomberg field mnemonics by keyword.

    Bloomberg has 30,000+ fields. Use this tool to discover the correct
    field mnemonic for the data you need. Always search before assuming
    a field name.

    Args:
        params: SearchFieldsInput containing search query and filters

    Returns:
        List of matching fields with IDs and descriptions

    Example:
        query="price earnings growth" -> finds PEG_RATIO
        query="dividend yield" -> finds DIVIDEND_YIELD, etc.
    """
    try:
        from bloomberg_mcp.tools import search_fields

        results = search_fields(
            query=params.query,
            field_type=params.field_type
        )

        # Limit results
        results = results[:params.max_results]

        if not results:
            return f"No fields found matching '{params.query}'"

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"## Field Search: '{params.query}'", ""]
            for r in results:
                lines.append(f"- **{r.get('id', 'N/A')}**: {r.get('description', 'N/A')}")
            result = "\n".join(lines)
        else:
            result = json.dumps(results, indent=2)

        return _truncate_response(result)

    except Exception as e:
        return f"Error searching fields: {str(e)}"


@mcp.tool(
    name="bloomberg_get_field_info",
    annotations={
        "title": "Get Field Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_field_info(params: FieldInfoInput) -> str:
    """
    Get detailed metadata about specific Bloomberg fields.

    Returns documentation, data types, and usage information for
    the specified field mnemonics.

    Args:
        params: FieldInfoInput containing field IDs to look up

    Returns:
        Detailed field information including data type and documentation

    Example:
        field_ids=["PX_LAST", "PE_RATIO"]
    """
    try:
        from bloomberg_mcp.tools import get_field_info

        results = get_field_info(
            field_ids=params.field_ids,
            return_documentation=params.return_documentation
        )

        if not results:
            return f"No field information found for: {params.field_ids}"

        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["## Field Information", ""]
            for f in results:
                lines.append(f"### {f.get('id', 'N/A')}")
                lines.append(f"- **Description**: {f.get('description', 'N/A')}")
                if f.get('datatype'):
                    lines.append(f"- **Data Type**: {f.get('datatype')}")
                if f.get('categoryName'):
                    lines.append(f"- **Category**: {f.get('categoryName')}")
                if f.get('documentation'):
                    lines.append(f"- **Documentation**: {f.get('documentation')}")
                lines.append("")
            result = "\n".join(lines)
        else:
            result = json.dumps(results, indent=2)

        return _truncate_response(result)

    except Exception as e:
        return f"Error fetching field info: {str(e)}"


@mcp.tool(
    name="bloomberg_run_screen",
    annotations={
        "title": "Run Equity Screen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_run_screen(params: RunScreenInput) -> str:
    """
    Run a pre-saved Bloomberg equity screen (EQS).

    Executes a saved screen from Bloomberg's Equity Screening tool and returns
    the list of matching securities along with any output fields defined in
    the screen.

    Screens must be created and saved in Bloomberg Terminal EQS <GO> before
    they can be accessed via API.

    Args:
        params: RunScreenInput containing screen name, type, and options

    Returns:
        JSON or Markdown formatted list of securities with field data

    Example:
        screen_name="Japan_ADR_Universe", screen_type="PRIVATE"
    """
    try:
        from bloomberg_mcp.tools import run_screen

        result = run_screen(
            screen_name=params.screen_name,
            screen_type=params.screen_type,
            group=params.group
        )

        if result.errors and not result.securities:
            return f"Screen error: {', '.join(result.errors)}"

        formatted = _format_screen_result(result, params.response_format, params.max_results)
        return _truncate_response(formatted)

    except Exception as e:
        return f"Error running screen: {str(e)}"


# ============================================================================
# Server Entry Point
# ============================================================================

def main():
    """Main entry point for the Bloomberg MCP server."""
    import sys

    # Check for transport argument
    transport = "stdio"
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8080"))

    for arg in sys.argv[1:]:
        if arg == "--http":
            transport = "streamable-http"
        elif arg == "--sse":
            transport = "sse"
        elif arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg.startswith("--host="):
            host = arg.split("=")[1]

    if transport == "stdio":
        mcp.run()
    else:
        # For HTTP/SSE transport, use uvicorn directly
        import uvicorn
        if transport == "sse":
            app = mcp.sse_app()
        else:
            app = mcp.streamable_http_app()
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )


if __name__ == "__main__":
    main()
