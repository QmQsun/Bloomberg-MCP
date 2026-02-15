#!/usr/bin/env python3
"""
Bloomberg MCP Server - FastMCP wrapper for Bloomberg data access.

This server exposes Bloomberg data tools via MCP protocol, enabling
LLMs to fetch market data, reference data, and historical data.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

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
# FieldSet Expansion Helper
# ============================================================================

def _get_fieldset_map():
    """Lazy-load fieldset map to avoid circular imports."""
    from bloomberg_mcp.tools.dynamic_screening import FieldSets
    return {
        "RVOL": FieldSets.RVOL,
        "MOMENTUM": FieldSets.MOMENTUM,
        "MOMENTUM_EXTENDED": FieldSets.MOMENTUM_EXTENDED,
        "SENTIMENT": FieldSets.SENTIMENT,
        "SECTOR": FieldSets.SECTOR,
        "TECHNICAL": FieldSets.TECHNICAL,
        "TECHNICAL_EXTENDED": FieldSets.TECHNICAL_EXTENDED,
        "VALUATION": FieldSets.VALUATION,
        "PRICE": FieldSets.PRICE,
        "PRICE_EXTENDED": FieldSets.PRICE_EXTENDED,
        "ADR": FieldSets.ADR,
        "MORNING_NOTE": FieldSets.MORNING_NOTE,
        "SCREENING_FULL": FieldSets.SCREENING_FULL,
        "VOLUME_EXTENDED": FieldSets.VOLUME_EXTENDED,
        "LIQUIDITY": FieldSets.LIQUIDITY,
        "VOLATILITY": FieldSets.VOLATILITY,
        "ANALYST": FieldSets.ANALYST,
        "CLASSIFICATION": FieldSets.CLASSIFICATION,
        "DESCRIPTIVE": FieldSets.DESCRIPTIVE,
    }


def _expand_fields(fields: List[str]) -> List[str]:
    """Expand FieldSet shortcuts to raw Bloomberg fields.

    Accepts mix of FieldSet names (e.g., 'VALUATION', 'MOMENTUM') and
    raw Bloomberg fields (e.g., 'PX_LAST', 'PE_RATIO').

    Returns deduplicated list preserving order.
    """
    fieldset_map = _get_fieldset_map()
    expanded = []
    seen = set()

    for field_spec in fields:
        field_upper = field_spec.upper()
        if field_upper in fieldset_map:
            # Expand FieldSet to its component fields
            for f in fieldset_map[field_upper].fields:
                if f not in seen:
                    seen.add(f)
                    expanded.append(f)
        else:
            # Raw Bloomberg field - preserve original case
            if field_spec not in seen:
                seen.add(field_spec)
                expanded.append(field_spec)

    return expanded


def _normalize_date(date_str: str) -> str:
    """Normalize date string to YYYYMMDD format.

    Accepts:
    - YYYYMMDD (passthrough)
    - YYYY-MM-DD (ISO format)
    - YYYY/MM/DD

    Returns YYYYMMDD format for Bloomberg API.
    """
    # Already in correct format
    if len(date_str) == 8 and date_str.isdigit():
        return date_str

    # Try ISO format YYYY-MM-DD
    if len(date_str) == 10 and date_str[4] in '-/':
        return date_str.replace('-', '').replace('/', '')

    # Fallback - return as-is and let Bloomberg validate
    return date_str


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
        description="""List of Bloomberg fields or FieldSet shortcuts.

Raw fields: 'PX_LAST', 'PE_RATIO', 'VOLUME', etc.

FieldSet shortcuts (expand to multiple fields):
- PRICE: PX_LAST, PX_OPEN, PX_HIGH, PX_LOW, CHG_PCT_1D
- VALUATION: PE_RATIO, PX_TO_BOOK_RATIO, CUR_MKT_CAP, DIVIDEND_YIELD
- MOMENTUM: CHG_PCT_1D, CHG_PCT_5D, CHG_PCT_1M, CHG_PCT_YTD
- RVOL: VOLUME, VOLUME_AVG_20D, TURNOVER
- TECHNICAL: RSI_14D, VOLATILITY_30D, VOLATILITY_90D, BETA_RAW_OVERRIDABLE
- SECTOR: GICS_SECTOR_NAME, GICS_INDUSTRY_GROUP_NAME, GICS_INDUSTRY_NAME
- SENTIMENT: NEWS_SENTIMENT, NEWS_SENTIMENT_DAILY_AVG
- ANALYST: EQY_REC_CONS, BEST_TARGET_PRICE, TOT_ANALYST_REC

Example: ['VALUATION', 'PX_LAST'] expands to PE_RATIO, PX_TO_BOOK_RATIO, etc.""",
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
        description="List of Bloomberg fields or FieldSet shortcuts (same as reference data)",
        min_length=1,
        max_length=25
    )
    start_date: str = Field(
        ...,
        description="Start date: YYYYMMDD (e.g., '20240101') or YYYY-MM-DD (e.g., '2024-01-01')"
    )
    end_date: str = Field(
        ...,
        description="End date: YYYYMMDD (e.g., '20241231') or YYYY-MM-DD (e.g., '2024-12-31')"
    )
    periodicity: str = Field(
        default="DAILY",
        description="Data periodicity: DAILY, WEEKLY, MONTHLY, QUARTERLY, or YEARLY"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format"
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate and normalize date format."""
        # Accept YYYYMMDD
        if len(v) == 8 and v.isdigit():
            return v
        # Accept YYYY-MM-DD or YYYY/MM/DD
        if len(v) == 10 and v[4] in '-/':
            normalized = v.replace('-', '').replace('/', '')
            if len(normalized) == 8 and normalized.isdigit():
                return normalized
        raise ValueError(f"Date must be YYYYMMDD or YYYY-MM-DD format, got: {v}")

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


class GetUniverseInput(BaseModel):
    """Input for getting a list of securities from an index or saved screen."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source: str = Field(
        ...,
        description="""
Universe source. Use one of these formats:

INDEX CONSTITUENTS (use "index:" prefix):
- "index:NKY Index" - Nikkei 225 (~225 securities)
- "index:TPX Index" - TOPIX (~2000 securities)
- "index:SPX Index" - S&P 500 (~500 securities)
- "index:NDX Index" - Nasdaq 100 (~100 securities)
- "index:SOX Index" - Philadelphia Semiconductor Index (~30 securities)
- "index:RTY Index" - Russell 2000 (~2000 securities)

SAVED BLOOMBERG SCREENS (use "screen:" prefix):
- "screen:Japan_Liquid_ADRs" - Pre-saved EQS screen
- "screen:YourScreenName" - Any saved screen from EQS <GO>
        """,
        min_length=1,
    )
    include_fields: Optional[List[str]] = Field(
        default=None,
        description="""Optional fields to fetch for each security. Supports FieldSet shortcuts.

If provided, returns securities with field data instead of just ticker list.
Examples: ['PX_LAST', 'CHG_PCT_1D'] or ['PRICE', 'MOMENTUM'] for FieldSets.""",
        max_length=30
    )
    max_results: Optional[int] = Field(
        default=None,
        description="Maximum number of securities to return (None for all)",
        ge=1,
        le=2000
    )


class FilterSpec(BaseModel):
    """A single filter condition for screening."""
    field: str = Field(
        ...,
        description="Field to filter on (e.g., 'rvol', 'CHG_PCT_1D', 'GICS_SECTOR_NAME')"
    )
    op: str = Field(
        ...,
        description="Operator: 'gt', 'gte', 'lt', 'lte', 'eq', 'neq', 'between', 'in'"
    )
    value: Any = Field(
        ...,
        description="Value to compare (number, string, or list for 'between'/'in')"
    )


class DynamicScreenInput(BaseModel):
    """Input for running a dynamic equity screen with custom filters."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(
        default="Dynamic Screen",
        description="Screen name for identification in results"
    )
    universe: Any = Field(
        ...,
        description="""
Universe to screen. Either:

1. STRING with prefix:
   - "index:NKY Index" - Nikkei 225 constituents
   - "index:SPX Index" - S&P 500 constituents
   - "index:TPX Index" - TOPIX constituents
   - "index:SOX Index" - Philadelphia Semiconductor Index
   - "screen:Japan_Liquid_ADRs" - Saved Bloomberg screen

2. LIST of securities:
   - ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity"]
        """
    )
    fields: List[str] = Field(
        ...,
        description="""
Fields to fetch. Can mix FieldSet names and raw Bloomberg fields.

FIELDSET NAMES (expand to multiple fields):
- "RVOL" → VOLUME, VOLUME_AVG_20D, TURNOVER + computed rvol
- "MOMENTUM" → CHG_PCT_1D, CHG_PCT_5D, CHG_PCT_1M, CHG_PCT_YTD
- "SENTIMENT" → NEWS_SENTIMENT, NEWS_SENTIMENT_DAILY_AVG
- "SECTOR" → GICS_SECTOR_NAME, GICS_INDUSTRY_GROUP_NAME, GICS_INDUSTRY_NAME
- "TECHNICAL" → RSI_14D, VOLATILITY_30D, VOLATILITY_90D, BETA_RAW_OVERRIDABLE
- "VALUATION" → PE_RATIO, PX_TO_BOOK_RATIO, CUR_MKT_CAP, DIVIDEND_YIELD
- "PRICE" → PX_LAST, PX_OPEN, PX_HIGH, PX_LOW, CHG_PCT_1D

RAW BLOOMBERG FIELDS:
- "PX_LAST", "CHG_PCT_1D", "VOLUME", "NEWS_SENTIMENT", "PE_RATIO", etc.

EXAMPLE: ["RVOL", "MOMENTUM", "GICS_SECTOR_NAME"]
        """,
        min_length=1
    )
    filters: Optional[List[FilterSpec]] = Field(
        default=None,
        description="""
Filters to apply. Each filter has: field, op, value.

OPERATORS:
- "gt": greater than (e.g., rvol > 2.0)
- "gte": greater than or equal
- "lt": less than
- "lte": less than or equal
- "eq": equals (strings or numbers)
- "neq": not equals
- "between": range [min, max] inclusive
- "in": value in list

FILTER EXAMPLES:
- {"field": "rvol", "op": "gt", "value": 1.5}
- {"field": "CHG_PCT_1D", "op": "gt", "value": 2.0}
- {"field": "GICS_SECTOR_NAME", "op": "eq", "value": "Information Technology"}
- {"field": "CHG_PCT_1D", "op": "between", "value": [-5, 5]}
- {"field": "GICS_SECTOR_NAME", "op": "in", "value": ["Technology", "Financials"]}

COMPUTED FIELDS for filtering:
- "rvol": VOLUME / VOLUME_AVG_20D (requires RVOL fieldset)

TIP: For small universes (<50), prefer ranking over strict filtering.
        """
    )
    rank_by: Optional[str] = Field(
        default=None,
        description="Field to rank by (e.g., 'rvol', 'CHG_PCT_1D', 'NEWS_SENTIMENT')"
    )
    rank_descending: bool = Field(
        default=True,
        description="True = highest values first, False = lowest first"
    )
    top_n: int = Field(
        default=20,
        description="Number of results to return after ranking",
        ge=1,
        le=500
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' for structured data or 'markdown' for readable"
    )


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
        securities=["AAPL US Equity"], fields=["VALUATION", "MOMENTUM"]  # FieldSet shortcuts
    """
    try:
        from bloomberg_mcp.tools import get_reference_data

        # Expand FieldSet shortcuts to raw Bloomberg fields
        expanded_fields = _expand_fields(params.fields)

        data = get_reference_data(
            securities=params.securities,
            fields=expanded_fields,
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
        start_date="2024-01-01", end_date="2024-12-31"  # ISO format also works
    """
    try:
        from bloomberg_mcp.tools import get_historical_data

        # Expand FieldSet shortcuts to raw Bloomberg fields
        expanded_fields = _expand_fields(params.fields)

        data = get_historical_data(
            securities=params.securities,
            fields=expanded_fields,
            start_date=params.start_date,  # Already normalized by validator
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


@mcp.tool(
    name="bloomberg_get_universe",
    annotations={
        "title": "Get Universe Securities",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_get_universe(params: GetUniverseInput) -> str:
    """
    Get a list of securities from an index or saved Bloomberg screen.

    Use this tool to discover what securities are in a universe BEFORE
    running a dynamic screen. This helps you understand the size and
    composition of different universes.

    UNIVERSE SOURCES:

    INDEX CONSTITUENTS (use "index:" prefix):
    - "index:NKY Index" - Nikkei 225 (~225 Japan large-caps)
    - "index:TPX Index" - TOPIX (~2000 Japan equities)
    - "index:SPX Index" - S&P 500 (~500 US large-caps)
    - "index:NDX Index" - Nasdaq 100 (~100 US tech-heavy)
    - "index:SOX Index" - Philadelphia Semiconductor (~30 semis)
    - "index:RTY Index" - Russell 2000 (~2000 US small-caps)

    SAVED BLOOMBERG SCREENS (use "screen:" prefix):
    - "screen:Japan_Liquid_ADRs" - Pre-saved screen of liquid Japan ADRs
    - "screen:YourScreenName" - Any screen saved in EQS <GO>

    Args:
        params: GetUniverseInput with source, optional include_fields, and max_results

    Returns:
        JSON list of security identifiers (or with field data if include_fields specified)

    Example:
        source="index:SOX Index" → Returns ~30 semiconductor stocks
        source="index:SOX Index", include_fields=["PX_LAST", "CHG_PCT_1D"] → With price data
        source="index:SOX Index", include_fields=["PRICE", "MOMENTUM"] → FieldSet shortcuts
    """
    try:
        from bloomberg_mcp.tools.dynamic_screening.custom_eqs import (
            get_universe_from_screen,
            get_index_constituents,
        )

        source = params.source.strip()
        securities = []

        if source.lower().startswith("index:"):
            # Extract index ticker (e.g., "NKY Index" from "index:NKY Index")
            index_ticker = source[6:].strip()
            securities = get_index_constituents(index_ticker)
        elif source.lower().startswith("screen:"):
            # Extract screen name
            screen_name = source[7:].strip()
            securities = get_universe_from_screen(screen_name)
        else:
            return f"Error: Invalid source format. Use 'index:TICKER' or 'screen:NAME'. Got: {source}"

        # Apply max_results limit if specified
        if params.max_results and len(securities) > params.max_results:
            securities = securities[:params.max_results]
            truncated = True
        else:
            truncated = False

        # If include_fields is specified, fetch reference data
        field_data = None
        if params.include_fields:
            from bloomberg_mcp.tools import get_reference_data

            expanded_fields = _expand_fields(params.include_fields)
            ref_data = get_reference_data(
                securities=securities,
                fields=expanded_fields
            )
            field_data = [
                {"security": d.security, **d.fields}
                for d in ref_data
            ]

        result = {
            "source": source,
            "count": len(securities),
            "truncated": truncated,
            "securities": securities,
        }

        if field_data:
            result["fields_requested"] = _expand_fields(params.include_fields)
            result["data"] = field_data

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return f"Error getting universe: {str(e)}"


@mcp.tool(
    name="bloomberg_dynamic_screen",
    annotations={
        "title": "Run Dynamic Screen",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def bloomberg_dynamic_screen(params: DynamicScreenInput) -> str:
    """
    Run a dynamic equity screen with custom universe, fields, filters, and ranking.

    This is the primary tool for LLM-driven market analysis. You can:
    1. Choose ANY universe (index, saved screen, or explicit list)
    2. Fetch any combination of Bloomberg fields
    3. Apply filters to narrow results
    4. Rank and select top/bottom N securities

    UNIVERSE OPTIONS:

    Use a string with prefix:
    - "index:SPX Index" - S&P 500 constituents (~500)
    - "index:NKY Index" - Nikkei 225 (~225)
    - "index:SOX Index" - Semiconductor Index (~30)
    - "screen:Japan_Liquid_ADRs" - Saved Bloomberg screen

    Or provide an explicit list:
    - ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity"]

    FIELDSET SHORTCUTS (expand to multiple fields):

    - "RVOL" → VOLUME, VOLUME_AVG_20D, TURNOVER (+ computed rvol)
    - "MOMENTUM" → CHG_PCT_1D, CHG_PCT_5D, CHG_PCT_1M, CHG_PCT_YTD
    - "MOMENTUM_EXTENDED" → adds CHG_PCT_3M, CHG_PCT_6M, CHG_PCT_1YR
    - "SENTIMENT" → NEWS_SENTIMENT, NEWS_SENTIMENT_DAILY_AVG
    - "SECTOR" → GICS_SECTOR_NAME, GICS_INDUSTRY_GROUP_NAME, GICS_INDUSTRY_NAME
    - "TECHNICAL" → RSI_14D, VOLATILITY_30D, VOLATILITY_90D, BETA_RAW_OVERRIDABLE
    - "VALUATION" → PE_RATIO, PX_TO_BOOK_RATIO, CUR_MKT_CAP, DIVIDEND_YIELD
    - "PRICE" → PX_LAST, PX_OPEN, PX_HIGH, PX_LOW, CHG_PCT_1D
    - "ADR" → PX_LAST, CHG_PCT_1D, VOLUME, VOLUME_AVG_20D, NEWS_SENTIMENT, GICS_SECTOR_NAME
    - "MORNING_NOTE" → Comprehensive set for morning analysis

    You can also use raw Bloomberg fields: "PX_LAST", "PE_RATIO", etc.

    FILTER OPERATORS:

    - "gt": greater than (e.g., rvol > 2.0)
    - "gte": greater than or equal
    - "lt": less than
    - "lte": less than or equal
    - "eq": equals (for strings like sector names)
    - "neq": not equals
    - "between": range [min, max] inclusive
    - "in": value in list (for multiple sectors)

    FILTER EXAMPLES:

    {"field": "rvol", "op": "gt", "value": 1.5}
    {"field": "CHG_PCT_1D", "op": "gt", "value": 2.0}
    {"field": "GICS_SECTOR_NAME", "op": "eq", "value": "Information Technology"}
    {"field": "CHG_PCT_1D", "op": "between", "value": [-5, 5]}
    {"field": "GICS_SECTOR_NAME", "op": "in", "value": ["Financials", "Industrials"]}

    RANKING:

    Use rank_by to sort results by any field (rvol, CHG_PCT_1D, NEWS_SENTIMENT, etc.)
    Combined with top_n to get the top N results.

    SCREENING TIPS:

    1. For small universes (<50), prefer ranking over strict filters
    2. Use broader filters first, then narrow down
    3. Combine FieldSets: ["RVOL", "MOMENTUM", "SECTOR"]
    4. The "rvol" field is computed as VOLUME/VOLUME_AVG_20D

    Args:
        params: DynamicScreenInput with universe, fields, filters, ranking

    Returns:
        JSON with screen results including securities, fields, and metadata

    Example:
        name="High RVOL Tech Stocks"
        universe="index:SOX Index"
        fields=["RVOL", "MOMENTUM", "SECTOR"]
        filters=[{"field": "rvol", "op": "gt", "value": 1.5}]
        rank_by="rvol"
        top_n=10
    """
    try:
        from bloomberg_mcp.tools.dynamic_screening import (
            DynamicScreen,
            FieldSets,
        )
        from bloomberg_mcp.tools.dynamic_screening.filters import (
            ComparisonFilter,
            BetweenFilter,
            InFilter,
        )

        # Build the screen
        screen = DynamicScreen(params.name)

        # Configure universe
        universe = params.universe
        if isinstance(universe, str):
            universe = universe.strip()
            if universe.lower().startswith("index:"):
                index_ticker = universe[6:].strip()
                screen.universe_from_index(index_ticker)
            elif universe.lower().startswith("screen:"):
                screen_name = universe[7:].strip()
                screen.universe_from_screen(screen_name)
            else:
                return f"Error: Invalid universe format. Use 'index:TICKER', 'screen:NAME', or a list of securities. Got: {universe}"
        elif isinstance(universe, list):
            screen.universe_from_list(universe)
        else:
            return f"Error: Universe must be a string with prefix or a list of securities. Got: {type(universe)}"

        # Resolve and add fields
        fieldset_map = {
            "RVOL": FieldSets.RVOL,
            "MOMENTUM": FieldSets.MOMENTUM,
            "MOMENTUM_EXTENDED": FieldSets.MOMENTUM_EXTENDED,
            "SENTIMENT": FieldSets.SENTIMENT,
            "SECTOR": FieldSets.SECTOR,
            "TECHNICAL": FieldSets.TECHNICAL,
            "TECHNICAL_EXTENDED": FieldSets.TECHNICAL_EXTENDED,
            "VALUATION": FieldSets.VALUATION,
            "PRICE": FieldSets.PRICE,
            "PRICE_EXTENDED": FieldSets.PRICE_EXTENDED,
            "ADR": FieldSets.ADR,
            "MORNING_NOTE": FieldSets.MORNING_NOTE,
            "SCREENING_FULL": FieldSets.SCREENING_FULL,
            "VOLUME_EXTENDED": FieldSets.VOLUME_EXTENDED,
            "LIQUIDITY": FieldSets.LIQUIDITY,
            "VOLATILITY": FieldSets.VOLATILITY,
            "ANALYST": FieldSets.ANALYST,
            "CLASSIFICATION": FieldSets.CLASSIFICATION,
            "DESCRIPTIVE": FieldSets.DESCRIPTIVE,
        }

        for field_spec in params.fields:
            field_upper = field_spec.upper()
            if field_upper in fieldset_map:
                screen.with_fields(fieldset_map[field_upper])
            else:
                # Raw Bloomberg field
                screen.with_fields([field_spec])

        # Apply filters
        if params.filters:
            for f in params.filters:
                op = f.op.lower()
                field = f.field
                value = f.value

                if op == "gt":
                    screen.filter(ComparisonFilter(field, "gt", value))
                elif op == "gte":
                    screen.filter(ComparisonFilter(field, "gte", value))
                elif op == "lt":
                    screen.filter(ComparisonFilter(field, "lt", value))
                elif op == "lte":
                    screen.filter(ComparisonFilter(field, "lte", value))
                elif op == "eq":
                    screen.filter(ComparisonFilter(field, "eq", value))
                elif op in ("neq", "ne"):
                    screen.filter(ComparisonFilter(field, "ne", value))
                elif op == "between":
                    if isinstance(value, list) and len(value) == 2:
                        screen.filter(BetweenFilter(field, value[0], value[1]))
                    else:
                        return f"Error: 'between' filter requires [min, max] list. Got: {value}"
                elif op == "in":
                    if isinstance(value, list):
                        screen.filter(InFilter(field, value))
                    else:
                        return f"Error: 'in' filter requires a list of values. Got: {value}"
                else:
                    return f"Error: Unknown filter operator '{op}'. Valid: gt, gte, lt, lte, eq, neq, between, in"

        # Apply ranking
        if params.rank_by:
            screen.rank_by(params.rank_by, descending=params.rank_descending)
            screen.top(params.top_n)

        # Execute screen
        result = screen.run()

        # Format output
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [
                f"## Screen: {result.name}",
                f"**Universe**: {result.universe_source} ({result.universe_size} securities)",
                f"**Passed filters**: {result.filtered_count}",
                f"**Execution time**: {result.execution_time_ms:.0f}ms",
                ""
            ]

            if result.errors:
                lines.append(f"**Errors**: {', '.join(result.errors)}")
                lines.append("")

            if result.filters_applied:
                lines.append(f"**Filters**: {', '.join(result.filters_applied)}")
                lines.append("")

            if result.records:
                # Show key fields in table
                lines.append("| Rank | Security | Price | Chg% | RVOL | Sector |")
                lines.append("|------|----------|-------|------|------|--------|")

                for rec in result.records[:50]:
                    rank = rec.rank or "-"
                    price = f"${rec.price:.2f}" if rec.price else "-"
                    chg = f"{rec.change_pct:+.2f}%" if rec.change_pct else "-"
                    rvol = f"{rec.rvol:.2f}x" if rec.rvol else "-"
                    sector = rec.sector[:15] if rec.sector else "-"
                    lines.append(f"| {rank} | {rec.ticker} | {price} | {chg} | {rvol} | {sector} |")

                if len(result.records) > 50:
                    lines.append(f"\n*... and {len(result.records) - 50} more*")

            return "\n".join(lines)
        else:
            # JSON format
            output = result.to_dict()
            return json.dumps(output, indent=2, default=str)

    except Exception as e:
        logger.exception("Error running dynamic screen")
        return f"Error running dynamic screen: {str(e)}"


# ============================================================================
# Economic Calendar Tool
# ============================================================================

class EconomicCalendarModeInput(str, Enum):
    """Calendar query mode."""
    WEEK_AHEAD = "week_ahead"
    TODAY = "today"
    RECENT = "recent"
    CENTRAL_BANK = "central_bank"


class EconomicCalendarToolInput(BaseModel):
    """Input for economic calendar query."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    mode: EconomicCalendarModeInput = Field(
        default=EconomicCalendarModeInput.WEEK_AHEAD,
        description="Query mode: week_ahead (7 days), today, recent (24h releases), central_bank (30 days)"
    )
    regions: List[str] = Field(
        default=["US", "Japan"],
        description="Regions to include: US, Japan, Europe, China"
    )
    categories: Optional[List[str]] = Field(
        default=None,
        description="Event categories to filter. None = all. Options: central_bank, inflation, employment, growth, trade, manufacturing, consumer"
    )
    importance: str = Field(
        default="high",
        description="Minimum importance level: high, medium, low, all"
    )
    days_ahead: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days ahead to look (for week_ahead mode)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: json or markdown"
    )


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

        # Convert tool input to internal model
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
            # Use the morning note formatter for markdown
            return format_calendar_for_morning_note(result)
        else:
            # JSON format
            return json.dumps(result.to_dict(), indent=2)

    except Exception as e:
        logger.exception("Error fetching economic calendar")
        return f"Error fetching economic calendar: {str(e)}"


# ============================================================================
# Earnings Calendar Tool
# ============================================================================

class EarningsModeInput(str, Enum):
    """Earnings calendar query mode."""
    OVERNIGHT = "overnight"
    TODAY = "today"
    WEEK_AHEAD = "week_ahead"


class EarningsCalendarToolInput(BaseModel):
    """Input for earnings calendar query."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    mode: EarningsModeInput = Field(
        default=EarningsModeInput.WEEK_AHEAD,
        description="Query mode: overnight (last 24h), today, week_ahead (7 days)"
    )
    universe: Any = Field(
        default="MORNING_NOTE",
        description="""
Universe to query. Either:
- Named universe: "MORNING_NOTE", "SEMI_LEADERS", "MEGA_CAP_TECH", "JAPAN_ADRS", "US_FINANCIALS", "CONSUMER", "INDUSTRIALS"
- Explicit list: ["AAPL US Equity", "NVDA US Equity", ...]
        """
    )
    days_ahead: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days ahead to look for earnings"
    )
    include_estimates: bool = Field(
        default=True,
        description="Include EPS/sales estimates and analyst data"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: json or markdown"
    )


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
    2. Semiconductor earnings → read-through to 8035, 6857, 6920
    3. Financial earnings → read-through to 8306, 8411

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

        # Convert tool input to internal model
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
            # Use morning note formatter
            return format_earnings_for_morning_note(result)
        else:
            # JSON format
            return json.dumps(result.to_dict(), indent=2)

    except Exception as e:
        logger.exception("Error fetching earnings calendar")
        return f"Error fetching earnings calendar: {str(e)}"


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
            base_app = mcp.sse_app()
        else:
            base_app = mcp.streamable_http_app()

        # Wrap app to allow all hosts (needed for Tailscale/remote access)
        # This middleware rewrites the Host header to localhost before the request
        # reaches FastMCP's TrustedHostMiddleware
        class AllowAllHostsMiddleware:
            def __init__(self, app):
                self.app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] == "http":
                    # Rewrite headers to use localhost
                    headers = [(k, v) for k, v in scope["headers"] if k != b"host"]
                    headers.append((b"host", b"localhost:8080"))
                    scope = dict(scope, headers=headers)
                await self.app(scope, receive, send)

        app = AllowAllHostsMiddleware(base_app)

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )


if __name__ == "__main__":
    main()
