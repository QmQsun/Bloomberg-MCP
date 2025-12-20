"""Data models for dynamic screening toolset.

Provides typed dataclasses for:
- Universe definitions (static lists, saved screens, index constituents)
- Field sets (pre-defined collections of Bloomberg fields)
- Screen results and security records
- Signal reports for hypothesis validation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union


# =============================================================================
# FIELD SETS - Pre-defined collections of Bloomberg fields
# =============================================================================

@dataclass(frozen=True)
class FieldSet:
    """A named collection of Bloomberg fields.

    FieldSets are immutable and can be combined with + operator.

    Example:
        >>> momentum = FieldSet("momentum", ["CHG_PCT_1D", "CHG_PCT_5D"])
        >>> volume = FieldSet("volume", ["VOLUME", "VOLUME_AVG_20D"])
        >>> combined = momentum + volume
        >>> print(combined.fields)
        ['CHG_PCT_1D', 'CHG_PCT_5D', 'VOLUME', 'VOLUME_AVG_20D']
    """
    name: str
    fields: tuple  # Using tuple for hashability (frozen=True)

    def __init__(self, name: str, fields: List[str]):
        # Workaround for frozen dataclass
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'fields', tuple(fields))

    def __add__(self, other: "FieldSet") -> "FieldSet":
        """Combine two field sets, preserving order and removing duplicates."""
        seen = set()
        combined = []
        for f in list(self.fields) + list(other.fields):
            if f not in seen:
                seen.add(f)
                combined.append(f)
        return FieldSet(f"{self.name}+{other.name}", combined)

    def __iter__(self):
        return iter(self.fields)

    def __len__(self):
        return len(self.fields)


class FieldSets:
    """Pre-defined field sets for common screening use cases.

    All fields are VALIDATED against Bloomberg CustomEqsRequest API (2025-12-18).
    70 fields confirmed working across US Equities and Japan ADRs.
    See references/validated-fields.md for the complete compatibility matrix.

    Example:
        >>> fields = FieldSets.RVOL + FieldSets.MOMENTUM
        >>> screen.with_fields(fields)
    """

    # ==========================================================================
    # PRICE FIELDS (13 validated)
    # ==========================================================================

    # Core price fields
    PRICE = FieldSet("price", [
        "PX_LAST",
        "PX_OPEN",
        "PX_HIGH",
        "PX_LOW",
        "CHG_PCT_1D",
    ])

    # Extended price fields
    PRICE_EXTENDED = FieldSet("price_extended", [
        "PX_LAST",
        "PX_OPEN",
        "PX_HIGH",
        "PX_LOW",
        "PX_BID",
        "PX_ASK",
        "PX_MID",
        "PX_CLOSE_1D",
        "PX_LAST_EOD",
        "PX_OFFICIAL_CLOSE",
        "LAST_PRICE",
        "LAST_TRADE",
    ])

    # ==========================================================================
    # MOMENTUM / CHANGE FIELDS (9 validated)
    # ==========================================================================

    # Core momentum (short-term)
    MOMENTUM = FieldSet("momentum", [
        "CHG_PCT_1D",
        "CHG_PCT_5D",
        "CHG_PCT_1M",
        "CHG_PCT_YTD",
    ])

    # Extended momentum (all timeframes)
    MOMENTUM_EXTENDED = FieldSet("momentum_extended", [
        "CHG_PCT_1D",
        "CHG_PCT_5D",
        "CHG_PCT_1M",
        "CHG_PCT_3M",
        "CHG_PCT_6M",
        "CHG_PCT_1YR",
        "CHG_PCT_YTD",
    ])

    # Net change fields (dollar amount)
    NET_CHANGE = FieldSet("net_change", [
        "CHG_NET_1D",
        "CHG_NET_5D",
    ])

    # ==========================================================================
    # VOLUME FIELDS (11 validated)
    # ==========================================================================

    # Core volume + RVOL calculation
    RVOL = FieldSet("rvol", [
        "VOLUME",
        "VOLUME_AVG_20D",
        "TURNOVER",
    ])

    # Extended volume with all averages
    VOLUME_EXTENDED = FieldSet("volume_extended", [
        "VOLUME",
        "VOLUME_AVG_5D",
        "VOLUME_AVG_10D",
        "VOLUME_AVG_20D",
        "VOLUME_AVG_30D",
        "TURNOVER",
        "PX_VOLUME",
    ])

    # Liquidity/trading value metrics
    LIQUIDITY = FieldSet("liquidity", [
        "VOLUME",
        "TURNOVER",
        "AVG_DAILY_VALUE_TRADED_5D",
        "AVG_DAILY_VALUE_TRADED_20D",
        "EQY_SH_OUT",
    ])

    # ==========================================================================
    # TECHNICAL FIELDS (10 validated)
    # ==========================================================================

    # Core technical indicators
    TECHNICAL = FieldSet("technical", [
        "RSI_14D",
        "VOLATILITY_30D",
        "VOLATILITY_90D",
        "BETA_RAW_OVERRIDABLE",
    ])

    # Extended technical with all volatility timeframes
    TECHNICAL_EXTENDED = FieldSet("technical_extended", [
        "RSI_14D",
        "RSI_30D",
        "VOLATILITY_10D",
        "VOLATILITY_20D",
        "VOLATILITY_30D",
        "VOLATILITY_60D",
        "VOLATILITY_90D",
        "VOLATILITY_260D",
        "BETA_RAW_OVERRIDABLE",
        "BETA_ADJ_OVERRIDABLE",
    ])

    # Volatility only (for vol screening)
    VOLATILITY = FieldSet("volatility", [
        "VOLATILITY_10D",
        "VOLATILITY_20D",
        "VOLATILITY_30D",
        "VOLATILITY_60D",
        "VOLATILITY_90D",
        "VOLATILITY_260D",
    ])

    # RSI only (for overbought/oversold screening)
    RSI = FieldSet("rsi", [
        "RSI_14D",
        "RSI_30D",
    ])

    # Beta only (for market sensitivity screening)
    BETA = FieldSet("beta", [
        "BETA_RAW_OVERRIDABLE",
        "BETA_ADJ_OVERRIDABLE",
    ])

    # ==========================================================================
    # VALUATION FIELDS (4 validated - NOW WORKING!)
    # ==========================================================================

    # Core valuation - CONFIRMED WORKING with CustomEqsRequest
    VALUATION = FieldSet("valuation", [
        "PE_RATIO",
        "PX_TO_BOOK_RATIO",
        "CUR_MKT_CAP",
        "DIVIDEND_YIELD",  # Note: US equities only
    ])

    # Market cap only
    MARKET_CAP = FieldSet("market_cap", [
        "CUR_MKT_CAP",
        "EQY_SH_OUT",
    ])

    # ==========================================================================
    # ANALYST FIELDS (3 validated)
    # ==========================================================================

    ANALYST = FieldSet("analyst", [
        "EQY_REC_CONS",       # Consensus rating (1-5 scale)
        "BEST_TARGET_PRICE",  # Consensus target price
        "TOT_ANALYST_REC",    # Total number of analysts
    ])

    # ==========================================================================
    # CLASSIFICATION FIELDS (7 validated)
    # ==========================================================================

    # Sector classification (GICS)
    SECTOR = FieldSet("sector", [
        "GICS_SECTOR_NAME",
        "GICS_INDUSTRY_GROUP_NAME",
        "GICS_INDUSTRY_NAME",
    ])

    # Extended classification
    CLASSIFICATION = FieldSet("classification", [
        "GICS_SECTOR",
        "GICS_SECTOR_NAME",
        "GICS_INDUSTRY_GROUP_NAME",
        "GICS_INDUSTRY_NAME",
        "GICS_SUB_INDUSTRY_NAME",
        "COUNTRY_ISO",
        "EXCH_CODE",
    ])

    # ==========================================================================
    # DESCRIPTIVE FIELDS (9 validated)
    # ==========================================================================

    # Basic descriptive
    DESCRIPTIVE = FieldSet("descriptive", [
        "NAME",
        "SECURITY_TYP",
        "EXCH_CODE",
    ])

    # Extended descriptive with identifiers
    DESCRIPTIVE_EXTENDED = FieldSet("descriptive_extended", [
        "NAME",
        "SHORT_NAME",
        "TICKER",
        "SECURITY_TYP",
        "SECURITY_DES",
        "PARSEKYABLE_DES",
        "ID_BB_GLOBAL",
        "CIE_DES",
        "EXCH_CODE",
        "COUNTRY_ISO",
    ])

    # Identifiers only
    IDENTIFIERS = FieldSet("identifiers", [
        "TICKER",
        "ID_BB_GLOBAL",
        "SECURITY_DES",
        "PARSEKYABLE_DES",
    ])

    # ==========================================================================
    # SENTIMENT FIELDS (2 validated)
    # ==========================================================================

    # News sentiment - Works for both US equities and ADRs
    SENTIMENT = FieldSet("sentiment", [
        "NEWS_SENTIMENT",
        "NEWS_SENTIMENT_DAILY_AVG",
    ])

    # ==========================================================================
    # QUOTE FIELDS (5 validated)
    # ==========================================================================

    # Quote/market microstructure
    QUOTE = FieldSet("quote", [
        "PX_BID",
        "PX_ASK",
        "BID_SIZE",
        "ASK_SIZE",
        "QUOTE_TYP",
    ])

    # Time fields
    TIME_FIELDS = FieldSet("time_fields", [
        "TIME",
        "LAST_UPDATE_DT",
    ])

    # ==========================================================================
    # COMPOSITE FIELD SETS (Pre-configured for common use cases)
    # ==========================================================================

    # ADR screening (optimized for Japan ADR universe)
    ADR = FieldSet("adr", [
        "PX_LAST",
        "CHG_PCT_1D",
        "VOLUME",
        "VOLUME_AVG_20D",
        "NEWS_SENTIMENT",
        "GICS_SECTOR_NAME",
    ])

    # Morning note comprehensive set
    MORNING_NOTE = FieldSet("morning_note", [
        "PX_LAST",
        "PX_OPEN",
        "PX_HIGH",
        "PX_LOW",
        "CHG_PCT_1D",
        "VOLUME",
        "VOLUME_AVG_20D",
        "NEWS_SENTIMENT",
        "NEWS_SENTIMENT_DAILY_AVG",
        "GICS_SECTOR_NAME",
    ])

    # Full screening set (most comprehensive)
    SCREENING_FULL = FieldSet("screening_full", [
        # Price
        "PX_LAST", "PX_OPEN", "PX_HIGH", "PX_LOW",
        # Change
        "CHG_PCT_1D", "CHG_PCT_5D", "CHG_PCT_1M", "CHG_PCT_YTD",
        # Volume
        "VOLUME", "VOLUME_AVG_20D", "TURNOVER",
        # Technical
        "RSI_14D", "VOLATILITY_30D", "BETA_RAW_OVERRIDABLE",
        # Valuation
        "PE_RATIO", "PX_TO_BOOK_RATIO", "CUR_MKT_CAP",
        # Classification
        "GICS_SECTOR_NAME", "GICS_INDUSTRY_NAME",
        # Sentiment
        "NEWS_SENTIMENT",
        # Analyst
        "EQY_REC_CONS", "BEST_TARGET_PRICE",
    ])

    # Value screening set
    VALUE_SCREEN = FieldSet("value_screen", [
        "PX_LAST",
        "CHG_PCT_1D",
        "PE_RATIO",
        "PX_TO_BOOK_RATIO",
        "DIVIDEND_YIELD",
        "CUR_MKT_CAP",
        "GICS_SECTOR_NAME",
    ])

    # Momentum screening set
    MOMENTUM_SCREEN = FieldSet("momentum_screen", [
        "PX_LAST",
        "CHG_PCT_1D",
        "CHG_PCT_5D",
        "CHG_PCT_1M",
        "CHG_PCT_3M",
        "VOLUME",
        "VOLUME_AVG_20D",
        "RSI_14D",
        "GICS_SECTOR_NAME",
    ])

    # Volatility screening set
    VOLATILITY_SCREEN = FieldSet("volatility_screen", [
        "PX_LAST",
        "CHG_PCT_1D",
        "VOLATILITY_10D",
        "VOLATILITY_30D",
        "VOLATILITY_90D",
        "BETA_RAW_OVERRIDABLE",
        "VOLUME",
        "VOLUME_AVG_20D",
        "GICS_SECTOR_NAME",
    ])

    # Analyst-focused screening set
    ANALYST_SCREEN = FieldSet("analyst_screen", [
        "PX_LAST",
        "CHG_PCT_1D",
        "EQY_REC_CONS",
        "BEST_TARGET_PRICE",
        "TOT_ANALYST_REC",
        "PE_RATIO",
        "CUR_MKT_CAP",
        "GICS_SECTOR_NAME",
    ])


# =============================================================================
# UNIVERSE DEFINITIONS
# =============================================================================

class UniverseType(Enum):
    """Type of universe source."""
    STATIC = "static"           # Explicit list of securities
    SAVED_SCREEN = "screen"     # Bloomberg saved EQS screen
    INDEX = "index"             # Index constituents


@dataclass
class ScreenUniverse:
    """Defines the universe of securities for screening.

    A universe can be:
    - Static: An explicit list of securities
    - Saved Screen: Results from a Bloomberg EQS screen
    - Index: Constituents of an index (SPX, TOPIX, etc.)

    Example:
        >>> # Static universe
        >>> universe = ScreenUniverse.from_list([
        ...     "AAPL US Equity", "MSFT US Equity"
        ... ])
        >>>
        >>> # From saved screen
        >>> universe = ScreenUniverse.from_screen("Japan_Liquid_ADRs")
        >>>
        >>> # Index constituents
        >>> universe = ScreenUniverse.from_index("SPX Index")
    """

    type: UniverseType
    source: str  # Screen name, index ticker, or "static"
    securities: List[str] = field(default_factory=list)
    screen_type: str = "PRIVATE"  # For saved screens

    @classmethod
    def from_list(cls, securities: List[str]) -> "ScreenUniverse":
        """Create universe from explicit security list."""
        return cls(
            type=UniverseType.STATIC,
            source="static",
            securities=securities,
        )

    @classmethod
    def from_screen(
        cls,
        screen_name: str,
        screen_type: str = "PRIVATE"
    ) -> "ScreenUniverse":
        """Create universe from saved Bloomberg EQS screen."""
        return cls(
            type=UniverseType.SAVED_SCREEN,
            source=screen_name,
            screen_type=screen_type,
        )

    @classmethod
    def from_index(cls, index_ticker: str) -> "ScreenUniverse":
        """Create universe from index constituents."""
        return cls(
            type=UniverseType.INDEX,
            source=index_ticker,
        )


# =============================================================================
# SCREEN RESULTS
# =============================================================================

@dataclass
class SecurityRecord:
    """A single security with its field data.

    Provides both dict-style and attribute-style access to fields.

    Example:
        >>> rec = SecurityRecord("AAPL US Equity", {"PX_LAST": 150.0})
        >>> rec.PX_LAST  # Attribute access
        150.0
        >>> rec["PX_LAST"]  # Dict access
        150.0
    """

    security: str
    fields: Dict[str, Any] = field(default_factory=dict)

    # Computed fields (set during filtering/ranking)
    rank: Optional[int] = None
    percentile: Optional[float] = None
    signal_type: Optional[str] = None

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to fields."""
        if name in ("security", "fields", "rank", "percentile", "signal_type"):
            return object.__getattribute__(self, name)
        fields = object.__getattribute__(self, "fields")
        if name in fields:
            return fields[name]
        raise AttributeError(f"'{type(self).__name__}' has no field '{name}'")

    def __getitem__(self, key: str) -> Any:
        """Allow dict-style access to fields."""
        return self.fields[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get field value with default."""
        return self.fields.get(key, default)

    @property
    def rvol(self) -> Optional[float]:
        """Computed relative volume (VOLUME / VOLUME_AVG_20D)."""
        vol = self.fields.get("VOLUME")
        avg = self.fields.get("VOLUME_AVG_20D")
        if vol and avg and avg > 0:
            return vol / avg
        return None

    @property
    def rvol_5d(self) -> Optional[float]:
        """Relative volume vs 5-day average."""
        vol = self.fields.get("VOLUME")
        avg = self.fields.get("VOLUME_AVG_5D")
        if vol and avg and avg > 0:
            return vol / avg
        return None

    @property
    def change_pct(self) -> Optional[float]:
        """1-day percentage change."""
        return self.fields.get("CHG_PCT_1D")

    @property
    def change_5d(self) -> Optional[float]:
        """5-day percentage change."""
        return self.fields.get("CHG_PCT_5D")

    @property
    def change_1m(self) -> Optional[float]:
        """1-month percentage change."""
        return self.fields.get("CHG_PCT_1M")

    @property
    def change_3m(self) -> Optional[float]:
        """3-month percentage change."""
        return self.fields.get("CHG_PCT_3M")

    @property
    def change_ytd(self) -> Optional[float]:
        """Year-to-date percentage change."""
        return self.fields.get("CHG_PCT_YTD")

    @property
    def ticker(self) -> str:
        """Short ticker (without ' Equity' suffix)."""
        return self.security.replace(" Equity", "").replace(" US", "").replace(" JP", "")

    @property
    def price(self) -> Optional[float]:
        """Last price."""
        return self.fields.get("PX_LAST")

    @property
    def pe_ratio(self) -> Optional[float]:
        """Price-to-earnings ratio."""
        return self.fields.get("PE_RATIO")

    @property
    def pb_ratio(self) -> Optional[float]:
        """Price-to-book ratio."""
        return self.fields.get("PX_TO_BOOK_RATIO")

    @property
    def market_cap(self) -> Optional[float]:
        """Current market capitalization."""
        return self.fields.get("CUR_MKT_CAP")

    @property
    def rsi(self) -> Optional[float]:
        """14-day RSI."""
        return self.fields.get("RSI_14D")

    @property
    def beta(self) -> Optional[float]:
        """Raw beta."""
        return self.fields.get("BETA_RAW_OVERRIDABLE")

    @property
    def volatility(self) -> Optional[float]:
        """30-day volatility."""
        return self.fields.get("VOLATILITY_30D")

    @property
    def sentiment(self) -> Optional[float]:
        """News sentiment score."""
        return self.fields.get("NEWS_SENTIMENT")

    @property
    def sector(self) -> Optional[str]:
        """GICS sector name."""
        return self.fields.get("GICS_SECTOR_NAME")

    @property
    def industry(self) -> Optional[str]:
        """GICS industry name."""
        return self.fields.get("GICS_INDUSTRY_NAME")

    @property
    def analyst_rating(self) -> Optional[float]:
        """Consensus analyst rating (1-5 scale)."""
        return self.fields.get("EQY_REC_CONS")

    @property
    def target_price(self) -> Optional[float]:
        """Consensus target price."""
        return self.fields.get("BEST_TARGET_PRICE")

    @property
    def upside(self) -> Optional[float]:
        """Upside to target price as percentage."""
        price = self.fields.get("PX_LAST")
        target = self.fields.get("BEST_TARGET_PRICE")
        if price and target and price > 0:
            return ((target - price) / price) * 100
        return None

    @property
    def is_oversold(self) -> bool:
        """RSI below 30 (oversold condition)."""
        rsi = self.fields.get("RSI_14D")
        return rsi is not None and rsi < 30

    @property
    def is_overbought(self) -> bool:
        """RSI above 70 (overbought condition)."""
        rsi = self.fields.get("RSI_14D")
        return rsi is not None and rsi > 70

    @property
    def is_high_rvol(self) -> bool:
        """Relative volume above 2x average."""
        rvol = self.rvol
        return rvol is not None and rvol > 2.0

    @property
    def is_value(self) -> bool:
        """Low PE (< 15) and low P/B (< 2)."""
        pe = self.fields.get("PE_RATIO")
        pb = self.fields.get("PX_TO_BOOK_RATIO")
        return (pe is not None and pe < 15 and pe > 0) or (pb is not None and pb < 2 and pb > 0)


@dataclass
class ScreenResult:
    """Results from a dynamic screen execution.

    Contains the filtered securities with their field data,
    along with metadata about the screening process.
    """

    name: str
    records: List[SecurityRecord] = field(default_factory=list)
    universe_size: int = 0
    filtered_count: int = 0
    execution_time_ms: float = 0
    errors: List[str] = field(default_factory=list)

    # Metadata
    universe_source: Optional[str] = None
    fields_requested: List[str] = field(default_factory=list)
    filters_applied: List[str] = field(default_factory=list)
    executed_at: datetime = field(default_factory=datetime.now)

    @property
    def securities(self) -> List[str]:
        """List of security identifiers."""
        return [r.security for r in self.records]

    def __iter__(self):
        return iter(self.records)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index: int) -> SecurityRecord:
        return self.records[index]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "universe_size": self.universe_size,
            "filtered_count": self.filtered_count,
            "execution_time_ms": self.execution_time_ms,
            "securities": [
                {
                    "security": r.security,
                    "rank": r.rank,
                    **r.fields,
                }
                for r in self.records
            ],
            "errors": self.errors,
            "metadata": {
                "universe_source": self.universe_source,
                "fields_requested": self.fields_requested,
                "filters_applied": self.filters_applied,
                "executed_at": self.executed_at.isoformat(),
            }
        }


# =============================================================================
# SIGNAL REPORTS - For hypothesis validation
# =============================================================================

class SignalType(Enum):
    """Types of trading signals."""
    HIGH_RVOL_UP = "high_rvol_up"      # High volume + positive move
    HIGH_RVOL_DOWN = "high_rvol_down"  # High volume + negative move
    BREAKOUT = "breakout"               # Price breakout
    BREAKDOWN = "breakdown"             # Price breakdown
    SENTIMENT_DIVERGE = "sentiment_diverge"  # Sentiment vs price divergence
    MOMENTUM_LEADER = "momentum_leader"
    MOMENTUM_LAGGARD = "momentum_laggard"


@dataclass
class SignalReport:
    """A hypothesis-validated signal with supporting evidence.

    Used in morning note generation to provide actionable insights
    backed by quantitative evidence.

    Example:
        >>> signal = SignalReport(
        ...     signal_type=SignalType.HIGH_RVOL_UP,
        ...     securities=["AAPL US Equity"],
        ...     hypothesis="Tech momentum continues",
        ...     evidence={
        ...         "rvol_avg": 2.5,
        ...         "sector_breadth": 0.7,
        ...     },
        ...     confidence=0.8,
        ... )
    """

    signal_type: SignalType
    securities: List[str]
    hypothesis: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5  # 0-1 confidence score
    priority: int = 3  # 1=highest, 5=lowest

    # Supporting data
    screen_result: Optional[ScreenResult] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "signal_type": self.signal_type.value,
            "securities": self.securities,
            "hypothesis": self.hypothesis,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "priority": self.priority,
            "notes": self.notes,
        }
