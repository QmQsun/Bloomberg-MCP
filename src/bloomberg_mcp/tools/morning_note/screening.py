"""Morning Note Dynamic Screening Integration.

Provides pre-configured screening workflows for morning note generation,
using the dynamic_screening toolset for hypothesis-driven analysis.

This module bridges the gap between raw Bloomberg data and actionable
morning note content by:
1. Running targeted screens to identify key movers
2. Collecting evidence for market themes
3. Generating signal reports for the LLM analyzer

Example usage in morning note pipeline:
    >>> from bloomberg_mcp.tools.morning_note.screening import (
    ...     run_morning_screens,
    ...     get_adr_signals,
    ...     get_volume_leaders,
    ... )
    >>>
    >>> # Run all screens in parallel-safe sequence
    >>> signals = run_morning_screens()
    >>>
    >>> # Or run individual screens
    >>> rvol_signals = get_adr_signals()
    >>> volume_leaders = get_volume_leaders()
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..dynamic_screening import (
    DynamicScreen,
    FieldSets,
    F,
    MorningNoteScreens,
    ScreenResult,
    SecurityRecord,
    SignalReport,
    SignalType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MORNING NOTE SIGNAL TYPES
# =============================================================================

@dataclass
class MorningNoteSignals:
    """Container for all morning note screening signals.

    Groups signals by category for structured LLM consumption.
    """

    # High conviction signals
    rvol_leaders: List[SecurityRecord] = field(default_factory=list)
    momentum_leaders: List[SecurityRecord] = field(default_factory=list)
    momentum_laggards: List[SecurityRecord] = field(default_factory=list)

    # Sentiment signals
    positive_sentiment: List[SecurityRecord] = field(default_factory=list)
    negative_sentiment: List[SecurityRecord] = field(default_factory=list)
    sentiment_divergence: List[SecurityRecord] = field(default_factory=list)

    # Volume signals
    volume_breakouts: List[SecurityRecord] = field(default_factory=list)

    # Sector aggregations
    sector_performance: Dict[str, float] = field(default_factory=dict)

    # Signal reports for hypothesis validation
    signal_reports: List[SignalReport] = field(default_factory=list)

    # Metadata
    universe_size: int = 0
    execution_time_ms: float = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rvol_leaders": [
                {"security": r.security, "rvol": r.rvol, "change_pct": r.change_pct}
                for r in self.rvol_leaders
            ],
            "momentum_leaders": [
                {"security": r.security, "change_pct": r.change_pct}
                for r in self.momentum_leaders
            ],
            "momentum_laggards": [
                {"security": r.security, "change_pct": r.change_pct}
                for r in self.momentum_laggards
            ],
            "positive_sentiment": [
                {"security": r.security, "sentiment": r.get("NEWS_SENTIMENT")}
                for r in self.positive_sentiment
            ],
            "negative_sentiment": [
                {"security": r.security, "sentiment": r.get("NEWS_SENTIMENT")}
                for r in self.negative_sentiment
            ],
            "volume_breakouts": [
                {"security": r.security, "rvol": r.rvol, "change_pct": r.change_pct}
                for r in self.volume_breakouts
            ],
            "sector_performance": self.sector_performance,
            "signal_reports": [s.to_dict() for s in self.signal_reports],
            "universe_size": self.universe_size,
            "execution_time_ms": self.execution_time_ms,
            "errors": self.errors,
        }


# =============================================================================
# CORE SCREENING FUNCTIONS
# =============================================================================

def run_morning_screens(
    rvol_threshold: float = 1.5,
    momentum_top_n: int = 5,
) -> MorningNoteSignals:
    """Run all morning note screens and aggregate results.

    This is the main entry point for morning note screening.
    Screens are run sequentially to avoid Bloomberg API thread-safety issues.

    Args:
        rvol_threshold: Minimum relative volume for RVOL leaders
        momentum_top_n: Number of momentum leaders/laggards to return

    Returns:
        MorningNoteSignals with all screen results

    Example:
        >>> signals = run_morning_screens()
        >>> print(f"Found {len(signals.rvol_leaders)} high RVOL ADRs")
    """
    import time
    start_time = time.time()

    signals = MorningNoteSignals()

    # 1. RVOL Leaders
    try:
        result = (
            DynamicScreen("RVOL Leaders")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.RVOL + FieldSets.MOMENTUM + FieldSets.SENTIMENT)
            .filter(F.rvol > rvol_threshold)
            .rank_by("rvol", descending=True)
            .top(10)
            .run()
        )
        signals.rvol_leaders = result.records
        signals.universe_size = result.universe_size
    except Exception as e:
        logger.error(f"RVOL Leaders screen failed: {e}")
        signals.errors.append(f"RVOL Leaders: {e}")

    # 2. Momentum Leaders
    try:
        result = MorningNoteScreens.momentum_leaders().run()
        signals.momentum_leaders = result.records[:momentum_top_n]
    except Exception as e:
        logger.error(f"Momentum Leaders screen failed: {e}")
        signals.errors.append(f"Momentum Leaders: {e}")

    # 3. Momentum Laggards
    try:
        result = MorningNoteScreens.momentum_laggards().run()
        signals.momentum_laggards = result.records[:momentum_top_n]
    except Exception as e:
        logger.error(f"Momentum Laggards screen failed: {e}")
        signals.errors.append(f"Momentum Laggards: {e}")

    # 4. Positive Sentiment
    try:
        result = MorningNoteScreens.sentiment_positive().run()
        signals.positive_sentiment = result.records
    except Exception as e:
        logger.error(f"Positive Sentiment screen failed: {e}")
        signals.errors.append(f"Positive Sentiment: {e}")

    # 5. Volume Breakouts
    try:
        result = MorningNoteScreens.volume_breakout().run()
        signals.volume_breakouts = result.records
    except Exception as e:
        logger.error(f"Volume Breakout screen failed: {e}")
        signals.errors.append(f"Volume Breakout: {e}")

    # 6. Sector Performance Aggregation
    try:
        signals.sector_performance = calculate_sector_performance()
    except Exception as e:
        logger.error(f"Sector Performance calculation failed: {e}")
        signals.errors.append(f"Sector Performance: {e}")

    signals.execution_time_ms = (time.time() - start_time) * 1000
    logger.info(f"Morning screens completed in {signals.execution_time_ms:.0f}ms")

    return signals


def get_adr_signals(
    rvol_threshold: float = 2.0,
    top_n: int = 10,
) -> ScreenResult:
    """Get high RVOL ADR signals for morning note.

    Focuses on ADRs with elevated volume that may indicate overnight catalysts.

    Args:
        rvol_threshold: Minimum relative volume
        top_n: Number of top results to return

    Returns:
        ScreenResult with high RVOL ADRs
    """
    return (
        DynamicScreen("ADR Signals")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.ADR + FieldSets.RVOL + FieldSets.MOMENTUM + FieldSets.SENTIMENT)
        .filter(F.rvol > rvol_threshold)
        .rank_by("rvol", descending=True)
        .top(top_n)
        .test_hypothesis(
            hypothesis="High volume ADRs signal overnight catalysts requiring attention",
            evidence_fields=["NEWS_SENTIMENT", "GICS_SECTOR_NAME"],
        )
        .run()
    )


def get_volume_leaders(top_n: int = 10) -> ScreenResult:
    """Get ADRs with highest relative volume.

    Volume leaders regardless of direction - useful for identifying
    where market attention is focused.

    Args:
        top_n: Number of top results to return

    Returns:
        ScreenResult with volume leaders
    """
    return (
        DynamicScreen("Volume Leaders")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.RVOL + FieldSets.MOMENTUM)
        .filter(F.VOLUME.not_null())
        .rank_by("rvol", descending=True)
        .top(top_n)
        .run()
    )


def get_momentum_extremes(top_n: int = 5) -> Dict[str, ScreenResult]:
    """Get both momentum leaders and laggards.

    Returns:
        Dict with "leaders" and "laggards" ScreenResults
    """
    leaders = MorningNoteScreens.momentum_leaders().run()
    leaders.records = leaders.records[:top_n]

    laggards = MorningNoteScreens.momentum_laggards().run()
    laggards.records = laggards.records[:top_n]

    return {
        "leaders": leaders,
        "laggards": laggards,
    }


def calculate_sector_performance() -> Dict[str, float]:
    """Calculate average performance by GICS sector.

    Aggregates ADR performance by sector for sector breadth analysis.

    Returns:
        Dict mapping sector name to average change percentage
    """
    from collections import defaultdict

    # Fetch all ADRs with sector data
    result = (
        DynamicScreen("Sector Analysis")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.MOMENTUM + FieldSets.SECTOR)
        .filter(F.CHG_PCT_1D.not_null())
        .run()
    )

    # Aggregate by sector
    sector_changes: Dict[str, List[float]] = defaultdict(list)

    for rec in result.records:
        sector = rec.get("GICS_SECTOR_NAME")
        change = rec.change_pct
        if sector and change is not None:
            sector_changes[sector].append(change)

    # Calculate averages
    sector_performance = {}
    for sector, changes in sector_changes.items():
        if changes:
            sector_performance[sector] = sum(changes) / len(changes)

    return dict(sorted(sector_performance.items(), key=lambda x: x[1], reverse=True))


# =============================================================================
# HYPOTHESIS TESTING SCREENS
# =============================================================================

def test_tech_momentum_hypothesis() -> Optional[SignalReport]:
    """Test hypothesis: Tech sector showing momentum leadership.

    Returns:
        SignalReport if hypothesis is supported, None otherwise
    """
    screen = (
        DynamicScreen("Tech Momentum Test")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.MOMENTUM + FieldSets.SECTOR + FieldSets.RVOL)
        .filter(
            F.GICS_SECTOR_NAME == "Information Technology",
            F.CHG_PCT_1D > 0,
        )
        .rank_by("CHG_PCT_1D", descending=True)
        .test_hypothesis(
            hypothesis="Tech sector showing momentum leadership overnight",
            evidence_fields=["NEWS_SENTIMENT"],
        )
    )

    return screen.generate_signal(SignalType.MOMENTUM_LEADER, confidence_threshold=0.3)


def test_risk_off_hypothesis() -> Optional[SignalReport]:
    """Test hypothesis: Risk-off environment (defensive outperformance).

    Returns:
        SignalReport if hypothesis is supported, None otherwise
    """
    screen = (
        DynamicScreen("Risk-Off Test")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.MOMENTUM + FieldSets.SECTOR)
        .filter(
            F.GICS_SECTOR_NAME.in_(["Utilities", "Consumer Staples", "Health Care"]),
            F.CHG_PCT_1D > 0,
        )
        .rank_by("CHG_PCT_1D", descending=True)
        .test_hypothesis(
            hypothesis="Defensive sectors outperforming suggests risk-off sentiment",
        )
    )

    return screen.generate_signal(SignalType.MOMENTUM_LEADER, confidence_threshold=0.4)


def test_volume_conviction_hypothesis(
    rvol_threshold: float = 3.0
) -> Optional[SignalReport]:
    """Test hypothesis: High volume moves have conviction.

    Returns:
        SignalReport if hypothesis is supported, None otherwise
    """
    screen = (
        DynamicScreen("Volume Conviction Test")
        .universe_from_screen("Japan_Liquid_ADRs")
        .with_fields(FieldSets.RVOL + FieldSets.MOMENTUM)
        .filter(
            F.rvol > rvol_threshold,
            F.CHG_PCT_1D > 2.0,  # Significant move
        )
        .rank_by("rvol", descending=True)
        .test_hypothesis(
            hypothesis="High volume moves (>3x RVOL, >2% change) indicate conviction",
        )
    )

    return screen.generate_signal(SignalType.HIGH_RVOL_UP, confidence_threshold=0.2)


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

__all__ = [
    "MorningNoteSignals",
    "run_morning_screens",
    "get_adr_signals",
    "get_volume_leaders",
    "get_momentum_extremes",
    "calculate_sector_performance",
    "test_tech_momentum_hypothesis",
    "test_risk_off_hypothesis",
    "test_volume_conviction_hypothesis",
]
