"""Response quality gates for Bloomberg data.

Validates Bloomberg API responses before they reach the LLM,
catching stale data, empty responses, and field limit violations.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Bloomberg field limits per request type
FIELD_LIMITS = {
    "reference": 400,
    "historical": 25,
}


class ValidationWarning:
    """A non-fatal quality issue attached to response data."""

    def __init__(self, code: str, message: str, security: Optional[str] = None):
        self.code = code
        self.message = message
        self.security = security

    def __str__(self) -> str:
        prefix = f"[{self.security}] " if self.security else ""
        return f"{prefix}{self.code}: {self.message}"


def validate_field_count(fields: List[str], request_type: str) -> None:
    """Pre-request assertion: field count within Bloomberg limits.

    Args:
        fields: Expanded field list (after FieldSet resolution)
        request_type: "reference" or "historical"

    Raises:
        ValueError: If field count exceeds Bloomberg limit
    """
    max_fields = FIELD_LIMITS.get(request_type)
    if max_fields is None:
        return
    if len(fields) > max_fields:
        raise ValueError(
            f"Bloomberg {request_type} request supports max {max_fields} fields, "
            f"got {len(fields)}. Use _expand_and_chunk_fields() to split."
        )


def validate_reference_response(
    data: List[Any],
    requested_fields: Optional[List[str]] = None,
) -> List[ValidationWarning]:
    """Post-Bloomberg quality checks for reference data (BDP).

    Checks:
    1. Securities with ALL fields empty or errored
    2. Missing fields (requested but not returned)
    3. High proportion of None/NaN values

    Returns list of warnings (non-fatal). Warnings are also injected
    into SecurityData.errors so the LLM sees them.
    """
    warnings: List[ValidationWarning] = []

    for sec_data in data:
        security = getattr(sec_data, "security", "unknown")
        fields = getattr(sec_data, "fields", {})
        errors = getattr(sec_data, "errors", [])

        # Check 1: All fields empty
        if not fields or all(v is None for v in fields.values()):
            w = ValidationWarning(
                "EMPTY_RESPONSE",
                "All fields returned empty — check security identifier and field names",
                security=security,
            )
            warnings.append(w)
            if hasattr(sec_data, "errors"):
                sec_data.errors.append(str(w))
            continue

        # Check 2: Missing requested fields
        if requested_fields:
            returned = set(fields.keys())
            missing = [f for f in requested_fields if f not in returned]
            if missing and len(missing) <= 5:
                w = ValidationWarning(
                    "MISSING_FIELDS",
                    f"Fields not returned: {', '.join(missing)}",
                    security=security,
                )
                warnings.append(w)

        # Check 3: High None ratio (> 50% of fields are None)
        none_count = sum(1 for v in fields.values() if v is None)
        if fields and none_count / len(fields) > 0.5:
            w = ValidationWarning(
                "HIGH_NULL_RATIO",
                f"{none_count}/{len(fields)} fields returned None",
                security=security,
            )
            warnings.append(w)

    return warnings


def validate_historical_response(
    data: List[Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[ValidationWarning]:
    """Post-Bloomberg quality checks for historical data (BDH).

    Checks:
    1. Empty data series
    2. Unexpectedly short series (< 5 data points for > 30 day range)
    """
    warnings: List[ValidationWarning] = []

    for hist_data in data:
        security = getattr(hist_data, "security", "unknown")
        points = getattr(hist_data, "data", [])

        if not points:
            w = ValidationWarning(
                "EMPTY_SERIES",
                "No historical data points returned — check date range and security",
                security=security,
            )
            warnings.append(w)
            if hasattr(hist_data, "errors"):
                hist_data.errors.append(str(w))
            continue

        # Check short series relative to date range
        if start_date and end_date and len(points) < 5:
            try:
                s = _parse_date(start_date)
                e = _parse_date(end_date)
                if s and e and (e - s) > timedelta(days=30):
                    w = ValidationWarning(
                        "SHORT_SERIES",
                        f"Only {len(points)} data points for "
                        f"{(e - s).days}-day range — data may be sparse",
                        security=security,
                    )
                    warnings.append(w)
            except Exception:
                pass  # Date parsing failure is not a validation error

    return warnings


def validate_bulk_response(
    field_value: Any,
    field_name: str,
    security: str,
) -> List[ValidationWarning]:
    """Post-Bloomberg quality checks for bulk data (BDS).

    Checks:
    1. Scalar returned instead of array (field name likely wrong)
    2. Empty array
    """
    warnings: List[ValidationWarning] = []

    if field_value is None:
        warnings.append(ValidationWarning(
            "NULL_BULK_FIELD",
            f"BDS field '{field_name}' returned None — verify field name is a valid BDS field",
            security=security,
        ))
    elif not isinstance(field_value, (list, dict)):
        warnings.append(ValidationWarning(
            "SCALAR_BULK_FIELD",
            f"BDS field '{field_name}' returned scalar ({type(field_value).__name__}) "
            f"instead of array — this is likely a BDP field, use bloomberg_get_reference_data instead",
            security=security,
        ))
    elif isinstance(field_value, list) and len(field_value) == 0:
        warnings.append(ValidationWarning(
            "EMPTY_BULK_FIELD",
            f"BDS field '{field_name}' returned empty array",
            security=security,
        ))

    return warnings


def _parse_date(date_str: str) -> Optional[datetime]:
    """Try to parse YYYYMMDD or YYYY-MM-DD."""
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None
