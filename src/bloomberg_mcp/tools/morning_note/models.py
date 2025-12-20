"""Pydantic models for morning note data structures.

These models provide structured output optimized for LLM reasoning:
- Rich context with derived metrics (rankings, spreads, relative volume)
- Clear semantic field names
- Logical groupings by function (indexes, sectors, ADRs, etc.)
- No pre-computed signals - data enables LLM judgment
"""

from datetime import datetime
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, computed_field


# =============================================================================
# BUILDING BLOCKS
# =============================================================================

class PriceData(BaseModel):
    """Price bar with derived intraday context."""
    last: float = Field(description="Last/closing price")
    change_pct: float = Field(description="1-day percentage change")
    open: Optional[float] = Field(default=None, description="Session open price")
    high: Optional[float] = Field(default=None, description="Session high")
    low: Optional[float] = Field(default=None, description="Session low")

    @computed_field
    @property
    def intraday_range_pct(self) -> Optional[float]:
        """Intraday range as percentage of open. High volatility = large value."""
        if self.open and self.high and self.low and self.open > 0:
            return round((self.high - self.low) / self.open * 100, 3)
        return None

    @computed_field
    @property
    def close_position_in_range(self) -> Optional[float]:
        """Where price closed in the day's range. 0=low, 1=high, 0.5=middle."""
        if self.high and self.low and self.high != self.low:
            return round((self.last - self.low) / (self.high - self.low), 3)
        return None


class VolumeData(BaseModel):
    """Volume with relative context for conviction signals."""
    volume: float = Field(description="Session volume")
    avg_20d: float = Field(description="20-day average volume")

    @computed_field
    @property
    def relative_volume(self) -> float:
        """Volume vs 20-day average. >1.5 = elevated, >2.0 = high conviction."""
        if self.avg_20d > 0:
            return round(self.volume / self.avg_20d, 2)
        return 0.0


# =============================================================================
# INDEX DATA
# =============================================================================

class IndexSnapshot(BaseModel):
    """Single index with full price context."""
    ticker: str
    name: str
    price: PriceData
    volume: Optional[float] = Field(default=None, description="Index volume (if available)")


class BreadthContext(BaseModel):
    """Market breadth signals derived from SPX vs SPW comparison.

    Interpretation:
    - spread > 0: Mega-cap led, narrow leadership
    - spread < 0: Broad participation, equal-weight outperforming
    - |spread| > 0.5: Significant divergence worth noting
    """
    spx_change_pct: float
    spw_change_pct: float
    spread: float = Field(description="SPX - SPW. Positive = narrow, Negative = broad")

    nasdaq_vs_spx: float = Field(description="NASDAQ - SPX. Positive = tech leading")
    russell_vs_spx: float = Field(description="Russell - SPX. Positive = small caps leading")


# =============================================================================
# SECTOR & INDUSTRY DATA
# =============================================================================

class SectorSnapshot(BaseModel):
    """Sector ETF with ranking and volume context."""
    ticker: str
    name: str
    change_pct: float
    rank: int = Field(description="Performance rank, 1 = best")
    total_sectors: int = Field(default=11, description="Total sectors for context")
    volume: Optional[VolumeData] = None

    @computed_field
    @property
    def is_leader(self) -> bool:
        """Top 3 performer."""
        return self.rank <= 3

    @computed_field
    @property
    def is_laggard(self) -> bool:
        """Bottom 3 performer."""
        return self.rank >= self.total_sectors - 2


class IndustrySnapshot(BaseModel):
    """Thematic industry ETF."""
    ticker: str
    name: str
    theme: str = Field(description="Theme category: precious_metals, semiconductors, etc.")
    change_pct: float
    volume: Optional[VolumeData] = None


# =============================================================================
# MACRO DATA
# =============================================================================

class MacroInstrument(BaseModel):
    """FX, rate, or commodity instrument."""
    ticker: str
    name: str
    last: float
    change_pct: float
    change_bps: Optional[float] = Field(default=None, description="Change in basis points (for rates)")
    open: Optional[float] = None

    @computed_field
    @property
    def direction(self) -> Literal["up", "down", "flat"]:
        """Simple direction indicator."""
        if self.change_pct > 0.1:
            return "up"
        elif self.change_pct < -0.1:
            return "down"
        return "flat"


class YieldCurve(BaseModel):
    """US and Japan yield context."""
    us_10y: float = Field(description="US 10Y yield level")
    us_2y: float = Field(description="US 2Y yield level")
    jp_10y: float = Field(description="Japan 10Y yield level")

    @computed_field
    @property
    def us_2s10s_spread(self) -> float:
        """US 10Y - 2Y spread. Positive = normal, Negative = inverted."""
        return round(self.us_10y - self.us_2y, 3)

    @computed_field
    @property
    def us_jp_spread(self) -> float:
        """US 10Y - JP 10Y spread. Rate differential."""
        return round(self.us_10y - self.jp_10y, 3)


class MacroSnapshot(BaseModel):
    """Complete macro environment snapshot."""
    # FX
    dxy: MacroInstrument
    usdjpy: MacroInstrument
    eurjpy: Optional[MacroInstrument] = None

    # Rates
    yields: YieldCurve
    us_10y_change_pct: float
    jp_10y_change_pct: float

    # Commodities
    wti: MacroInstrument
    brent: Optional[MacroInstrument] = None
    gold: MacroInstrument


# =============================================================================
# JAPAN-SPECIFIC DATA
# =============================================================================

class JapanProxySnapshot(BaseModel):
    """Nikkei/TOPIX/EWJ with divergence context."""
    nikkei_cash: IndexSnapshot = Field(description="Nikkei 225 cash index (prior JP close)")
    nikkei_futures: IndexSnapshot = Field(description="Nikkei futures (current)")
    topix: IndexSnapshot
    ewj: IndexSnapshot = Field(description="EWJ US-listed ETF")

    @computed_field
    @property
    def futures_implied_move_pct(self) -> float:
        """Futures implied move vs prior cash close."""
        if self.nikkei_cash.price.last > 0:
            return round(
                (self.nikkei_futures.price.last - self.nikkei_cash.price.last)
                / self.nikkei_cash.price.last * 100,
                2
            )
        return 0.0

    @computed_field
    @property
    def ewj_open_to_close_pct(self) -> Optional[float]:
        """EWJ intraday direction. Negative = sold off, Positive = bid into close."""
        if self.ewj.price.open and self.ewj.price.open > 0:
            return round(
                (self.ewj.price.last - self.ewj.price.open) / self.ewj.price.open * 100,
                2
            )
        return None

    @computed_field
    @property
    def futures_vs_ewj_divergence(self) -> float:
        """Futures change vs EWJ change. Large divergence = notable."""
        return round(
            self.nikkei_futures.price.change_pct - self.ewj.price.change_pct,
            2
        )


class ADRSnapshot(BaseModel):
    """Japan ADR with full context for read-through analysis."""
    adr_ticker: str
    jp_code: str
    name: str
    sector: str = Field(description="Sector: banks, autos, tech, semiconductors, etc.")

    # Price
    last: float
    change_pct: float
    open: Optional[float] = None
    prev_close: Optional[float] = None

    # Volume context
    volume: Optional[VolumeData] = None

    @computed_field
    @property
    def open_to_close_pct(self) -> Optional[float]:
        """Intraday direction. Negative = faded, Positive = strengthened."""
        if self.open and self.open > 0:
            return round((self.last - self.open) / self.open * 100, 2)
        return None

    @computed_field
    @property
    def gap_pct(self) -> Optional[float]:
        """Gap from previous close. Large gaps = overnight news."""
        if self.prev_close and self.prev_close > 0 and self.open:
            return round((self.open - self.prev_close) / self.prev_close * 100, 2)
        return None


class ADRSectorSummary(BaseModel):
    """Aggregated ADR data by sector for quick reference."""
    sector: str
    adrs: List[ADRSnapshot]

    @computed_field
    @property
    def avg_change_pct(self) -> float:
        """Average change across sector ADRs."""
        if not self.adrs:
            return 0.0
        return round(sum(a.change_pct for a in self.adrs) / len(self.adrs), 2)

    @computed_field
    @property
    def strongest_ticker(self) -> Optional[str]:
        """Best performing ADR in sector."""
        if not self.adrs:
            return None
        return max(self.adrs, key=lambda a: a.change_pct).adr_ticker

    @computed_field
    @property
    def weakest_ticker(self) -> Optional[str]:
        """Worst performing ADR in sector."""
        if not self.adrs:
            return None
        return min(self.adrs, key=lambda a: a.change_pct).adr_ticker

    @computed_field
    @property
    def highest_rvol_ticker(self) -> Optional[str]:
        """ADR with highest relative volume (conviction signal)."""
        adrs_with_vol = [a for a in self.adrs if a.volume and a.volume.relative_volume > 0]
        if not adrs_with_vol:
            return None
        return max(adrs_with_vol, key=lambda a: a.volume.relative_volume).adr_ticker


class JPEquitySnapshot(BaseModel):
    """Japan equity from watchlist."""
    ticker: str
    code: str = Field(description="Numeric code e.g. '8306'")
    name: str
    theme: str = Field(description="Theme: banks, autos, semiconductors, etc.")
    last: float
    change_pct: float = Field(description="Change from prior JP session")
    gics_sector: Optional[str] = None


# =============================================================================
# COMPLETE SNAPSHOTS
# =============================================================================

class USSessionSnapshot(BaseModel):
    """Complete US session data for morning note generation.

    Provides all data needed for "What Happened in U.S. Markets" section:
    - Index performance with breadth signals
    - Sector rankings with volume context
    - Industry/thematic ETF leadership
    - Macro (FX, rates, commodities)
    """
    as_of: datetime
    session_date: str = Field(description="Session date YYYY-MM-DD")

    # Indexes
    indexes: Dict[str, IndexSnapshot] = Field(
        description="Keyed by: spx, dow, nasdaq, russell, spw"
    )

    # Breadth analysis
    breadth: BreadthContext

    # Sectors sorted by performance (rank 1 = best)
    sectors: List[SectorSnapshot]

    # Industry ETFs grouped by theme
    industry_etfs: Dict[str, List[IndustrySnapshot]] = Field(
        description="Keyed by theme: precious_metals, semiconductors, etc."
    )

    # Macro
    macro: MacroSnapshot

    # Convenience accessors
    @computed_field
    @property
    def sector_leaders(self) -> List[SectorSnapshot]:
        """Top 3 sectors by performance."""
        return [s for s in self.sectors if s.rank <= 3]

    @computed_field
    @property
    def sector_laggards(self) -> List[SectorSnapshot]:
        """Bottom 3 sectors by performance."""
        return [s for s in self.sectors if s.rank >= len(self.sectors) - 2]

    @computed_field
    @property
    def industry_leaders(self) -> List[IndustrySnapshot]:
        """Top 5 industry ETFs by performance."""
        all_etfs = []
        for etfs in self.industry_etfs.values():
            all_etfs.extend(etfs)
        return sorted(all_etfs, key=lambda e: e.change_pct, reverse=True)[:5]

    @computed_field
    @property
    def industry_laggards(self) -> List[IndustrySnapshot]:
        """Bottom 5 industry ETFs by performance."""
        all_etfs = []
        for etfs in self.industry_etfs.values():
            all_etfs.extend(etfs)
        return sorted(all_etfs, key=lambda e: e.change_pct)[:5]


class JapanOvernightSnapshot(BaseModel):
    """Complete Japan-relevant data for morning note.

    Provides all data needed for Japan sections:
    - Nikkei futures vs cash (implied move)
    - EWJ intraday character
    - ADR performance by sector with RVOL
    - Japan equity watchlist
    """
    as_of: datetime

    # Proxies (Nikkei, TOPIX, EWJ)
    proxies: JapanProxySnapshot

    # ADRs grouped by sector
    adr_sectors: Dict[str, ADRSectorSummary] = Field(
        description="Keyed by sector: banks, autos, tech, semiconductors, etc."
    )

    # Japan equity watchlist
    watchlist: Dict[str, List[JPEquitySnapshot]] = Field(
        description="Keyed by theme: banks, autos, semiconductors, etc."
    )

    # Summary stats
    @computed_field
    @property
    def adrs_positive_count(self) -> int:
        """Number of ADRs with positive change."""
        count = 0
        for sector in self.adr_sectors.values():
            count += sum(1 for a in sector.adrs if a.change_pct > 0)
        return count

    @computed_field
    @property
    def adrs_negative_count(self) -> int:
        """Number of ADRs with negative change."""
        count = 0
        for sector in self.adr_sectors.values():
            count += sum(1 for a in sector.adrs if a.change_pct < 0)
        return count

    @computed_field
    @property
    def total_adrs(self) -> int:
        """Total ADRs tracked."""
        return sum(len(sector.adrs) for sector in self.adr_sectors.values())

    @computed_field
    @property
    def strongest_adr_sectors(self) -> List[str]:
        """Sectors with positive average change, sorted by strength."""
        positive = [(k, v.avg_change_pct) for k, v in self.adr_sectors.items() if v.avg_change_pct > 0]
        return [k for k, _ in sorted(positive, key=lambda x: x[1], reverse=True)]

    @computed_field
    @property
    def weakest_adr_sectors(self) -> List[str]:
        """Sectors with negative average change, sorted by weakness."""
        negative = [(k, v.avg_change_pct) for k, v in self.adr_sectors.items() if v.avg_change_pct < 0]
        return [k for k, _ in sorted(negative, key=lambda x: x[1])]

    @computed_field
    @property
    def high_rvol_adrs(self) -> List[str]:
        """ADRs with relative volume > 1.5 (elevated conviction)."""
        high_vol = []
        for sector in self.adr_sectors.values():
            for adr in sector.adrs:
                if adr.volume and adr.volume.relative_volume > 1.5:
                    high_vol.append(f"{adr.adr_ticker} ({adr.volume.relative_volume:.1f}x)")
        return high_vol
