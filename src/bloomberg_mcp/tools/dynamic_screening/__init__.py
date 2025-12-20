"""Dynamic Screening Toolset for Bloomberg API.

This module provides an elegant, composable screening framework that unifies:
- BeqsRequest: Runs saved Bloomberg EQS screens (universe definition)
- CustomEqsRequest: Fetches field data for a universe (data enrichment)
- Python DSL: Composable filters for hypothesis testing

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    DYNAMIC SCREENING FLOW                        │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  1. UNIVERSE DEFINITION                                          │
    │     ├── BeqsRequest → Saved screen (e.g., Japan_Liquid_ADRs)   │
    │     ├── Static list → Explicit securities                       │
    │     └── Index constituents → SPX, TOPIX, etc.                   │
    │                                                                  │
    │  2. DATA ENRICHMENT (CustomEqsRequest)                          │
    │     ├── FieldSet → Pre-defined field collections                │
    │     ├── Custom fields → Ad-hoc field selection                  │
    │     └── Partial response handling → Batched collection          │
    │                                                                  │
    │  3. FILTERING (Python DSL)                                       │
    │     ├── Predicate filters → gt, lt, eq, between, etc.          │
    │     ├── Composite filters → and_, or_, not_                     │
    │     └── Ranking filters → top_n, bottom_n, percentile           │
    │                                                                  │
    │  4. OUTPUT                                                       │
    │     ├── ScreenResult → Securities with field data               │
    │     ├── Evidence → Hypothesis validation artifacts              │
    │     └── SignalReport → Actionable trading signals               │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘

Example usage:
    >>> from bloomberg_mcp.tools.dynamic_screening import (
    ...     DynamicScreen,
    ...     FieldSets,
    ...     F,
    ... )
    >>>
    >>> # Define a screen
    >>> screen = (
    ...     DynamicScreen("High RVOL Momentum")
    ...     .universe_from_screen("Japan_Liquid_ADRs")
    ...     .with_fields(FieldSets.RVOL + FieldSets.MOMENTUM)
    ...     .filter(
    ...         F.rvol > 2.0,
    ...         F.change_pct > 0,
    ...     )
    ...     .rank_by("rvol", descending=True)
    ...     .top_n(10)
    ... )
    >>>
    >>> # Execute
    >>> result = screen.run()
    >>> for sec in result.securities:
    ...     print(f"{sec}: RVOL={sec.rvol:.1f}x, Chg={sec.change_pct:.2f}%")
"""

from .models import (
    ScreenUniverse,
    FieldSet,
    FieldSets,
    ScreenResult,
    SecurityRecord,
    SignalReport,
    SignalType,
)

from .filters import (
    F,
    Filter,
    gt,
    lt,
    gte,
    lte,
    eq,
    ne,
    between,
    in_,
    not_null,
    and_,
    or_,
    not_,
)

from .screen import DynamicScreen, MorningNoteScreens

from .custom_eqs import (
    get_custom_eqs_data,
    build_custom_eqs_request,
    parse_custom_eqs_response,
)

__all__ = [
    # Core screen class
    "DynamicScreen",
    "MorningNoteScreens",

    # Universe and field configuration
    "ScreenUniverse",
    "FieldSet",
    "FieldSets",

    # Filter DSL
    "F",
    "Filter",
    "gt", "lt", "gte", "lte", "eq", "ne",
    "between", "in_", "not_null",
    "and_", "or_", "not_",

    # Results
    "ScreenResult",
    "SecurityRecord",
    "SignalReport",
    "SignalType",

    # Low-level CustomEqsRequest access
    "get_custom_eqs_data",
    "build_custom_eqs_request",
    "parse_custom_eqs_response",
]
