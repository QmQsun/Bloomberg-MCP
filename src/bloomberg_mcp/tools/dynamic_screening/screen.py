"""DynamicScreen - Fluent API for composable Bloomberg screening.

The DynamicScreen class provides a builder pattern for constructing
and executing Bloomberg screens with:
- Multiple universe sources (static list, saved screen, index)
- Configurable field sets
- Composable filters
- Ranking and selection
- Hypothesis testing support

Example:
    >>> from bloomberg_mcp.tools.dynamic_screening import (
    ...     DynamicScreen, FieldSets, F
    ... )
    >>>
    >>> # Build and execute a screen
    >>> result = (
    ...     DynamicScreen("High RVOL Tech")
    ...     .universe_from_screen("Japan_Liquid_ADRs")
    ...     .with_fields(FieldSets.RVOL + FieldSets.MOMENTUM)
    ...     .filter(
    ...         F.rvol > 2.0,
    ...         F.CHG_PCT_1D > 0,
    ...     )
    ...     .rank_by("rvol", descending=True)
    ...     .top(10)
    ...     .run()
    ... )
    >>>
    >>> for rec in result:
    ...     print(f"{rec.ticker}: RVOL={rec.rvol:.1f}x")
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from .models import (
    FieldSet,
    FieldSets,
    ScreenUniverse,
    ScreenResult,
    SecurityRecord,
    SignalReport,
    SignalType,
    UniverseType,
)
from .filters import (
    Filter,
    AndFilter,
    rank_records,
    top_n,
    bottom_n,
    percentile,
)
from .custom_eqs import (
    get_custom_eqs_data,
    get_universe_from_screen,
    get_index_constituents,
)

logger = logging.getLogger(__name__)


class DynamicScreen:
    """Fluent builder for dynamic Bloomberg screens.

    DynamicScreen provides a chainable API for:
    1. Defining the universe (static, saved screen, or index)
    2. Specifying fields to fetch
    3. Applying filters
    4. Ranking and selecting results

    The screen is executed lazily when run() is called.

    Example:
        >>> screen = (
        ...     DynamicScreen("My Screen")
        ...     .universe_from_list(["AAPL US Equity", "MSFT US Equity"])
        ...     .with_fields(["PX_LAST", "CHG_PCT_1D"])
        ...     .filter(F.PX_LAST > 100)
        ...     .run()
        ... )
    """

    def __init__(self, name: str):
        """Initialize a new dynamic screen.

        Args:
            name: Human-readable name for the screen
        """
        self._name = name
        self._universe: Optional[ScreenUniverse] = None
        self._fields: List[str] = []
        self._filters: List[Filter] = []
        self._rank_field: Optional[str] = None
        self._rank_descending: bool = True
        self._top_n: Optional[int] = None
        self._bottom_n: Optional[int] = None
        self._percentile_range: Optional[tuple] = None

        # Hypothesis testing
        self._hypothesis: Optional[str] = None
        self._evidence_fields: List[str] = []

    # =========================================================================
    # UNIVERSE CONFIGURATION
    # =========================================================================

    def universe_from_list(self, securities: List[str]) -> "DynamicScreen":
        """Set universe from explicit security list.

        Args:
            securities: List of Bloomberg security identifiers

        Returns:
            Self for chaining
        """
        self._universe = ScreenUniverse.from_list(securities)
        return self

    def universe_from_screen(
        self,
        screen_name: str,
        screen_type: str = "PRIVATE"
    ) -> "DynamicScreen":
        """Set universe from a saved Bloomberg EQS screen.

        Args:
            screen_name: Name of the saved screen
            screen_type: "PRIVATE" or "GLOBAL"

        Returns:
            Self for chaining
        """
        self._universe = ScreenUniverse.from_screen(screen_name, screen_type)
        return self

    def universe_from_index(self, index_ticker: str) -> "DynamicScreen":
        """Set universe from index constituents.

        Args:
            index_ticker: Index identifier (e.g., "SPX Index")

        Returns:
            Self for chaining
        """
        self._universe = ScreenUniverse.from_index(index_ticker)
        return self

    # =========================================================================
    # FIELD CONFIGURATION
    # =========================================================================

    def with_fields(
        self,
        fields: Union[FieldSet, List[str], str]
    ) -> "DynamicScreen":
        """Add fields to fetch.

        Can be called multiple times to accumulate fields.

        Args:
            fields: FieldSet, list of field names, or single field name

        Returns:
            Self for chaining
        """
        if isinstance(fields, FieldSet):
            self._fields.extend(fields.fields)
        elif isinstance(fields, list):
            self._fields.extend(fields)
        else:
            self._fields.append(fields)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for f in self._fields:
            if f not in seen:
                seen.add(f)
                deduped.append(f)
        self._fields = deduped

        return self

    # =========================================================================
    # FILTERING
    # =========================================================================

    def filter(self, *filters: Filter) -> "DynamicScreen":
        """Add filters to the screen.

        Multiple filters are combined with AND logic.
        Can be called multiple times to accumulate filters.

        Args:
            *filters: Filter objects (from F.field > value syntax)

        Returns:
            Self for chaining

        Example:
            >>> screen.filter(
            ...     F.rvol > 2.0,
            ...     F.CHG_PCT_1D > 0,
            ... )
        """
        self._filters.extend(filters)
        return self

    def filter_fn(
        self,
        predicate: Callable[[SecurityRecord], bool],
        description: str = "custom"
    ) -> "DynamicScreen":
        """Add a custom filter function.

        For complex filtering logic not expressible with the DSL.

        Args:
            predicate: Function that takes SecurityRecord and returns bool
            description: Human-readable description

        Returns:
            Self for chaining

        Example:
            >>> screen.filter_fn(
            ...     lambda r: r.rvol and r.rvol > r.get("RVOL_AVG", 1),
            ...     description="rvol above average"
            ... )
        """
        class CustomFilter(Filter):
            def __init__(self, fn, desc):
                self._fn = fn
                self._desc = desc

            def __call__(self, record: SecurityRecord) -> bool:
                return self._fn(record)

            def describe(self) -> str:
                return self._desc

        self._filters.append(CustomFilter(predicate, description))
        return self

    # =========================================================================
    # RANKING AND SELECTION
    # =========================================================================

    def rank_by(
        self,
        field: str,
        descending: bool = True
    ) -> "DynamicScreen":
        """Rank results by a field.

        Args:
            field: Field name to rank by (can be computed like "rvol")
            descending: If True, highest values get rank 1

        Returns:
            Self for chaining
        """
        self._rank_field = field
        self._rank_descending = descending
        return self

    def top(self, n: int) -> "DynamicScreen":
        """Select top N results (requires rank_by).

        Args:
            n: Number of top results to keep

        Returns:
            Self for chaining
        """
        self._top_n = n
        return self

    def bottom(self, n: int) -> "DynamicScreen":
        """Select bottom N results (requires rank_by).

        Args:
            n: Number of bottom results to keep

        Returns:
            Self for chaining
        """
        self._bottom_n = n
        return self

    def percentile_range(
        self,
        min_pct: float = 0,
        max_pct: float = 100
    ) -> "DynamicScreen":
        """Select results within percentile range (requires rank_by).

        Args:
            min_pct: Minimum percentile (0-100)
            max_pct: Maximum percentile (0-100)

        Returns:
            Self for chaining
        """
        self._percentile_range = (min_pct, max_pct)
        return self

    # =========================================================================
    # HYPOTHESIS TESTING
    # =========================================================================

    def test_hypothesis(
        self,
        hypothesis: str,
        evidence_fields: Optional[List[str]] = None
    ) -> "DynamicScreen":
        """Set up hypothesis testing for this screen.

        When run(), the screen will include hypothesis validation
        in the result, collecting evidence from specified fields.

        Args:
            hypothesis: The hypothesis statement to test
            evidence_fields: Additional fields to collect as evidence

        Returns:
            Self for chaining

        Example:
            >>> screen.test_hypothesis(
            ...     hypothesis="Tech momentum continues overnight",
            ...     evidence_fields=["NEWS_SENTIMENT", "GICS_SECTOR_NAME"],
            ... )
        """
        self._hypothesis = hypothesis
        if evidence_fields:
            self._evidence_fields = evidence_fields
            # Ensure evidence fields are fetched
            self.with_fields(evidence_fields)
        return self

    # =========================================================================
    # EXECUTION
    # =========================================================================

    def run(self) -> ScreenResult:
        """Execute the screen and return results.

        This is where all the work happens:
        1. Resolve universe (fetch from screen/index if needed)
        2. Fetch field data via CustomEqsRequest
        3. Apply filters
        4. Rank and select

        Returns:
            ScreenResult with filtered, ranked securities

        Raises:
            ValueError: If universe is not configured
            RuntimeError: If Bloomberg connection fails
        """
        start_time = time.time()

        if self._universe is None:
            raise ValueError("Universe not configured. Call universe_from_* first.")

        # Step 1: Resolve universe to list of securities
        securities = self._resolve_universe()
        universe_size = len(securities)
        logger.info(f"Screen '{self._name}': Universe has {universe_size} securities")

        if not securities:
            return ScreenResult(
                name=self._name,
                universe_size=0,
                filtered_count=0,
                errors=["Empty universe"],
            )

        # Step 2: Ensure we have fields to fetch
        if not self._fields:
            # Default to basic price/volume fields
            self._fields = list(FieldSets.PRICE.fields) + list(FieldSets.RVOL.fields)

        # Step 3: Fetch data via CustomEqsRequest
        records = get_custom_eqs_data(securities, self._fields)
        logger.info(f"Screen '{self._name}': Fetched data for {len(records)} securities")

        # Step 4: Apply filters
        if self._filters:
            combined_filter = AndFilter(self._filters) if len(self._filters) > 1 else self._filters[0]
            records = [r for r in records if combined_filter(r)]
            logger.info(f"Screen '{self._name}': {len(records)} passed filters")

        # Step 5: Rank if requested
        if self._rank_field:
            records = rank_records(records, self._rank_field, self._rank_descending)

        # Step 6: Select subset if requested
        if self._top_n is not None:
            records = top_n(records, self._top_n)
        elif self._bottom_n is not None:
            records = bottom_n(records, self._bottom_n)
        elif self._percentile_range is not None:
            records = percentile(records, *self._percentile_range)

        # Build result
        execution_time = (time.time() - start_time) * 1000

        result = ScreenResult(
            name=self._name,
            records=records,
            universe_size=universe_size,
            filtered_count=len(records),
            execution_time_ms=execution_time,
            universe_source=self._universe.source,
            fields_requested=self._fields.copy(),
            filters_applied=[f.describe() for f in self._filters],
            executed_at=datetime.now(),
        )

        logger.info(
            f"Screen '{self._name}' complete: "
            f"{result.filtered_count}/{universe_size} securities, "
            f"{execution_time:.0f}ms"
        )

        return result

    def _resolve_universe(self) -> List[str]:
        """Resolve universe configuration to list of securities."""
        if self._universe is None:
            return []

        if self._universe.type == UniverseType.STATIC:
            return self._universe.securities

        elif self._universe.type == UniverseType.SAVED_SCREEN:
            return get_universe_from_screen(
                self._universe.source,
                self._universe.screen_type,
            )

        elif self._universe.type == UniverseType.INDEX:
            return get_index_constituents(self._universe.source)

        return []

    # =========================================================================
    # SIGNAL GENERATION
    # =========================================================================

    def generate_signal(
        self,
        signal_type: SignalType,
        confidence_threshold: float = 0.5,
    ) -> Optional[SignalReport]:
        """Execute screen and generate a signal report.

        This is a convenience method that runs the screen and
        packages the results as a SignalReport for hypothesis validation.

        Args:
            signal_type: Type of signal to generate
            confidence_threshold: Minimum confidence to return signal

        Returns:
            SignalReport if confidence meets threshold, None otherwise
        """
        result = self.run()

        if not result.records:
            return None

        # Calculate confidence based on filter pass rate and signal strength
        confidence = len(result.records) / max(result.universe_size, 1)

        # Boost confidence if we have strong outliers
        if result.records and self._rank_field:
            top_rec = result.records[0]
            if self._rank_field == "rvol" and top_rec.rvol:
                # High RVOL boosts confidence
                confidence = min(1.0, confidence * (1 + top_rec.rvol / 10))

        if confidence < confidence_threshold:
            return None

        # Collect evidence
        evidence: Dict[str, Any] = {
            "universe_size": result.universe_size,
            "pass_count": result.filtered_count,
            "pass_rate": result.filtered_count / max(result.universe_size, 1),
        }

        if self._evidence_fields:
            for field in self._evidence_fields:
                values = [r.fields.get(field) for r in result.records if r.fields.get(field) is not None]
                if values:
                    if all(isinstance(v, (int, float)) for v in values):
                        evidence[f"{field}_avg"] = sum(values) / len(values)
                        evidence[f"{field}_max"] = max(values)
                        evidence[f"{field}_min"] = min(values)
                    else:
                        # Categorical - show distribution
                        from collections import Counter
                        evidence[f"{field}_distribution"] = dict(Counter(values))

        return SignalReport(
            signal_type=signal_type,
            securities=result.securities,
            hypothesis=self._hypothesis or f"Signal: {signal_type.value}",
            evidence=evidence,
            confidence=confidence,
            screen_result=result,
        )

    # =========================================================================
    # CLONING / COPYING
    # =========================================================================

    def clone(self) -> "DynamicScreen":
        """Create a copy of this screen for modification.

        Returns:
            New DynamicScreen with same configuration
        """
        new_screen = DynamicScreen(self._name)
        new_screen._universe = self._universe
        new_screen._fields = self._fields.copy()
        new_screen._filters = self._filters.copy()
        new_screen._rank_field = self._rank_field
        new_screen._rank_descending = self._rank_descending
        new_screen._top_n = self._top_n
        new_screen._bottom_n = self._bottom_n
        new_screen._percentile_range = self._percentile_range
        new_screen._hypothesis = self._hypothesis
        new_screen._evidence_fields = self._evidence_fields.copy()
        return new_screen


# =============================================================================
# PREDEFINED SCREENS - Common morning note use cases
# =============================================================================

class MorningNoteScreens:
    """Pre-configured screens for morning note generation.

    These screens are ready to use or can be customized via clone().

    Example:
        >>> result = MorningNoteScreens.high_rvol_adrs().run()
        >>> for rec in result[:5]:
        ...     print(f"{rec.ticker}: RVOL={rec.rvol:.1f}x, Chg={rec.change_pct:.2f}%")
    """

    @staticmethod
    def high_rvol_adrs(rvol_threshold: float = 2.0) -> DynamicScreen:
        """ADRs with high relative volume (potential catalysts)."""
        from .filters import F

        return (
            DynamicScreen("High RVOL ADRs")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.ADR + FieldSets.MOMENTUM + FieldSets.SENTIMENT)
            .filter(F.rvol > rvol_threshold)
            .rank_by("rvol", descending=True)
            .top(10)
            .test_hypothesis(
                hypothesis="High volume ADRs signal overnight catalysts",
                evidence_fields=["NEWS_SENTIMENT", "GICS_SECTOR_NAME"],
            )
        )

    @staticmethod
    def momentum_leaders() -> DynamicScreen:
        """ADRs with strongest positive momentum."""
        from .filters import F

        return (
            DynamicScreen("Momentum Leaders")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.MOMENTUM + FieldSets.RVOL)
            .filter(F.CHG_PCT_1D > 0)
            .rank_by("CHG_PCT_1D", descending=True)
            .top(10)
        )

    @staticmethod
    def momentum_laggards() -> DynamicScreen:
        """ADRs with weakest momentum (potential shorts or recovery plays)."""
        from .filters import F

        return (
            DynamicScreen("Momentum Laggards")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.MOMENTUM + FieldSets.RVOL)
            .filter(F.CHG_PCT_1D < 0)
            .rank_by("CHG_PCT_1D", descending=False)
            .top(10)
        )

    @staticmethod
    def sentiment_positive() -> DynamicScreen:
        """ADRs with positive news sentiment."""
        from .filters import F

        return (
            DynamicScreen("Positive Sentiment")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.SENTIMENT + FieldSets.MOMENTUM)
            .filter(F.NEWS_SENTIMENT > 0)
            .rank_by("NEWS_SENTIMENT", descending=True)
            .top(10)
        )

    @staticmethod
    def sentiment_divergence() -> DynamicScreen:
        """ADRs where sentiment diverges from price action."""
        from .filters import F, or_

        return (
            DynamicScreen("Sentiment Divergence")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.SENTIMENT + FieldSets.MOMENTUM)
            .filter(
                or_(
                    # Positive sentiment but negative price
                    F.NEWS_SENTIMENT > 0.01,
                    # Negative sentiment but positive price
                    F.NEWS_SENTIMENT < -0.01,
                )
            )
            .filter_fn(
                lambda r: (
                    (r.get("NEWS_SENTIMENT", 0) > 0 and r.change_pct and r.change_pct < -1) or
                    (r.get("NEWS_SENTIMENT", 0) < 0 and r.change_pct and r.change_pct > 1)
                ),
                description="sentiment diverges from price"
            )
            .rank_by("rvol", descending=True)
            .test_hypothesis(
                hypothesis="Sentiment-price divergence signals reversal potential",
            )
        )

    @staticmethod
    def volume_breakout() -> DynamicScreen:
        """ADRs with volume breakouts (RVOL > 3x) on up moves."""
        from .filters import F

        return (
            DynamicScreen("Volume Breakout")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.RVOL + FieldSets.MOMENTUM + FieldSets.TECHNICAL)
            .filter(
                F.rvol > 3.0,
                F.CHG_PCT_1D > 2.0,
            )
            .rank_by("rvol", descending=True)
            .test_hypothesis(
                hypothesis="Volume breakouts signal momentum continuation",
            )
        )

    @staticmethod
    def sector_screen(sector: str) -> DynamicScreen:
        """Screen ADRs filtered by GICS sector."""
        from .filters import F

        return (
            DynamicScreen(f"{sector} Sector")
            .universe_from_screen("Japan_Liquid_ADRs")
            .with_fields(FieldSets.ADR + FieldSets.SECTOR)
            .filter(F.GICS_SECTOR_NAME == sector)
            .rank_by("CHG_PCT_1D", descending=True)
        )
