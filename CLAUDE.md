# Bloomberg MCP - AI Assistant Guide

## Project Overview

**Purpose:** Pure data access layer for Bloomberg Terminal via the Bloomberg API (blpapi).

**Scope:** Request/response operations only. No real-time streaming. No business logic or analysis.

**Design Philosophy:**
- This package fetches data. Analysis/reports live in separate packages that consume this.
- All functions auto-connect to Bloomberg if not already connected.
- Returns typed dataclasses or dicts - no raw blpapi objects leak out.

---

## Architecture

```
bloomberg-mcp/
├── src/bloomberg_mcp/
│   ├── __init__.py              # Package exports (session + dataclasses)
│   ├── core/                    # Low-level Bloomberg API interaction
│   │   ├── __init__.py
│   │   ├── session.py           # BloombergSession singleton
│   │   ├── requests.py          # Request builders (fromPy pattern)
│   │   └── responses.py         # Response parsers + dataclasses
│   └── tools/                   # High-level data access functions
│       ├── __init__.py          # Exports all tool functions
│       ├── reference.py         # get_reference_data()
│       ├── historical.py        # get_historical_data()
│       ├── intraday.py          # get_intraday_bars(), get_intraday_ticks()
│       └── search.py            # search_securities(), search_fields(), get_field_info()
├── tests/
├── pyproject.toml
└── CLAUDE.md                    # This file
```

---

## Module Reference

### `bloomberg_mcp.tools` - Primary API

**This is the main entry point. Import tools from here.**

| Function | Service | Description |
|----------|---------|-------------|
| `get_reference_data(securities, fields, overrides)` | //blp/refdata | Current field values for securities |
| `get_historical_data(securities, fields, start_date, end_date, periodicity)` | //blp/refdata | Time series data |
| `get_intraday_bars(security, start, end, interval, event_type)` | //blp/refdata | OHLCV bar data |
| `get_intraday_ticks(security, start, end, event_types)` | //blp/refdata | Raw tick data |
| `search_securities(query, max_results, yellow_key)` | //blp/instruments | Find securities by name |
| `search_fields(query, field_type)` | //blp/apiflds | Discover Bloomberg fields |
| `get_field_info(field_ids)` | //blp/apiflds | Detailed field metadata |

### `bloomberg_mcp.core.session` - Connection Management

```python
class BloombergSession:
    """Singleton session manager. Auto-created by tools, rarely used directly."""

    @classmethod
    def get_instance(cls, host="localhost", port=8194) -> BloombergSession

    def connect(self) -> bool
    def disconnect(self) -> None
    def is_connected(self) -> bool
    def get_service(self, name: str) -> blpapi.Service
    def send_request(self, request, service_name, parse_func) -> List[Any]
```

### `bloomberg_mcp.core.responses` - Data Types

```python
@dataclass
class SecurityData:
    security: str                    # e.g., "AAPL US Equity"
    fields: Dict[str, Any]           # e.g., {"PX_LAST": 150.0, "NAME": "Apple Inc"}
    errors: List[str]                # Field-level errors

@dataclass
class HistoricalData:
    security: str
    data: List[Dict[str, Any]]       # [{date: datetime, PX_LAST: 150.0, ...}, ...]
    errors: List[str]

@dataclass
class IntradayBar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    num_events: int

@dataclass
class IntradayBarData:
    security: str
    bars: List[IntradayBar]
    errors: List[str]
```

### `bloomberg_mcp.core.requests` - Request Builders

Low-level request construction. Used internally by tools. Only use directly for custom requests.

---

## Usage Patterns

### Basic Reference Data
```python
from bloomberg_mcp.tools import get_reference_data

# Single security, multiple fields
data = get_reference_data(
    securities=["AAPL US Equity"],
    fields=["PX_LAST", "PE_RATIO", "DIVIDEND_YIELD", "RETURN_ON_EQUITY"]
)
print(data[0].fields)
# {'PX_LAST': 150.25, 'PE_RATIO': 25.5, 'DIVIDEND_YIELD': 0.55, 'RETURN_ON_EQUITY': 147.5}

# Multiple securities
data = get_reference_data(
    securities=["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity"],
    fields=["PX_LAST", "NAME"]
)
for sec in data:
    print(f"{sec.security}: {sec.fields.get('PX_LAST')}")
```

### Historical Data
```python
from bloomberg_mcp.tools import get_historical_data

# Daily prices for past year
data = get_historical_data(
    securities=["SPY US Equity"],
    fields=["PX_LAST", "VOLUME"],
    start_date="20240101",
    end_date="20241231",
    periodicity="DAILY"
)
for point in data[0].data[-5:]:  # Last 5 days
    print(f"{point['date']}: {point['PX_LAST']}")

# Monthly data
data = get_historical_data(
    securities=["AAPL US Equity"],
    fields=["PX_LAST"],
    start_date="20200101",
    end_date="20241231",
    periodicity="MONTHLY"
)
```

### Intraday Data
```python
from bloomberg_mcp.tools import get_intraday_bars, get_intraday_ticks
from datetime import datetime

# Hourly bars (times in GMT)
bars = get_intraday_bars(
    security="AAPL US Equity",
    start=datetime(2024, 12, 10, 14, 30),  # 9:30 AM ET = 14:30 GMT
    end=datetime(2024, 12, 10, 21, 0),     # 4:00 PM ET = 21:00 GMT
    interval=60,  # 60-minute bars
    event_type="TRADE"
)
for bar in bars:
    print(f"{bar.time}: O={bar.open} H={bar.high} L={bar.low} C={bar.close}")

# Tick data (raw trades)
ticks = get_intraday_ticks(
    security="AAPL US Equity",
    start=datetime(2024, 12, 10, 14, 30),
    end=datetime(2024, 12, 10, 14, 35),  # 5 minutes of ticks
    event_types=["TRADE"]
)
```

### Field Discovery
```python
from bloomberg_mcp.tools import search_fields, get_field_info, search_securities

# Search for fields by keyword
fields = search_fields("price earnings ratio")
for f in fields[:5]:
    print(f"{f.get('id')}: {f.get('description')}")

# Get detailed info on specific fields
info = get_field_info(["PX_LAST", "PE_RATIO", "RETURN_ON_EQUITY"])
for f in info:
    print(f"{f.get('id')}: {f.get('datatype')} - {f.get('description')}")

# Search for securities
results = search_securities("Apple", max_results=5, yellow_key="Equity")
for r in results:
    print(f"{r['security']}: {r['description']}")
```

---

## Common Bloomberg Fields

### Price & Volume
- `PX_LAST` - Last price
- `PX_BID` / `PX_ASK` - Bid/ask
- `VOLUME` - Volume
- `CHG_PCT_1D` - 1-day change %
- `CHG_PCT_YTD` - YTD change %

### Valuation
- `PE_RATIO` - Price/Earnings
- `PX_TO_BOOK_RATIO` - Price/Book
- `PX_TO_SALES_RATIO` - Price/Sales
- `EV_TO_EBITDA` - EV/EBITDA
- `DIVIDEND_YIELD` - Dividend yield

### Profitability
- `RETURN_ON_EQUITY` - ROE
- `RETURN_ON_ASSET` - ROA
- `GROSS_MARGIN` - Gross margin
- `OPER_MARGIN` - Operating margin
- `NET_MARGIN` - Net margin

### Growth
- `SALES_GROWTH` - Revenue growth
- `EPS_GROWTH` - EPS growth
- `EBITDA_GROWTH` - EBITDA growth

### Balance Sheet
- `CUR_RATIO` - Current ratio
- `QUICK_RATIO` - Quick ratio
- `TOT_DEBT_TO_EBITDA` - Debt/EBITDA
- `TOT_DEBT_TO_TOT_EQY` - Debt/Equity

### Risk
- `BETA_RAW_OVERRIDABLE` - Beta
- `VOLATILITY_30D` / `VOLATILITY_90D` - Volatility

### Analyst
- `EQY_REC_CONS` - Consensus recommendation
- `BEST_TARGET_PRICE` - Target price
- `BEST_EPS` - Consensus EPS

Use `search_fields()` to discover more - Bloomberg has 30,000+ fields.

---

## Security Identifier Formats

```
AAPL US Equity      # US equity
VOD LN Equity       # UK equity
7203 JP Equity      # Japan equity (numeric)
SPX Index           # Index
USGG10YR Index      # Government bond yield
EUR Curncy          # Currency
CL1 Comdty          # Commodity future
IBM 4.7 02/19/46 Corp  # Corporate bond
```

---

## Bloomberg Services Used

| Service | Purpose |
|---------|---------|
| `//blp/refdata` | Reference data, historical data, intraday data |
| `//blp/instruments` | Security search/lookup |
| `//blp/apiflds` | Field search and metadata |

---

## Error Handling

Errors appear in two places:

1. **Security-level errors** - Invalid security, no data available
   ```python
   data = get_reference_data(["INVALID US Equity"], ["PX_LAST"])
   if data[0].errors:
       print(f"Error: {data[0].errors}")
   ```

2. **Field-level errors** - Invalid field for security type
   ```python
   data = get_reference_data(["SPX Index"], ["DIVIDEND_YIELD"])
   # May return error for fields not applicable to indexes
   ```

Connection errors raise `RuntimeError`.

---

## Testing

Tests use `blpapi.test` utilities to mock Bloomberg responses without live connection.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bloomberg_mcp
```

---

## Development Notes

### Adding New Request Types

1. Add request builder to `core/requests.py`
2. Add response parser to `core/responses.py`
3. Add high-level tool function to `tools/`
4. Export from `tools/__init__.py`

### Pre-defined Names

All `blpapi.Name` objects are pre-defined at module level in `core/requests.py` for performance. Don't create Names inline.

### Response Parsing

Use `msg.toPy()` to convert Bloomberg responses to Python dicts. Handle `RESPONSE_ERROR`, `SECURITY_ERROR`, and `FIELD_EXCEPTIONS`.

---

## Dependencies

- `blpapi` - Bloomberg API Python SDK (installed separately with BLPAPI_ROOT set)
- Python 3.10+

---

## Future: MCP Server

The MCP server (`server.py`) will expose these tools to AI assistants. Not yet implemented - focus is on stable Python API first.
