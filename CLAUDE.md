# Bloomberg MCP — Project Guide

Data access layer for Bloomberg Terminal via blpapi + MCP (Model Context Protocol).
This server exposes Bloomberg data tools to AI assistants via natural language.

**Current state:** 12 tools, modular structure (PHASE 0 complete).
**Target state:** ~22 tools, full Bloomberg API surface coverage.

---

## Architecture Overview

```
src/bloomberg_mcp/
├── server.py                # FastMCP init + entry point (~89 lines)
├── models/
│   ├── __init__.py          # Re-exports all models
│   ├── enums.py             # ResponseFormat, EconomicCalendarModeInput, EarningsModeInput
│   └── inputs.py            # ALL Pydantic BaseModel input classes
├── handlers/
│   ├── __init__.py          # Imports all handler modules to trigger registration
│   ├── reference.py         # bloomberg_get_reference_data handler
│   ├── historical.py        # bloomberg_get_historical_data handler
│   ├── intraday.py          # bloomberg_get_intraday_bars + ticks handlers
│   ├── search.py            # search_securities + search_fields + field_info
│   ├── screening.py         # run_screen + get_universe + dynamic_screen
│   └── calendars.py         # economic_calendar + earnings_calendar
├── formatters.py            # _format_security_data, _format_historical_data, etc.
├── utils.py                 # _expand_fields, _normalize_date, _truncate_response, _get_session
├── core/
│   ├── session.py           # BloombergSession singleton (376 lines, solid)
│   ├── requests.py          # blpapi request builders using fromPy() (507 lines, solid)
│   └── responses.py         # Response parsers using toPy() (416 lines, needs BDS/TA/BQL)
└── tools/
    ├── reference.py         # get_reference_data() — thin wrapper
    ├── historical.py        # get_historical_data() — thin wrapper
    ├── intraday.py          # get_intraday_bars/ticks() — thin wrapper
    ├── search.py            # search_securities/fields/field_info (204 lines)
    ├── screening.py         # run_screen() — BEQS wrapper
    ├── dynamic_screening/   # DSL system: FieldSet + Filter + DynamicScreen (2,567 lines, mature)
    ├── morning_note/        # Market data collection system (3,648 lines, Japan-focused)
    ├── economic_calendar/   # Macro event calendar (874 lines)
    └── earnings_calendar/   # Earnings announcements (640 lines)
```

Connection: localhost:8194 (Bloomberg Desktop API). No authentication needed.

---

## Quick Reference — Function Signatures

```python
# Primary imports
from bloomberg_mcp.tools import (
    get_reference_data,      # BDP — current field values
    get_historical_data,     # BDH — time series
    get_intraday_bars,       # Intraday OHLCV bars
    get_intraday_ticks,      # Raw ticks
    search_securities,       # Find securities (//blp/instruments)
    search_fields,           # Discover fields (//blp/apiflds)
    get_field_info,          # Field metadata (//blp/apiflds)
)

# Data types
from bloomberg_mcp import (
    SecurityData,            # Reference data result
    HistoricalData,          # Historical data result
    IntradayBar,             # Single bar
    IntradayBarData,         # Bars collection
    ScreenResult,            # BEQS screen result
)
```

### Reference Data (BDP)
```python
def get_reference_data(
    securities: List[str],           # ["AAPL US Equity", "700 HK Equity"]
    fields: List[str],               # ["PX_LAST", "PE_RATIO"]
    overrides: Optional[Dict[str, Any]] = None,
) -> List[SecurityData]:
```

### Historical Data (BDH)
```python
def get_historical_data(
    securities: List[str],
    fields: List[str],
    start_date: str,                 # "YYYYMMDD" format
    end_date: str,
    periodicity: str = "DAILY",      # DAILY|WEEKLY|MONTHLY|QUARTERLY|YEARLY
) -> List[HistoricalData]:
```

### Data Types
```python
@dataclass
class SecurityData:
    security: str
    fields: Dict[str, Any]           # {"PX_LAST": 150.0, "PE_RATIO": 25.0}
    errors: List[str]

@dataclass
class HistoricalData:
    security: str
    data: List[Dict[str, Any]]       # [{"date": datetime, "PX_LAST": 150.0}, ...]
    errors: List[str]
```

---

## PHASE 0: Refactor server.py — COMPLETE

server.py split from 1,798 lines to 89 lines. All 12 tools preserved.
Duplicated fieldset_map consolidated to `utils.py` as single source of truth.

- [x] server.py < 200 lines (89 lines)
- [x] All 12 tools still work (same names, same params, same output)
- [x] `pytest tests/` passes (16 passed, 51 skipped, 0 failed)
- [x] No import errors

---

## PHASE 1: Add BDS Tool + Caching + New FieldSets

### Tool: bloomberg_get_bulk_data (BDS)

BDS is NOT a separate request type — it uses the same `ReferenceDataRequest`.
The difference is in the RESPONSE: bulk fields return arrays instead of scalars.

Detection: `element.isArray()` returns True for bulk fields.
The existing `parse_reference_data_response()` already handles this via `field.toPy()`,
but the response is not optimized for AI consumption.

```python
# New tool in handlers/bulk.py
@mcp.tool(name="bloomberg_get_bulk_data")
async def bloomberg_get_bulk_data(params: BulkDataInput) -> str:
    """
    Get Bloomberg bulk data (BDS) — returns tabular/array data.
    
    Unlike reference data (BDP) which returns single values,
    bulk data returns lists/tables of related information.
    
    Common BDS fields:
    - TOP_20_HOLDERS_PUBLIC_FILINGS — Top 20 shareholders
    - DVD_HIST_ALL — Complete dividend history
    - SUPPLY_CHAIN_SUPPLIERS — Supplier list with revenue exposure
    - SUPPLY_CHAIN_CUSTOMERS — Customer list with revenue exposure
    - SUPPLY_CHAIN_COMPETITORS — Competitor list
    - INDX_MEMBERS — Index constituents
    - ANALYST_RECOMMENDATIONS — Analyst ratings detail
    - ERN_ANN_DT_AND_PER — Earnings announcement dates
    - BOARD_OF_DIRECTORS — Board members
    - EARN_ANN_DT_TIME_HIST_WITH_EPS — Historical earnings with actual EPS
    """
```

Input model:
```python
class BulkDataInput(BaseModel):
    security: str              # Single security (BDS convention)
    field: str                 # BDS field name
    overrides: Optional[Dict[str, Any]] = None
    max_rows: int = 100        # Limit returned rows
    response_format: ResponseFormat = ResponseFormat.JSON
```

Implementation: Use existing `get_reference_data()` internally, but:
1. Detect bulk fields in response (isArray check or just rely on toPy())
2. Format as clean table (row count, column names, truncation metadata)
3. Add `total_rows` and `truncated` to response

### Cache Layer (core/cache.py)

```python
class BloombergCache:
    """TTL-based in-memory cache keyed on (securities, fields, overrides)."""
    
    # TTL by data type:
    REFERENCE_STATIC_TTL = 86400    # 24h (company name, sector, BICS)
    FINANCIAL_STMT_TTL = 604800     # 7 days (quarterly)
    ESTIMATES_TTL = 14400           # 4h (updates intraday)
    PRICE_TTL = 30                  # 30 sec (near real-time)
    HISTORICAL_TTL = 43200          # 12h (EOD data doesn't change)
    BULK_DATA_TTL = 86400           # 24h (holders, supply chain)
```

### New FieldSets (in tools/dynamic_screening/models.py)

Add these GENERIC FieldSets (no company-specific naming):

```python
# Consensus estimates
ESTIMATES_CONSENSUS = FieldSet("estimates_consensus", [
    "BEST_EPS", "BEST_EPS_MEDIAN", "BEST_EPS_4WK_CHG",
    "BEST_SALES", "BEST_SALES_4WK_CHG", "BEST_EBITDA",
    "EQY_REC_CONS", "BEST_TARGET_PRICE", "BEST_EPS_SURPRISE",
    "BEST_EST_LONG_TERM_GROWTH",
])

# Profitability
PROFITABILITY = FieldSet("profitability", [
    "GROSS_MARGIN", "OPER_MARGIN", "PROF_MARGIN",
    "RETURN_ON_EQUITY", "RETURN_ON_ASSET", "RETURN_ON_INV_CAPITAL",
    "EBITDA_MARGIN",
])

# Cash flow quality
CASH_FLOW = FieldSet("cash_flow", [
    "FREE_CASH_FLOW_YIELD", "CF_FREE_CASH_FLOW",
    "CASH_FLOW_FROM_OPERATIONS", "NET_INCOME",
    "IS_COMP_SALES", "EBITDA",
])

# Balance sheet / leverage
BALANCE_SHEET = FieldSet("balance_sheet", [
    "TOT_DEBT_TO_TOT_EQY", "INTEREST_COVERAGE_RATIO",
    "CUR_RATIO", "QUICK_RATIO",
    "TOT_DEBT_TO_EBITDA", "NET_DEBT",
])

# Ownership
OWNERSHIP = FieldSet("ownership", [
    "PCT_HELD_BY_INSIDERS", "PCT_HELD_BY_INSTITUTIONS",
    "NUM_OF_INSTITUTIONAL_HOLDERS",
    "SHORT_INT_RATIO", "PUT_CALL_OPEN_INTEREST_RATIO",
])

# ESG / Governance
GOVERNANCE = FieldSet("governance", [
    "ESG_DISCLOSURE_SCORE", "ENVIRON_DISCLOSURE_SCORE",
    "SOCIAL_DISCLOSURE_SCORE", "GOVNCE_DISCLOSURE_SCORE",
])

# Risk metrics
RISK = FieldSet("risk", [
    "BETA_RAW_OVERRIDABLE", "VOLATILITY_10D", "VOLATILITY_30D",
    "VOLATILITY_90D", "VOLATILITY_260D",
    "CUR_MKT_CAP",
])

# Comprehensive valuation
VALUATION_EXTENDED = FieldSet("valuation_extended", [
    "PE_RATIO", "BEST_PE_RATIO", "PX_TO_BOOK_RATIO",
    "PX_TO_SALES_RATIO", "EV_TO_T12M_EBITDA",
    "PX_TO_FREE_CASH_FLOW", "DVD_PRCNT_YLD",
    "ENTERPRISE_VALUE", "CUR_MKT_CAP",
])

# Earnings surprise
EARNINGS_SURPRISE = FieldSet("earnings_surprise", [
    "BEST_EPS", "IS_EPS", "BEST_EPS_SURPRISE",
    "BEST_SALES", "SALES_REV_TURN", "BEST_SALES_SURPRISE",
])

# Growth
GROWTH = FieldSet("growth", [
    "SALES_GROWTH", "EPS_GROWTH", "EBITDA_GROWTH",
    "BEST_EST_LONG_TERM_GROWTH",
])
```

---

## PHASE 2: Estimates Detail + Technical Analysis

### Tool: bloomberg_get_estimates_detail

Multi-period consensus data. Internally makes multiple BDP calls with overrides.

```python
@mcp.tool(name="bloomberg_get_estimates_detail")
async def bloomberg_get_estimates_detail(params: EstimatesInput) -> str:
    """
    Get multi-period consensus estimates with revision momentum.
    
    For each security × period, returns:
    - BEST_{metric}: consensus estimate
    - BEST_{metric}_MEDIAN: median
    - BEST_{metric}_HIGH / LOW: range
    - BEST_{metric}_NUM_EST: analyst count
    - BEST_{metric}_4WK_CHG: 4-week revision momentum
    - BEST_{metric}_SURPRISE: last surprise
    """
```

Implementation: Loop over periods ["1FY","2FY","1FQ","2FQ"], each with override
`BEST_FPERIOD_OVERRIDE`. Parallelize if possible.

### Tool: bloomberg_get_technical_analysis

Uses //blp/tasvc service — DIFFERENT from //blp/refdata.

```python
@mcp.tool(name="bloomberg_get_technical_analysis")
async def bloomberg_get_technical_analysis(params: TechnicalAnalysisInput) -> str:
    """
    Get technical indicators via Bloomberg TA service.
    
    Supported studies: RSI, MACD, Bollinger Bands, SMA, EMA, DMI/ADX, Stochastic
    """
```

**CRITICAL: tasvc uses CHOICE-based element selection, NOT fromPy().**

```python
# Must use element-level API, not fromPy():
service = session.getService("//blp/tasvc")
request = service.createRequest("studyRequest")

price_source = request.getElement("priceSource")
price_source.getElement("securityName").setValue("IBM US Equity")
price_source.getElement("dataRange").setChoice("historical")
historical = price_source.getElement("dataRange").getElement("historical")
historical.getElement("startDate").setValue("20240101")
historical.getElement("endDate").setValue("20240630")

# Study selection — CHOICE type
request.getElement("studyAttributes").setChoice("rsiStudyAttributes")
rsi = request.getElement("studyAttributes").getElement("rsiStudyAttributes")
rsi.getElement("period").setValue(14)
```

Study names: `dmiStudyAttributes`, `smaStudyAttributes`, `emaStudyAttributes`,
`bollingerStudyAttributes`, `macdStudyAttributes`, `rsiStudyAttributes`, `stocStudyAttributes`

---

## PHASE 3: Ownership + Supply Chain + BQL

### Tool: bloomberg_get_ownership
Combines BDP (summary metrics) + BDS (holder list). See PHASE 1 BDS tool.

### Tool: bloomberg_get_supply_chain
BDS fields: SUPPLY_CHAIN_SUPPLIERS, SUPPLY_CHAIN_CUSTOMERS, SUPPLY_CHAIN_COMPETITORS

### Tool: bloomberg_run_bql
```python
service = session.getService("//blp/bqlsvc")
request = service.createRequest("sendQuery")
request.set("expression", "get(px_last()) for(['AAPL US Equity'])")
```
NOTE: //blp/bqlsvc works on Desktop API (localhost:8194). Standard BBG Professional license.
If service fails to open, log warning and skip — do not crash.

---

## PHASE 4: Morning Note Data Collection Overhaul

### Current state
Japan-focused: Nikkei/TOPIX/EWJ proxies + Japan ADR mapping + Japan equity watchlist.
3,648 lines across 7 files. Architecture is sound — only config needs changing.

### Target state
Multi-market: US + HK + A-share focused. Four-tier portfolio universe system.

### What to change

**config.py — Full rewrite of universe definitions:**
- Replace JAPAN_PROXIES with HK_PROXIES (HSI, HSCEI, HSTECH, A50 futures)
- Replace JAPAN_ADRS with AH_PAIRS (A/H share premium tracking)
- Replace JAPAN_WATCHLIST with configurable PORTFOLIO_TIERS:
  - Tier 1: Core Holdings (daily full coverage)
  - Tier 2: Watch List (catalyst monitoring)
  - Tier 3: Candidate Pool A (price + RVOL only)
  - Tier 4: Candidate Pool B (price only)
- Add Energy/Materials thematic ETFs: URA, URNM, COPX, REMX, XLE, XLU, GRID
- Keep US_INDEXES, SECTOR_ETFS, MACRO_* as-is (universally useful)

**Add hk_session.py (new file, mirrors japan_overnight.py logic):**
- HSI/HSCEI/HSTECH closing data
- A50 futures implied open
- AH premium tracking (H-price in HKD vs A-price in CNY, converted)
- USDCNH and USDCNY movement
- Southbound/Northbound flow if BBG fields available

**models.py — Add new data models:**
- AHPairSnapshot (h_ticker, a_ticker, ah_premium_pct, direction)
- HKSessionSnapshot (mirrors JapanOvernightSnapshot structure)
- PortfolioTierSnapshot (tier, securities, price/vol/key metrics)

**Keep unchanged:**
- storage.py — SQLite schema is generic
- historical.py — Query engine is market-agnostic
- screening.py — Uses dynamic_screening DSL, field-agnostic
- us_session.py — US data useful as-is, just expand industry ETFs

---

## Bloomberg API Technical Specs — Pitfall Reference

### CRITICAL: Singular vs Plural element names
| Request | Element | Correct |
|---------|---------|---------|
| ReferenceDataRequest | securities (plural) | `request.append("securities", ...)` |
| HistoricalDataRequest | securities (plural) | `request["securities"] = [...]` |
| IntradayBarRequest | security (SINGULAR) | `request.set("security", ...)` |
| IntradayBarRequest | eventType (SINGULAR) | `request.set("eventType", ...)` |
| IntradayTickRequest | security (SINGULAR) | `request.set("security", ...)` |
| IntradayTickRequest | eventTypes (PLURAL) | `request.getElement("eventTypes").appendValue(...)` |

### CRITICAL: Response structure differences
- ReferenceDataResponse: `securityData` is an ARRAY → iterate with numValues()
- HistoricalDataResponse: `securityData` is SINGLE SEQUENCE → one message per security
- IntradayBarResponse: nested `barData` → `barTickData[]`

### Python SDK method names (NOT C++)
```python
# CORRECT Python names:
element.getElementAsFloat(name)      # NOT getElementAsFloat64
element.getElementAsInteger(name)    # NOT getElementAsInt32
```

### Field limits
- ReferenceDataRequest: max 400 fields
- HistoricalDataRequest: max 25 fields

### Subscription vs Reference field names
- Subscription (//blp/mktdata): LAST_PRICE, BID, ASK
- Reference (//blp/refdata): PX_LAST, PX_BID, PX_ASK
These are NOT interchangeable.

### Date formats
- Historical requests: "YYYYMMDD" string (e.g., "20240101")
- Intraday requests: Python datetime objects or ISO 8601 strings

### periodicitySelection exact values
"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "SEMI_ANNUALLY", "YEARLY"

### nonTradingDayFillOption exact values
"NON_TRADING_WEEKDAYS", "ALL_CALENDAR_DAYS", "ACTIVE_DAYS_ONLY"

---

## Code Style Rules

1. All new tools: `@mcp.tool()` decorator + Pydantic BaseModel input
2. Request builders: put in `core/requests.py`, use `blpapi.Name()` constants
3. Response parsers: put in `core/responses.py`, prefer `toPy()` for convenience
4. New BBG services: open via `session.get_service("//blp/tasvc")` — already supported
5. FieldSets: define in `tools/dynamic_screening/models.py`
6. All responses support `response_format`: "markdown" | "json"
7. Use `_truncate_response()` to cap at 50,000 characters
8. Errors return string messages (MCP tool convention), do NOT raise exceptions in handlers
9. **NO company names, fund names, or proprietary framework references in code**
10. All naming must be generic and universally applicable

---

## Bloomberg Field Reference

### Price & Volume
PX_LAST, PX_BID, PX_ASK, PX_OPEN, PX_HIGH, PX_LOW, VOLUME,
CHG_PCT_1D, CHG_PCT_5D, CHG_PCT_1M, CHG_PCT_3M, CHG_PCT_YTD

### Valuation
PE_RATIO, BEST_PE_RATIO, PX_TO_BOOK_RATIO, PX_TO_SALES_RATIO,
EV_TO_EBITDA, EV_TO_T12M_EBITDA, DIVIDEND_YIELD, DVD_PRCNT_YLD,
PX_TO_FREE_CASH_FLOW, ENTERPRISE_VALUE, CUR_MKT_CAP, MARKET_CAP

### Profitability
RETURN_ON_EQUITY, RETURN_ON_ASSET, RETURN_ON_INV_CAPITAL,
GROSS_MARGIN, OPER_MARGIN, PROF_MARGIN, EBITDA_MARGIN

### Growth
SALES_GROWTH, EPS_GROWTH, EBITDA_GROWTH

### Balance Sheet
CUR_RATIO, QUICK_RATIO, TOT_DEBT_TO_TOT_EQY, TOT_DEBT_TO_EBITDA,
INTEREST_COVERAGE_RATIO, NET_DEBT

### Estimates & Consensus
BEST_EPS, BEST_EPS_MEDIAN, BEST_EPS_4WK_CHG, BEST_SALES,
BEST_EBITDA, BEST_TARGET_PRICE, EQY_REC_CONS, BEST_EST_LONG_TERM_GROWTH,
BEST_EPS_SURPRISE, BEST_SALES_SURPRISE, IS_EPS, SALES_REV_TURN

### Risk & Technical
BETA_RAW_OVERRIDABLE, VOLATILITY_10D, VOLATILITY_30D, VOLATILITY_90D,
VOLATILITY_260D, RSI_14D, MOV_AVG_50D, MOV_AVG_200D,
SHORT_INT_RATIO, PUT_CALL_OPEN_INTEREST_RATIO

### Ownership
PCT_HELD_BY_INSIDERS, PCT_HELD_BY_INSTITUTIONS, NUM_OF_INSTITUTIONAL_HOLDERS

### ESG
ESG_DISCLOSURE_SCORE, ENVIRON_DISCLOSURE_SCORE,
SOCIAL_DISCLOSURE_SCORE, GOVNCE_DISCLOSURE_SCORE

### Classification
GICS_SECTOR_NAME, GICS_INDUSTRY_GROUP_NAME, GICS_INDUSTRY_NAME,
GICS_SUB_INDUSTRY_NAME, BICS_LEVEL_1_SECTOR_NAME, BICS_LEVEL_2_INDUSTRY_GROUP_NAME

### Common BDS (Bulk) Fields
TOP_20_HOLDERS_PUBLIC_FILINGS, ALL_HOLDERS_PUBLIC_FILINGS,
DVD_HIST_ALL, SUPPLY_CHAIN_SUPPLIERS, SUPPLY_CHAIN_CUSTOMERS,
SUPPLY_CHAIN_COMPETITORS, INDX_MEMBERS, ANALYST_RECOMMENDATIONS,
ERN_ANN_DT_AND_PER, BOARD_OF_DIRECTORS, EARN_ANN_DT_TIME_HIST_WITH_EPS,
CORPORATE_ACTION_CALENDAR

### Security Identifier Formats
```
AAPL US Equity       # US stock
700 HK Equity        # HK stock
1133 HK Equity       # HK stock (numeric)
601012 CH Equity     # A-share (Shanghai)
000002 CH Equity     # A-share (Shenzhen)
002594 CH Equity     # A-share (Shenzhen SME)
300750 CH Equity     # A-share (ChiNext)
SPX Index            # Index
HSI Index            # Hang Seng Index
VIX Index            # Volatility index
EUR Curncy           # Currency
CL1 Comdty           # Commodity future
```

---

## Testing

```bash
# Unit tests (no Bloomberg required)
pytest tests/

# Integration tests (requires live Bloomberg Terminal)
pytest tests/integration/

# Format and lint
black src/ tests/
ruff check src/ tests/
mypy src/
```

---

## Dependencies

- `blpapi` — Bloomberg Python SDK (installed separately)
- `mcp` — Model Context Protocol SDK
- `pydantic` — Input validation
- `fastmcp` — MCP server framework
- Python 3.10+
- Bloomberg Terminal or B-PIPE connection
