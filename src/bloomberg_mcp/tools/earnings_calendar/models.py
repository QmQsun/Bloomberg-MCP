"""Models for Earnings Calendar tool.

Defines data structures, named universes, and field mappings for
earnings calendar queries in the morning note context.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class EarningsMode(str, Enum):
    """Earnings calendar query mode."""
    OVERNIGHT = "overnight"      # What reported in last 24h (for morning note)
    TODAY = "today"              # Reports today
    WEEK_AHEAD = "week_ahead"    # Next 7 days
    CUSTOM = "custom"            # Custom date range


class ReportTiming(str, Enum):
    """When the company typically reports."""
    BEFORE_MARKET = "BMO"        # Before market open
    AFTER_MARKET = "AMC"         # After market close
    DURING_MARKET = "DMH"        # During market hours
    UNKNOWN = "UNK"


# =============================================================================
# NAMED UNIVERSES FOR EARNINGS
# =============================================================================
# These universes are designed for morning note relevance to Japan trading

EARNINGS_UNIVERSES: Dict[str, List[str]] = {
    # Mega-cap tech that moves global sentiment
    "MEGA_CAP_TECH": [
        "AAPL US Equity",   # Apple
        "MSFT US Equity",   # Microsoft
        "GOOGL US Equity",  # Alphabet
        "AMZN US Equity",   # Amazon
        "META US Equity",   # Meta
        "NVDA US Equity",   # NVIDIA
        "TSLA US Equity",   # Tesla
    ],

    # Semiconductor leaders - direct read-through to Japan semis
    "SEMI_LEADERS": [
        "NVDA US Equity",   # NVIDIA - AI bellwether
        "AMD US Equity",    # AMD - CPU/GPU
        "INTC US Equity",   # Intel
        "TSM US Equity",    # TSMC ADR - foundry leader
        "ASML US Equity",   # ASML - litho monopoly
        "AMAT US Equity",   # Applied Materials
        "LRCX US Equity",   # Lam Research
        "KLAC US Equity",   # KLA Corp
        "MU US Equity",     # Micron - memory
        "MRVL US Equity",   # Marvell
        "AVGO US Equity",   # Broadcom
        "QCOM US Equity",   # Qualcomm
        "TXN US Equity",    # Texas Instruments
        "ADI US Equity",    # Analog Devices
    ],

    # Japan ADRs - direct impact on Tokyo
    "JAPAN_ADRS": [
        "TM US Equity",     # Toyota
        "HMC US Equity",    # Honda
        "SONY US Equity",   # Sony
        "MUFG US Equity",   # Mitsubishi UFJ
        "SMFG US Equity",   # Sumitomo Mitsui
        "NMR US Equity",    # Nomura
        "NTDOY US Equity",  # Nintendo
        "SNE US Equity",    # Sony (alt)
    ],

    # Financials - read-through to Japan banks
    "US_FINANCIALS": [
        "JPM US Equity",    # JPMorgan
        "BAC US Equity",    # Bank of America
        "GS US Equity",     # Goldman Sachs
        "MS US Equity",     # Morgan Stanley
        "C US Equity",      # Citigroup
        "WFC US Equity",    # Wells Fargo
    ],

    # Consumer/Retail - sentiment indicators
    "CONSUMER": [
        "WMT US Equity",    # Walmart
        "COST US Equity",   # Costco
        "TGT US Equity",    # Target
        "HD US Equity",     # Home Depot
        "NKE US Equity",    # Nike
        "SBUX US Equity",   # Starbucks
        "MCD US Equity",    # McDonald's
    ],

    # Industrials - capex/trade indicators
    "INDUSTRIALS": [
        "CAT US Equity",    # Caterpillar
        "DE US Equity",     # Deere
        "BA US Equity",     # Boeing
        "UNP US Equity",    # Union Pacific
        "UPS US Equity",    # UPS
        "FDX US Equity",    # FedEx
        "GE US Equity",     # GE Aerospace
        "HON US Equity",    # Honeywell
    ],

    # Combined universe for morning note context
    "MORNING_NOTE": [
        # Top-tier market movers
        "AAPL US Equity", "MSFT US Equity", "NVDA US Equity", "GOOGL US Equity",
        "AMZN US Equity", "META US Equity", "TSLA US Equity",
        # Semi leaders (Japan read-through)
        "AMD US Equity", "TSM US Equity", "ASML US Equity", "AMAT US Equity",
        "LRCX US Equity", "MU US Equity", "AVGO US Equity",
        # Japan ADRs
        "TM US Equity", "SONY US Equity", "MUFG US Equity",
        # Financials
        "JPM US Equity", "GS US Equity",
        # Bellwethers
        "CAT US Equity", "FDX US Equity",
    ],
}


# =============================================================================
# BLOOMBERG FIELDS FOR EARNINGS
# =============================================================================

EARNINGS_FIELDS = [
    "EXPECTED_REPORT_DT",       # Next expected report date
    "ANNOUNCEMENT_DT",          # Last announcement date (most recent report)
    "BEST_EPS",                 # Consensus EPS estimate
    "BEST_EPS_GAAP",            # GAAP EPS estimate
    "TRAIL_12M_EPS",            # Trailing 12M EPS
    "BEST_SALES",               # Consensus revenue estimate
    "EPS_GROWTH",               # EPS growth estimate %
    "SALES_GROWTH",             # Revenue growth estimate %
    "BEST_ANALYST_RATING",      # Analyst rating (1=sell, 5=buy)
    "TOT_ANALYST_REC",          # Number of analysts
    "BEST_TARGET_PRICE",        # Consensus price target
    "PX_LAST",                  # Current price
    "CHG_PCT_1D",               # 1-day change (for recently reported)
]

# Minimal fields for faster queries
EARNINGS_FIELDS_MINIMAL = [
    "EXPECTED_REPORT_DT",
    "ANNOUNCEMENT_DT",
    "BEST_EPS",
    "PX_LAST",
    "CHG_PCT_1D",
]


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class EarningsEvent:
    """A single earnings event."""
    ticker: str
    name: str
    report_date: date
    is_confirmed: bool              # True if date confirmed, False if estimated
    timing: ReportTiming            # BMO, AMC, DMH, UNK
    last_reported: Optional[date]   # When they last reported

    # Estimates
    eps_estimate: Optional[float] = None
    eps_growth: Optional[float] = None
    sales_estimate: Optional[float] = None  # In millions

    # Analyst context
    analyst_rating: Optional[float] = None  # 1-5 scale
    num_analysts: Optional[int] = None
    target_price: Optional[float] = None

    # Current state
    current_price: Optional[float] = None
    change_1d: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ticker": self.ticker,
            "name": self.name,
            "report_date": self.report_date.isoformat(),
            "is_confirmed": self.is_confirmed,
            "timing": self.timing.value,
            "last_reported": self.last_reported.isoformat() if self.last_reported else None,
            "eps_estimate": self.eps_estimate,
            "eps_growth": self.eps_growth,
            "sales_estimate_mm": self.sales_estimate,
            "analyst_rating": self.analyst_rating,
            "num_analysts": self.num_analysts,
            "target_price": self.target_price,
            "current_price": self.current_price,
            "change_1d_pct": self.change_1d,
        }

    def to_markdown_row(self) -> str:
        """Format as markdown table row."""
        date_str = self.report_date.strftime("%a %b %d")
        eps = f"${self.eps_estimate:.2f}" if self.eps_estimate else "-"
        growth = f"{self.eps_growth:+.1f}%" if self.eps_growth else "-"
        chg = f"{self.change_1d:+.2f}%" if self.change_1d else "-"
        return f"| {date_str} | {self.timing.value} | {self.ticker} | {eps} | {growth} | {chg} |"


@dataclass
class EarningsCalendarOutput:
    """Output from earnings calendar query."""
    mode: str
    query_date: date
    universe_name: str
    universe_size: int

    # Events grouped by timing relevance
    reported_recently: List[EarningsEvent] = field(default_factory=list)
    reports_today: List[EarningsEvent] = field(default_factory=list)
    reports_this_week: List[EarningsEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode,
            "query_date": self.query_date.isoformat(),
            "universe": self.universe_name,
            "universe_size": self.universe_size,
            "summary": {
                "reported_recently": len(self.reported_recently),
                "reports_today": len(self.reports_today),
                "reports_this_week": len(self.reports_this_week),
            },
            "reported_recently": [e.to_dict() for e in self.reported_recently],
            "reports_today": [e.to_dict() for e in self.reports_today],
            "reports_this_week": [e.to_dict() for e in self.reports_this_week],
        }

    def to_markdown(self) -> str:
        """Format as markdown for morning note."""
        lines = [
            f"## Earnings Calendar",
            f"**Universe**: {self.universe_name} ({self.universe_size} securities)",
            "",
        ]

        # Recently reported (what moved overnight)
        if self.reported_recently:
            lines.append("### Reported Recently")
            lines.append("| Date | Time | Ticker | EPS Est | Growth | Move |")
            lines.append("|------|------|--------|---------|--------|------|")
            for event in self.reported_recently:
                lines.append(event.to_markdown_row())
            lines.append("")

        # Reports today
        if self.reports_today:
            lines.append("### Reports Today")
            lines.append("| Date | Time | Ticker | EPS Est | Growth | Move |")
            lines.append("|------|------|--------|---------|--------|------|")
            for event in self.reports_today:
                lines.append(event.to_markdown_row())
            lines.append("")

        # Week ahead
        if self.reports_this_week:
            lines.append("### Upcoming This Week")
            lines.append("| Date | Time | Ticker | EPS Est | Growth | Move |")
            lines.append("|------|------|--------|---------|--------|------|")
            for event in self.reports_this_week:
                lines.append(event.to_markdown_row())
            lines.append("")

        if not (self.reported_recently or self.reports_today or self.reports_this_week):
            lines.append("No earnings events in the selected period.")

        return "\n".join(lines)


class EarningsCalendarInput(BaseModel):
    """Input parameters for earnings calendar query."""

    mode: EarningsMode = Field(
        default=EarningsMode.WEEK_AHEAD,
        description="Query mode: overnight (last 24h), today, week_ahead (7 days)"
    )

    universe: Union[str, List[str]] = Field(
        default="MORNING_NOTE",
        description="""
Universe to query. Either:
- Named universe: "MORNING_NOTE", "SEMI_LEADERS", "MEGA_CAP_TECH", "JAPAN_ADRS"
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

    response_format: str = Field(
        default="markdown",
        description="Output format: json or markdown"
    )


def resolve_universe(universe: Union[str, List[str]]) -> tuple[str, List[str]]:
    """
    Resolve universe input to name and list of securities.

    Returns:
        Tuple of (universe_name, list of securities)
    """
    if isinstance(universe, list):
        return ("Custom", universe)

    universe_upper = universe.upper().replace("-", "_").replace(" ", "_")

    if universe_upper in EARNINGS_UNIVERSES:
        return (universe_upper, EARNINGS_UNIVERSES[universe_upper])

    # Try partial match
    for name, securities in EARNINGS_UNIVERSES.items():
        if universe_upper in name or name in universe_upper:
            return (name, securities)

    # Assume it's a single security
    return ("Single", [universe])


__all__ = [
    "EarningsMode",
    "ReportTiming",
    "EarningsEvent",
    "EarningsCalendarOutput",
    "EarningsCalendarInput",
    "EARNINGS_UNIVERSES",
    "EARNINGS_FIELDS",
    "EARNINGS_FIELDS_MINIMAL",
    "resolve_universe",
]
