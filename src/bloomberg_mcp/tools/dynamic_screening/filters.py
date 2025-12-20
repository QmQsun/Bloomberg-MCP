"""Composable filter DSL for dynamic screening.

Provides a fluent, type-safe way to define screening criteria.

The filter DSL supports:
- Comparison operators: gt, lt, gte, lte, eq, ne
- Range filters: between, in_
- Null checks: not_null
- Logical operators: and_, or_, not_

Example:
    >>> from bloomberg_mcp.tools.dynamic_screening.filters import F, and_, or_
    >>>
    >>> # Simple filters
    >>> high_rvol = F.rvol > 2.0
    >>> positive = F.CHG_PCT_1D > 0
    >>>
    >>> # Combined filters
    >>> momentum_signal = and_(
    ...     F.rvol > 2.0,
    ...     F.CHG_PCT_1D > 1.0,
    ...     F.NEWS_SENTIMENT > 0,
    ... )
    >>>
    >>> # Range filter
    >>> mid_cap = F.MARKET_CAP.between(1e9, 10e9)
    >>>
    >>> # Use with screen
    >>> screen.filter(momentum_signal)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Union

from .models import SecurityRecord


# =============================================================================
# FILTER BASE CLASS
# =============================================================================

class Filter(ABC):
    """Abstract base class for all filters.

    Filters are predicates that can be applied to SecurityRecord objects.
    They support logical combination with &, |, and ~ operators.
    """

    @abstractmethod
    def __call__(self, record: SecurityRecord) -> bool:
        """Apply filter to a security record."""
        pass

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description of the filter."""
        pass

    def __and__(self, other: "Filter") -> "Filter":
        """Combine filters with AND."""
        return AndFilter([self, other])

    def __or__(self, other: "Filter") -> "Filter":
        """Combine filters with OR."""
        return OrFilter([self, other])

    def __invert__(self) -> "Filter":
        """Negate filter with NOT."""
        return NotFilter(self)

    def __repr__(self) -> str:
        return f"<Filter: {self.describe()}>"


# =============================================================================
# COMPARISON FILTERS
# =============================================================================

@dataclass
class ComparisonFilter(Filter):
    """Filter based on field comparison."""

    field: str
    operator: str  # "gt", "lt", "gte", "lte", "eq", "ne"
    value: Any

    _OPERATORS = {
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
    }

    _SYMBOLS = {
        "gt": ">",
        "lt": "<",
        "gte": ">=",
        "lte": "<=",
        "eq": "==",
        "ne": "!=",
    }

    def __call__(self, record: SecurityRecord) -> bool:
        field_value = self._get_field_value(record)
        if field_value is None:
            return False
        try:
            return self._OPERATORS[self.operator](field_value, self.value)
        except (TypeError, ValueError):
            return False

    def _get_field_value(self, record: SecurityRecord) -> Any:
        """Get field value, supporting computed fields like rvol."""
        # Check for computed properties first
        if self.field == "rvol":
            return record.rvol
        if self.field == "change_pct":
            return record.change_pct

        # Fall back to fields dict
        return record.fields.get(self.field)

    def describe(self) -> str:
        symbol = self._SYMBOLS.get(self.operator, self.operator)
        return f"{self.field} {symbol} {self.value}"


@dataclass
class BetweenFilter(Filter):
    """Filter for values within a range (inclusive)."""

    field: str
    low: Any
    high: Any
    inclusive: bool = True

    def __call__(self, record: SecurityRecord) -> bool:
        value = record.fields.get(self.field)
        if value is None:
            return False
        try:
            if self.inclusive:
                return self.low <= value <= self.high
            else:
                return self.low < value < self.high
        except (TypeError, ValueError):
            return False

    def describe(self) -> str:
        op = "<=" if self.inclusive else "<"
        return f"{self.low} {op} {self.field} {op} {self.high}"


@dataclass
class InFilter(Filter):
    """Filter for values in a set."""

    field: str
    values: Sequence[Any]

    def __call__(self, record: SecurityRecord) -> bool:
        value = record.fields.get(self.field)
        return value in self.values

    def describe(self) -> str:
        if len(self.values) <= 3:
            vals = ", ".join(str(v) for v in self.values)
        else:
            vals = f"{self.values[0]}, {self.values[1]}, ... ({len(self.values)} values)"
        return f"{self.field} in [{vals}]"


@dataclass
class NotNullFilter(Filter):
    """Filter for non-null values."""

    field: str

    def __call__(self, record: SecurityRecord) -> bool:
        value = record.fields.get(self.field)
        return value is not None

    def describe(self) -> str:
        return f"{self.field} is not null"


# =============================================================================
# LOGICAL COMBINATION FILTERS
# =============================================================================

@dataclass
class AndFilter(Filter):
    """Combine filters with AND logic."""

    filters: List[Filter]

    def __call__(self, record: SecurityRecord) -> bool:
        return all(f(record) for f in self.filters)

    def describe(self) -> str:
        return " AND ".join(f"({f.describe()})" for f in self.filters)

    def __and__(self, other: Filter) -> "AndFilter":
        """Flatten nested ANDs."""
        if isinstance(other, AndFilter):
            return AndFilter(self.filters + other.filters)
        return AndFilter(self.filters + [other])


@dataclass
class OrFilter(Filter):
    """Combine filters with OR logic."""

    filters: List[Filter]

    def __call__(self, record: SecurityRecord) -> bool:
        return any(f(record) for f in self.filters)

    def describe(self) -> str:
        return " OR ".join(f"({f.describe()})" for f in self.filters)

    def __or__(self, other: Filter) -> "OrFilter":
        """Flatten nested ORs."""
        if isinstance(other, OrFilter):
            return OrFilter(self.filters + other.filters)
        return OrFilter(self.filters + [other])


@dataclass
class NotFilter(Filter):
    """Negate a filter."""

    filter: Filter

    def __call__(self, record: SecurityRecord) -> bool:
        return not self.filter(record)

    def describe(self) -> str:
        return f"NOT ({self.filter.describe()})"


# =============================================================================
# FIELD PROXY - For fluent DSL (F.field_name > value)
# =============================================================================

class FieldProxy:
    """Proxy class for fluent field access in filter DSL.

    Allows writing filters like:
        F.PX_LAST > 100
        F.rvol >= 2.0
        F.GICS_SECTOR_NAME == "Technology"

    Example:
        >>> from bloomberg_mcp.tools.dynamic_screening.filters import F
        >>> high_price = F.PX_LAST > 100
        >>> high_rvol = F.rvol >= 2.0
    """

    def __init__(self, field_name: str):
        self._field = field_name

    def __gt__(self, value: Any) -> Filter:
        return ComparisonFilter(self._field, "gt", value)

    def __lt__(self, value: Any) -> Filter:
        return ComparisonFilter(self._field, "lt", value)

    def __ge__(self, value: Any) -> Filter:
        return ComparisonFilter(self._field, "gte", value)

    def __le__(self, value: Any) -> Filter:
        return ComparisonFilter(self._field, "lte", value)

    def __eq__(self, value: Any) -> Filter:  # type: ignore
        return ComparisonFilter(self._field, "eq", value)

    def __ne__(self, value: Any) -> Filter:  # type: ignore
        return ComparisonFilter(self._field, "ne", value)

    def between(self, low: Any, high: Any, inclusive: bool = True) -> Filter:
        """Create a between filter."""
        return BetweenFilter(self._field, low, high, inclusive)

    def in_(self, values: Sequence[Any]) -> Filter:
        """Create an 'in' filter."""
        return InFilter(self._field, values)

    def not_null(self) -> Filter:
        """Create a not-null filter."""
        return NotNullFilter(self._field)


class FieldAccessor:
    """Factory for creating field proxies.

    Usage:
        >>> F = FieldAccessor()
        >>> F.PX_LAST > 100
        >>> F.rvol >= 2.0
    """

    def __getattr__(self, field_name: str) -> FieldProxy:
        return FieldProxy(field_name)


# Singleton field accessor
F = FieldAccessor()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def gt(field: str, value: Any) -> Filter:
    """Greater than filter."""
    return ComparisonFilter(field, "gt", value)


def lt(field: str, value: Any) -> Filter:
    """Less than filter."""
    return ComparisonFilter(field, "lt", value)


def gte(field: str, value: Any) -> Filter:
    """Greater than or equal filter."""
    return ComparisonFilter(field, "gte", value)


def lte(field: str, value: Any) -> Filter:
    """Less than or equal filter."""
    return ComparisonFilter(field, "lte", value)


def eq(field: str, value: Any) -> Filter:
    """Equal filter."""
    return ComparisonFilter(field, "eq", value)


def ne(field: str, value: Any) -> Filter:
    """Not equal filter."""
    return ComparisonFilter(field, "ne", value)


def between(field: str, low: Any, high: Any, inclusive: bool = True) -> Filter:
    """Between filter (inclusive by default)."""
    return BetweenFilter(field, low, high, inclusive)


def in_(field: str, values: Sequence[Any]) -> Filter:
    """In set filter."""
    return InFilter(field, values)


def not_null(field: str) -> Filter:
    """Not null filter."""
    return NotNullFilter(field)


def and_(*filters: Filter) -> Filter:
    """Combine filters with AND."""
    return AndFilter(list(filters))


def or_(*filters: Filter) -> Filter:
    """Combine filters with OR."""
    return OrFilter(list(filters))


def not_(filter: Filter) -> Filter:
    """Negate a filter."""
    return NotFilter(filter)


# =============================================================================
# RANKING FUNCTIONS
# =============================================================================

def rank_records(
    records: List[SecurityRecord],
    field: str,
    descending: bool = True,
) -> List[SecurityRecord]:
    """Rank records by a field value.

    Args:
        records: List of security records
        field: Field to rank by (can be computed like 'rvol')
        descending: If True, highest values get rank 1

    Returns:
        Records with rank attribute set
    """
    def get_sort_value(rec: SecurityRecord) -> Any:
        if field == "rvol":
            return rec.rvol if rec.rvol is not None else float('-inf')
        if field == "change_pct":
            return rec.change_pct if rec.change_pct is not None else float('-inf')
        val = rec.fields.get(field)
        return val if val is not None else float('-inf')

    sorted_records = sorted(
        records,
        key=get_sort_value,
        reverse=descending
    )

    for i, rec in enumerate(sorted_records):
        rec.rank = i + 1

    return sorted_records


def top_n(records: List[SecurityRecord], n: int) -> List[SecurityRecord]:
    """Get top N records (assumes already ranked)."""
    return [r for r in records if r.rank is not None and r.rank <= n]


def bottom_n(records: List[SecurityRecord], n: int) -> List[SecurityRecord]:
    """Get bottom N records (assumes already ranked)."""
    if not records:
        return []
    max_rank = max(r.rank for r in records if r.rank is not None)
    return [r for r in records if r.rank is not None and r.rank > max_rank - n]


def percentile(
    records: List[SecurityRecord],
    min_pct: float = 0,
    max_pct: float = 100,
) -> List[SecurityRecord]:
    """Get records within percentile range (assumes already ranked)."""
    if not records:
        return []

    total = len(records)
    result = []

    for rec in records:
        if rec.rank is not None:
            pct = (rec.rank / total) * 100
            rec.percentile = pct
            if min_pct <= pct <= max_pct:
                result.append(rec)

    return result
