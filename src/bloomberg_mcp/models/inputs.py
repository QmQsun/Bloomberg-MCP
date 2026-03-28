"""Pydantic input models for all Bloomberg MCP tools."""

from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .enums import ResponseFormat, EconomicCalendarModeInput, EarningsModeInput


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
- "RVOL" \u2192 VOLUME, VOLUME_AVG_20D, TURNOVER + computed rvol
- "MOMENTUM" \u2192 CHG_PCT_1D, CHG_PCT_5D, CHG_PCT_1M, CHG_PCT_YTD
- "SENTIMENT" \u2192 NEWS_SENTIMENT, NEWS_SENTIMENT_DAILY_AVG
- "SECTOR" \u2192 GICS_SECTOR_NAME, GICS_INDUSTRY_GROUP_NAME, GICS_INDUSTRY_NAME
- "TECHNICAL" \u2192 RSI_14D, VOLATILITY_30D, VOLATILITY_90D, BETA_RAW_OVERRIDABLE
- "VALUATION" \u2192 PE_RATIO, PX_TO_BOOK_RATIO, CUR_MKT_CAP, DIVIDEND_YIELD
- "PRICE" \u2192 PX_LAST, PX_OPEN, PX_HIGH, PX_LOW, CHG_PCT_1D

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


class EstimatesDetailInput(BaseModel):
    """Input for fetching multi-period consensus estimates."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    securities: List[str] = Field(
        ...,
        description="List of security identifiers (e.g., ['AAPL US Equity'])",
        min_length=1,
        max_length=20
    )
    metrics: List[str] = Field(
        default=["EPS", "SALES", "EBITDA"],
        description="""Estimate metrics to fetch. Each generates BEST_{metric} fields.
Options: EPS, SALES, EBITDA, NET_INCOME, OPER_INC, FCF"""
    )
    periods: List[str] = Field(
        default=["1FY", "2FY", "1FQ", "2FQ"],
        description="""Fiscal periods to fetch. Uses BEST_FPERIOD_OVERRIDE.
- 1FY/2FY/3FY: Current/next/next+1 fiscal year
- 1FQ/2FQ/3FQ/4FQ: Current through 4th-next fiscal quarter"""
    )
    include_revisions: bool = Field(
        default=True,
        description="Include 4-week revision momentum (BEST_{metric}_4WK_CHG)"
    )
    include_surprise: bool = Field(
        default=True,
        description="Include last earnings surprise (BEST_{metric}_SURPRISE)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' or 'markdown'"
    )


class TechnicalAnalysisInput(BaseModel):
    """Input for Bloomberg Technical Analysis (//blp/tasvc)."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    security: str = Field(
        ...,
        description="Single security identifier (e.g., 'AAPL US Equity')",
        min_length=1
    )
    study: str = Field(
        ...,
        description="""Technical study to compute. Options:
- rsi: Relative Strength Index
- macd: Moving Average Convergence Divergence
- sma: Simple Moving Average
- ema: Exponential Moving Average
- bollinger: Bollinger Bands
- dmi: Directional Movement Index / ADX
- stochastic: Stochastic Oscillator"""
    )
    start_date: str = Field(
        ...,
        description="Start date: YYYYMMDD or YYYY-MM-DD"
    )
    end_date: str = Field(
        ...,
        description="End date: YYYYMMDD or YYYY-MM-DD"
    )
    period: Optional[int] = Field(
        default=None,
        description="Study period (e.g., 14 for RSI-14, 20 for SMA-20). Uses study default if omitted."
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' or 'markdown'"
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if len(v) == 8 and v.isdigit():
            return v
        if len(v) == 10 and v[4] in '-/':
            normalized = v.replace('-', '').replace('/', '')
            if len(normalized) == 8 and normalized.isdigit():
                return normalized
        raise ValueError(f"Date must be YYYYMMDD or YYYY-MM-DD format, got: {v}")

    @field_validator("study")
    @classmethod
    def validate_study(cls, v: str) -> str:
        valid = ["rsi", "macd", "sma", "ema", "bollinger", "dmi", "stochastic"]
        v_lower = v.lower()
        if v_lower not in valid:
            raise ValueError(f"study must be one of {valid}, got: {v}")
        return v_lower


class BulkDataInput(BaseModel):
    """Input for fetching Bloomberg bulk data (BDS).

    BDS returns tabular/array data (e.g., top holders, dividend history,
    supply chain) unlike BDP which returns single scalar values.
    """
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    security: str = Field(
        ...,
        description="Single security identifier (e.g., 'AAPL US Equity')",
        min_length=1
    )
    field: str = Field(
        ...,
        description="""BDS field name. Common fields:
- TOP_20_HOLDERS_PUBLIC_FILINGS: Top 20 shareholders
- DVD_HIST_ALL: Complete dividend history
- SUPPLY_CHAIN_SUPPLIERS: Supplier list with revenue exposure
- SUPPLY_CHAIN_CUSTOMERS: Customer list with revenue exposure
- SUPPLY_CHAIN_COMPETITORS: Competitor list
- INDX_MEMBERS: Index constituents
- ANALYST_RECOMMENDATIONS: Analyst ratings detail
- ERN_ANN_DT_AND_PER: Earnings announcement dates
- BOARD_OF_DIRECTORS: Board members
- EARN_ANN_DT_TIME_HIST_WITH_EPS: Historical earnings with actual EPS""",
        min_length=1
    )
    overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional field overrides as key-value pairs"
    )
    max_rows: int = Field(
        default=100,
        description="Maximum number of rows to return",
        ge=1,
        le=5000
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Output format: 'json' for structured data or 'markdown' for readable format"
    )


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
