"""Models for Economic Calendar tool.

Defines data structures and the indicator registry mapping Bloomberg tickers
to metadata for morning note generation.
"""

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CalendarMode(str, Enum):
    """Calendar query mode."""
    WEEK_AHEAD = "week_ahead"      # Next 7 days
    TODAY = "today"                 # Today only
    RECENT = "recent"               # Last 24h releases
    CENTRAL_BANK = "central_bank"   # Central bank decisions only (30 days)
    CUSTOM = "custom"               # Custom date range


class EventCategory(str, Enum):
    """Economic event categories."""
    CENTRAL_BANK = "central_bank"
    INFLATION = "inflation"
    EMPLOYMENT = "employment"
    GROWTH = "growth"
    TRADE = "trade"
    HOUSING = "housing"
    MANUFACTURING = "manufacturing"
    CONSUMER = "consumer"


class EventImportance(str, Enum):
    """Event importance for filtering."""
    HIGH = "high"       # Market-moving (NFP, CPI, Fed, BoJ)
    MEDIUM = "medium"   # Notable (PMI, Retail Sales)
    LOW = "low"         # Minor
    ALL = "all"         # No filter


@dataclass
class IndicatorMetadata:
    """Metadata for an economic indicator."""
    ticker: str
    name: str
    short_name: str
    region: str
    category: EventCategory
    importance: EventImportance
    unit: str = ""
    description: str = ""


# =============================================================================
# INDICATOR REGISTRY
# =============================================================================
# Comprehensive mapping of Bloomberg tickers to metadata for economic calendar

INDICATOR_REGISTRY: Dict[str, IndicatorMetadata] = {
    # =========================================================================
    # US INDICATORS
    # =========================================================================

    # Central Bank
    "FDTR Index": IndicatorMetadata(
        ticker="FDTR Index",
        name="Federal Reserve Fed Funds Target Rate",
        short_name="FOMC Decision",
        region="US",
        category=EventCategory.CENTRAL_BANK,
        importance=EventImportance.HIGH,
        unit="%",
        description="Federal Reserve interest rate decision"
    ),

    # Inflation
    "CPI YOY Index": IndicatorMetadata(
        ticker="CPI YOY Index",
        name="US CPI Year-over-Year",
        short_name="US CPI YoY",
        region="US",
        category=EventCategory.INFLATION,
        importance=EventImportance.HIGH,
        unit="%",
        description="Consumer Price Index annual change"
    ),
    "CPI XYOY Index": IndicatorMetadata(
        ticker="CPI XYOY Index",
        name="US Core CPI Year-over-Year",
        short_name="US Core CPI",
        region="US",
        category=EventCategory.INFLATION,
        importance=EventImportance.HIGH,
        unit="%",
        description="Core CPI (ex food & energy) annual change"
    ),
    "PCE CYOY Index": IndicatorMetadata(
        ticker="PCE CYOY Index",
        name="US PCE Core Deflator Year-over-Year",
        short_name="Core PCE",
        region="US",
        category=EventCategory.INFLATION,
        importance=EventImportance.HIGH,
        unit="%",
        description="Fed's preferred inflation measure"
    ),
    "PPI YOY Index": IndicatorMetadata(
        ticker="PPI YOY Index",
        name="US PPI Year-over-Year",
        short_name="US PPI",
        region="US",
        category=EventCategory.INFLATION,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="Producer Price Index annual change"
    ),

    # Employment
    "NFP TCH Index": IndicatorMetadata(
        ticker="NFP TCH Index",
        name="US Nonfarm Payrolls Change",
        short_name="NFP",
        region="US",
        category=EventCategory.EMPLOYMENT,
        importance=EventImportance.HIGH,
        unit="k",
        description="Monthly change in nonfarm employment"
    ),
    "USURTOT Index": IndicatorMetadata(
        ticker="USURTOT Index",
        name="US Unemployment Rate",
        short_name="US Unemployment",
        region="US",
        category=EventCategory.EMPLOYMENT,
        importance=EventImportance.HIGH,
        unit="%",
        description="US unemployment rate"
    ),
    "INJCJC Index": IndicatorMetadata(
        ticker="INJCJC Index",
        name="US Initial Jobless Claims",
        short_name="Jobless Claims",
        region="US",
        category=EventCategory.EMPLOYMENT,
        importance=EventImportance.MEDIUM,
        unit="k",
        description="Weekly initial unemployment claims"
    ),
    "ADP CHNG Index": IndicatorMetadata(
        ticker="ADP CHNG Index",
        name="ADP Employment Change",
        short_name="ADP Employment",
        region="US",
        category=EventCategory.EMPLOYMENT,
        importance=EventImportance.MEDIUM,
        unit="k",
        description="Private sector employment change"
    ),

    # Growth
    "GDP CQOQ Index": IndicatorMetadata(
        ticker="GDP CQOQ Index",
        name="US GDP Quarter-over-Quarter Annualized",
        short_name="US GDP",
        region="US",
        category=EventCategory.GROWTH,
        importance=EventImportance.HIGH,
        unit="%",
        description="US GDP quarterly growth annualized"
    ),
    "RSTAMOM Index": IndicatorMetadata(
        ticker="RSTAMOM Index",
        name="US Retail Sales Month-over-Month",
        short_name="Retail Sales",
        region="US",
        category=EventCategory.CONSUMER,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="Monthly retail sales change"
    ),
    "NAPMPMI Index": IndicatorMetadata(
        ticker="NAPMPMI Index",
        name="ISM Manufacturing PMI",
        short_name="ISM Mfg PMI",
        region="US",
        category=EventCategory.MANUFACTURING,
        importance=EventImportance.HIGH,
        unit="",
        description="Institute for Supply Management manufacturing index"
    ),
    "NAPMNMI Index": IndicatorMetadata(
        ticker="NAPMNMI Index",
        name="ISM Services PMI",
        short_name="ISM Services",
        region="US",
        category=EventCategory.MANUFACTURING,
        importance=EventImportance.MEDIUM,
        unit="",
        description="ISM non-manufacturing (services) index"
    ),
    "CONSSENT Index": IndicatorMetadata(
        ticker="CONSSENT Index",
        name="University of Michigan Consumer Sentiment",
        short_name="UMich Sentiment",
        region="US",
        category=EventCategory.CONSUMER,
        importance=EventImportance.MEDIUM,
        unit="",
        description="Consumer confidence survey"
    ),

    # Trade
    "USTBTOT Index": IndicatorMetadata(
        ticker="USTBTOT Index",
        name="US Trade Balance",
        short_name="US Trade Bal",
        region="US",
        category=EventCategory.TRADE,
        importance=EventImportance.MEDIUM,
        unit="$B",
        description="US trade balance"
    ),

    # =========================================================================
    # JAPAN INDICATORS
    # =========================================================================

    # Central Bank
    "BOJDPBAL Index": IndicatorMetadata(
        ticker="BOJDPBAL Index",
        name="Bank of Japan Policy Balance Rate",
        short_name="BoJ Decision",
        region="Japan",
        category=EventCategory.CENTRAL_BANK,
        importance=EventImportance.HIGH,
        unit="%",
        description="Bank of Japan interest rate decision"
    ),

    # Inflation
    "JNCPIYOY Index": IndicatorMetadata(
        ticker="JNCPIYOY Index",
        name="Japan CPI Year-over-Year",
        short_name="Japan CPI",
        region="Japan",
        category=EventCategory.INFLATION,
        importance=EventImportance.HIGH,
        unit="%",
        description="Japan national CPI annual change"
    ),
    "JNCPXYOY Index": IndicatorMetadata(
        ticker="JNCPXYOY Index",
        name="Japan Core CPI Year-over-Year",
        short_name="Japan Core CPI",
        region="Japan",
        category=EventCategory.INFLATION,
        importance=EventImportance.HIGH,
        unit="%",
        description="Japan core CPI (ex fresh food)"
    ),

    # Employment
    "JNUE Index": IndicatorMetadata(
        ticker="JNUE Index",
        name="Japan Unemployment Rate",
        short_name="Japan Unemp",
        region="Japan",
        category=EventCategory.EMPLOYMENT,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="Japan unemployment rate"
    ),

    # Growth
    "JGDPAGDP Index": IndicatorMetadata(
        ticker="JGDPAGDP Index",
        name="Japan GDP Quarter-over-Quarter Annualized",
        short_name="Japan GDP",
        region="Japan",
        category=EventCategory.GROWTH,
        importance=EventImportance.HIGH,
        unit="%",
        description="Japan GDP quarterly growth annualized"
    ),
    "JNTSMFG Index": IndicatorMetadata(
        ticker="JNTSMFG Index",
        name="Japan Tankan Large Manufacturers Index",
        short_name="Tankan Mfg",
        region="Japan",
        category=EventCategory.MANUFACTURING,
        importance=EventImportance.HIGH,
        unit="",
        description="Bank of Japan Tankan survey - large manufacturers"
    ),
    "JNTSNMFG Index": IndicatorMetadata(
        ticker="JNTSNMFG Index",
        name="Japan Tankan Large Non-Manufacturers Index",
        short_name="Tankan Non-Mfg",
        region="Japan",
        category=EventCategory.MANUFACTURING,
        importance=EventImportance.MEDIUM,
        unit="",
        description="Bank of Japan Tankan survey - large non-manufacturers"
    ),
    "MPMIJPMA Index": IndicatorMetadata(
        ticker="MPMIJPMA Index",
        name="Japan Manufacturing PMI",
        short_name="Japan PMI Mfg",
        region="Japan",
        category=EventCategory.MANUFACTURING,
        importance=EventImportance.MEDIUM,
        unit="",
        description="Jibun Bank Japan Manufacturing PMI"
    ),

    # Trade
    "JNBPFTB Index": IndicatorMetadata(
        ticker="JNBPFTB Index",
        name="Japan Trade Balance",
        short_name="Japan Trade Bal",
        region="Japan",
        category=EventCategory.TRADE,
        importance=EventImportance.MEDIUM,
        unit="¥B",
        description="Japan merchandise trade balance"
    ),
    "JNTBEXPY Index": IndicatorMetadata(
        ticker="JNTBEXPY Index",
        name="Japan Exports Year-over-Year",
        short_name="Japan Exports",
        region="Japan",
        category=EventCategory.TRADE,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="Japan exports annual change"
    ),

    # =========================================================================
    # EUROPE INDICATORS
    # =========================================================================

    # Central Bank
    "EURR002W Index": IndicatorMetadata(
        ticker="EURR002W Index",
        name="ECB Main Refinancing Rate",
        short_name="ECB Decision",
        region="Europe",
        category=EventCategory.CENTRAL_BANK,
        importance=EventImportance.HIGH,
        unit="%",
        description="European Central Bank main rate"
    ),
    "UKBRBASE Index": IndicatorMetadata(
        ticker="UKBRBASE Index",
        name="Bank of England Bank Rate",
        short_name="BoE Decision",
        region="Europe",
        category=EventCategory.CENTRAL_BANK,
        importance=EventImportance.HIGH,
        unit="%",
        description="Bank of England interest rate"
    ),

    # Inflation
    "ECCPEMUY Index": IndicatorMetadata(
        ticker="ECCPEMUY Index",
        name="Eurozone CPI Year-over-Year",
        short_name="EZ CPI",
        region="Europe",
        category=EventCategory.INFLATION,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="Eurozone harmonized CPI"
    ),
    "UKRPCJYR Index": IndicatorMetadata(
        ticker="UKRPCJYR Index",
        name="UK CPI Year-over-Year",
        short_name="UK CPI",
        region="Europe",
        category=EventCategory.INFLATION,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="UK consumer price index annual change"
    ),

    # Growth
    "EUGNEMUQ Index": IndicatorMetadata(
        ticker="EUGNEMUQ Index",
        name="Eurozone GDP Quarter-over-Quarter",
        short_name="EZ GDP",
        region="Europe",
        category=EventCategory.GROWTH,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="Eurozone GDP quarterly growth"
    ),
    "MPMIEZMA Index": IndicatorMetadata(
        ticker="MPMIEZMA Index",
        name="Eurozone Manufacturing PMI",
        short_name="EZ PMI Mfg",
        region="Europe",
        category=EventCategory.MANUFACTURING,
        importance=EventImportance.MEDIUM,
        unit="",
        description="S&P Global Eurozone Manufacturing PMI"
    ),

    # =========================================================================
    # CHINA INDICATORS
    # =========================================================================

    # Central Bank
    "CHLR1Y Index": IndicatorMetadata(
        ticker="CHLR1Y Index",
        name="China 1-Year Loan Prime Rate",
        short_name="China LPR",
        region="China",
        category=EventCategory.CENTRAL_BANK,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="PBoC loan prime rate"
    ),

    # Inflation
    "CNCPIYOY Index": IndicatorMetadata(
        ticker="CNCPIYOY Index",
        name="China CPI Year-over-Year",
        short_name="China CPI",
        region="China",
        category=EventCategory.INFLATION,
        importance=EventImportance.MEDIUM,
        unit="%",
        description="China consumer price index annual change"
    ),

    # Growth
    "CNGDPYOY Index": IndicatorMetadata(
        ticker="CNGDPYOY Index",
        name="China GDP Year-over-Year",
        short_name="China GDP",
        region="China",
        category=EventCategory.GROWTH,
        importance=EventImportance.HIGH,
        unit="%",
        description="China GDP annual growth"
    ),
    "MPMICNMA Index": IndicatorMetadata(
        ticker="MPMICNMA Index",
        name="China Caixin Manufacturing PMI",
        short_name="China PMI Mfg",
        region="China",
        category=EventCategory.MANUFACTURING,
        importance=EventImportance.MEDIUM,
        unit="",
        description="Caixin China Manufacturing PMI"
    ),

    # Trade
    "CNFRBAL$ Index": IndicatorMetadata(
        ticker="CNFRBAL$ Index",
        name="China Trade Balance USD",
        short_name="China Trade Bal",
        region="China",
        category=EventCategory.TRADE,
        importance=EventImportance.MEDIUM,
        unit="$B",
        description="China trade balance in USD"
    ),
}


# =============================================================================
# INPUT/OUTPUT MODELS
# =============================================================================

class EconomicCalendarInput(BaseModel):
    """Input parameters for economic calendar query."""

    mode: CalendarMode = Field(
        default=CalendarMode.WEEK_AHEAD,
        description="Query mode: week_ahead (7 days), today, recent (24h releases), central_bank (30 days)"
    )

    regions: List[str] = Field(
        default=["US", "Japan"],
        description="Regions to include: US, Japan, Europe, China"
    )

    categories: Optional[List[str]] = Field(
        default=None,
        description="Event categories to filter. None = all. Options: central_bank, inflation, employment, growth, trade, manufacturing"
    )

    importance: EventImportance = Field(
        default=EventImportance.HIGH,
        description="Minimum importance level: high, medium, low, all"
    )

    days_ahead: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days ahead to look (for week_ahead mode)"
    )

    response_format: str = Field(
        default="json",
        description="Output format: json or markdown"
    )


@dataclass
class EconomicEvent:
    """A single economic calendar event."""
    ticker: str
    name: str
    short_name: str
    region: str
    category: str
    importance: str
    release_date: date
    release_time: Optional[str]  # "08:30 ET" format
    observation_period: Optional[str]  # "Dec", "4Q", etc.
    prior_value: Optional[float]
    unit: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ticker": self.ticker,
            "name": self.name,
            "short_name": self.short_name,
            "region": self.region,
            "category": self.category,
            "importance": self.importance,
            "release_date": self.release_date.isoformat(),
            "release_time": self.release_time,
            "observation_period": self.observation_period,
            "prior_value": self.prior_value,
            "unit": self.unit,
        }

    def to_markdown_row(self) -> str:
        """Format as markdown table row."""
        date_str = self.release_date.strftime("%a %b %d")
        time_str = self.release_time or "TBD"
        prior = f"{self.prior_value:.2f}{self.unit}" if self.prior_value is not None else "N/A"
        period = self.observation_period or ""
        return f"| {date_str} | {time_str} | {self.short_name} | {self.region} | {period} | {prior} |"


@dataclass
class EconomicCalendarOutput:
    """Output from economic calendar query."""
    mode: str
    query_date: date
    date_range_start: date
    date_range_end: date
    total_events: int
    events: List[EconomicEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode,
            "query_date": self.query_date.isoformat(),
            "date_range": {
                "start": self.date_range_start.isoformat(),
                "end": self.date_range_end.isoformat(),
            },
            "total_events": self.total_events,
            "events": [e.to_dict() for e in self.events],
        }

    def to_markdown(self) -> str:
        """Format as markdown for morning note."""
        lines = [
            f"## Economic Calendar ({self.mode})",
            f"**Period:** {self.date_range_start.strftime('%b %d')} - {self.date_range_end.strftime('%b %d, %Y')}",
            "",
            "| Date | Time | Event | Region | Period | Prior |",
            "|------|------|-------|--------|--------|-------|",
        ]

        for event in self.events:
            lines.append(event.to_markdown_row())

        if not self.events:
            lines.append("| - | - | No events scheduled | - | - | - |")

        return "\n".join(lines)


# Helper to get indicators by filter
def get_indicators_by_filter(
    regions: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    importance: EventImportance = EventImportance.ALL,
) -> List[IndicatorMetadata]:
    """Get indicators matching filter criteria."""
    result = []

    for ticker, meta in INDICATOR_REGISTRY.items():
        # Region filter
        if regions and meta.region not in regions:
            continue

        # Category filter
        if categories and meta.category.value not in categories:
            continue

        # Importance filter
        if importance != EventImportance.ALL:
            importance_order = {"high": 3, "medium": 2, "low": 1}
            if importance_order.get(meta.importance.value, 0) < importance_order.get(importance.value, 0):
                continue

        result.append(meta)

    return result


__all__ = [
    "CalendarMode",
    "EventCategory",
    "EventImportance",
    "IndicatorMetadata",
    "EconomicEvent",
    "EconomicCalendarInput",
    "EconomicCalendarOutput",
    "INDICATOR_REGISTRY",
    "get_indicators_by_filter",
]
