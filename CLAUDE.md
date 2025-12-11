# Bloomberg MCP

Data access layer for Bloomberg Terminal. Request/response only, no streaming.

## Quick Reference

```python
# Primary imports
from bloomberg_mcp.tools import (
    get_reference_data,      # Current field values
    get_historical_data,     # Time series
    get_intraday_bars,       # OHLCV bars
    get_intraday_ticks,      # Raw ticks
    search_securities,       # Find securities
    search_fields,           # Discover fields
    get_field_info,          # Field metadata
)

# Data types
from bloomberg_mcp import (
    SecurityData,            # Reference data result
    HistoricalData,          # Historical data result
    IntradayBar,             # Single bar
    IntradayBarData,         # Bars collection
)
```

---

## Function Signatures

### Reference Data
```python
def get_reference_data(
    securities: List[str],           # ["AAPL US Equity", "MSFT US Equity"]
    fields: List[str],               # ["PX_LAST", "PE_RATIO"]
    overrides: Optional[Dict[str, Any]] = None,
) -> List[SecurityData]:
    """Returns list of SecurityData, one per security."""
```

### Historical Data
```python
def get_historical_data(
    securities: List[str],
    fields: List[str],
    start_date: str,                 # "YYYYMMDD" format
    end_date: str,                   # "YYYYMMDD" format
    periodicity: str = "DAILY",      # DAILY|WEEKLY|MONTHLY|QUARTERLY|YEARLY
) -> List[HistoricalData]:
    """Returns list of HistoricalData, one per security."""
```

### Intraday Bars
```python
def get_intraday_bars(
    security: str,                   # Single security only
    start: datetime,                 # GMT timezone
    end: datetime,                   # GMT timezone
    interval: int = 60,              # Minutes: 1,5,15,30,60
    event_type: str = "TRADE",       # TRADE|BID|ASK
) -> List[IntradayBar]:
    """Returns list of IntradayBar objects."""
```

### Intraday Ticks
```python
def get_intraday_ticks(
    security: str,
    start: datetime,                 # GMT timezone
    end: datetime,
    event_types: List[str] = ["TRADE"],
) -> List[dict]:
    """Returns list of tick dicts with time, value, size."""
```

### Search Securities
```python
def search_securities(
    query: str,                      # "Apple", "IBM", partial match
    max_results: int = 10,
    yellow_key: Optional[str] = None,  # Equity|Index|Comdty|Curncy
) -> List[dict]:
    """Returns [{"security": "AAPL US Equity", "description": "..."}]"""
```

### Search Fields
```python
def search_fields(
    query: str,                      # "price earnings", "dividend"
    field_type: Optional[str] = None,  # Exclude: Static|RealTime|Historical
) -> List[dict]:
    """Returns [{"id": "PE_RATIO", "description": "..."}]"""
```

### Get Field Info
```python
def get_field_info(
    field_ids: List[str],            # ["PX_LAST", "PE_RATIO"]
    return_documentation: bool = True,
) -> List[dict]:
    """Returns detailed field metadata."""
```

---

## Data Types

```python
@dataclass
class SecurityData:
    security: str                    # "AAPL US Equity"
    fields: Dict[str, Any]           # {"PX_LAST": 150.0, "PE_RATIO": 25.0}
    errors: List[str]                # Field-level errors

@dataclass
class HistoricalData:
    security: str
    data: List[Dict[str, Any]]       # [{"date": datetime, "PX_LAST": 150.0}, ...]
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
```

---

## Common Patterns

### Single Security Analysis
```python
data = get_reference_data(["AAPL US Equity"], [
    "PX_LAST", "PE_RATIO", "RETURN_ON_EQUITY", "VOLATILITY_30D"
])
sec = data[0]
price = sec.fields.get("PX_LAST")
pe = sec.fields.get("PE_RATIO")
```

### Multi-Security Comparison
```python
tickers = ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity"]
data = get_reference_data(tickers, ["PX_LAST", "PE_RATIO", "MARKET_CAP"])
for sec in data:
    print(f"{sec.security}: P/E={sec.fields.get('PE_RATIO')}")
```

### Historical Price Series
```python
hist = get_historical_data(
    ["SPY US Equity"],
    ["PX_LAST"],
    "20240101",
    "20241231",
    periodicity="DAILY"
)
prices = [d["PX_LAST"] for d in hist[0].data]
dates = [d["date"] for d in hist[0].data]
```

### Intraday Analysis (times in GMT)
```python
from datetime import datetime
bars = get_intraday_bars(
    "AAPL US Equity",
    start=datetime(2024, 12, 10, 14, 30),  # 9:30 AM ET = 14:30 GMT
    end=datetime(2024, 12, 10, 21, 0),     # 4:00 PM ET = 21:00 GMT
    interval=60
)
```

### Field Discovery
```python
# Find fields by keyword
results = search_fields("dividend yield")
field_id = results[0]["id"]  # e.g., "DIVIDEND_YIELD"

# Get field details
info = get_field_info(["DIVIDEND_YIELD"])
```

---

## Bloomberg Field Reference

### Price & Volume
| Field | Description |
|-------|-------------|
| `PX_LAST` | Last price |
| `PX_BID` / `PX_ASK` | Bid/Ask |
| `PX_OPEN` / `PX_HIGH` / `PX_LOW` | OHLC |
| `VOLUME` | Trading volume |
| `CHG_PCT_1D` | 1-day change % |
| `CHG_PCT_YTD` | YTD change % |

### Valuation
| Field | Description |
|-------|-------------|
| `PE_RATIO` | Price/Earnings (trailing) |
| `BEST_PE_RATIO` | Forward P/E |
| `PX_TO_BOOK_RATIO` | Price/Book |
| `PX_TO_SALES_RATIO` | Price/Sales |
| `EV_TO_EBITDA` | EV/EBITDA |
| `DIVIDEND_YIELD` | Dividend yield % |
| `MARKET_CAP` | Market capitalization |

### Profitability
| Field | Description |
|-------|-------------|
| `RETURN_ON_EQUITY` | ROE % |
| `RETURN_ON_ASSET` | ROA % |
| `RETURN_ON_INV_CAPITAL` | ROIC % |
| `GROSS_MARGIN` | Gross margin % |
| `OPER_MARGIN` | Operating margin % |
| `PROF_MARGIN` | Net margin % |

### Growth
| Field | Description |
|-------|-------------|
| `SALES_GROWTH` | Revenue growth % |
| `EPS_GROWTH` | EPS growth % |
| `EBITDA_GROWTH` | EBITDA growth % |

### Balance Sheet
| Field | Description |
|-------|-------------|
| `CUR_RATIO` | Current ratio |
| `QUICK_RATIO` | Quick ratio |
| `TOT_DEBT_TO_TOT_EQY` | Debt/Equity |
| `TOT_DEBT_TO_EBITDA` | Debt/EBITDA |
| `INTEREST_COVERAGE_RATIO` | Interest coverage |

### Risk & Technical
| Field | Description |
|-------|-------------|
| `BETA_RAW_OVERRIDABLE` | Beta |
| `VOLATILITY_30D` | 30-day volatility % |
| `VOLATILITY_90D` | 90-day volatility % |
| `RSI_14D` | 14-day RSI |
| `MOV_AVG_50D` | 50-day MA |
| `MOV_AVG_200D` | 200-day MA |

### Analyst
| Field | Description |
|-------|-------------|
| `EQY_REC_CONS` | Consensus rating (1-5) |
| `BEST_TARGET_PRICE` | Target price |
| `BEST_EPS` | Consensus EPS |

---

## Security Identifier Formats

```
AAPL US Equity       # US stock
VOD LN Equity        # UK stock
7203 JP Equity       # Japan stock (numeric)
SPX Index            # Index
EUR Curncy           # Currency
CL1 Comdty           # Commodity future
```

---

## Error Handling

```python
data = get_reference_data(["INVALID US Equity"], ["PX_LAST"])
if data[0].errors:
    print(f"Errors: {data[0].errors}")

# Connection errors raise RuntimeError
try:
    data = get_reference_data(...)
except RuntimeError as e:
    print(f"Connection failed: {e}")
```

---

## Module Structure

```
src/bloomberg_mcp/
├── __init__.py          # Exports: tools + data types
├── core/
│   ├── session.py       # BloombergSession singleton
│   ├── requests.py      # build_*_request() functions
│   └── responses.py     # parse_*_response() + dataclasses
└── tools/
    ├── reference.py     # get_reference_data()
    ├── historical.py    # get_historical_data()
    ├── intraday.py      # get_intraday_bars/ticks()
    └── search.py        # search_securities/fields(), get_field_info()
```

---

## Dependencies

- `blpapi` - Bloomberg Python SDK (installed separately)
- Python 3.10+
- Requires Bloomberg Terminal or B-PIPE connection
