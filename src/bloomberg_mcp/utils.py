"""Shared utility functions for Bloomberg MCP server."""

import os
from typing import List

# Constants
CHARACTER_LIMIT = 50000
BLOOMBERG_HOST = os.environ.get("BLOOMBERG_HOST", "localhost")
BLOOMBERG_PORT = int(os.environ.get("BLOOMBERG_PORT", "8194"))


def _get_fieldset_map():
    """Lazy-load fieldset map to avoid circular imports.

    Single source of truth for FieldSet name -> FieldSet object mapping.
    """
    from bloomberg_mcp.tools.dynamic_screening import FieldSets
    return {
        "RVOL": FieldSets.RVOL,
        "MOMENTUM": FieldSets.MOMENTUM,
        "MOMENTUM_EXTENDED": FieldSets.MOMENTUM_EXTENDED,
        "SENTIMENT": FieldSets.SENTIMENT,
        "SECTOR": FieldSets.SECTOR,
        "TECHNICAL": FieldSets.TECHNICAL,
        "TECHNICAL_EXTENDED": FieldSets.TECHNICAL_EXTENDED,
        "VALUATION": FieldSets.VALUATION,
        "PRICE": FieldSets.PRICE,
        "PRICE_EXTENDED": FieldSets.PRICE_EXTENDED,
        "ADR": FieldSets.ADR,
        "MORNING_NOTE": FieldSets.MORNING_NOTE,
        "SCREENING_FULL": FieldSets.SCREENING_FULL,
        "VOLUME_EXTENDED": FieldSets.VOLUME_EXTENDED,
        "LIQUIDITY": FieldSets.LIQUIDITY,
        "VOLATILITY": FieldSets.VOLATILITY,
        "ANALYST": FieldSets.ANALYST,
        "CLASSIFICATION": FieldSets.CLASSIFICATION,
        "DESCRIPTIVE": FieldSets.DESCRIPTIVE,
        # Fundamental FieldSets (PHASE 1)
        "ESTIMATES_CONSENSUS": FieldSets.ESTIMATES_CONSENSUS,
        "PROFITABILITY": FieldSets.PROFITABILITY,
        "CASH_FLOW": FieldSets.CASH_FLOW,
        "BALANCE_SHEET": FieldSets.BALANCE_SHEET,
        "OWNERSHIP": FieldSets.OWNERSHIP,
        "GOVERNANCE": FieldSets.GOVERNANCE,
        "RISK": FieldSets.RISK,
        "VALUATION_EXTENDED": FieldSets.VALUATION_EXTENDED,
        "EARNINGS_SURPRISE": FieldSets.EARNINGS_SURPRISE,
        "GROWTH": FieldSets.GROWTH,
    }


def _expand_fields(fields: List[str]) -> List[str]:
    """Expand FieldSet shortcuts to raw Bloomberg fields.

    Accepts mix of FieldSet names (e.g., 'VALUATION', 'MOMENTUM') and
    raw Bloomberg fields (e.g., 'PX_LAST', 'PE_RATIO').

    Returns deduplicated list preserving order.
    """
    fieldset_map = _get_fieldset_map()
    expanded = []
    seen = set()

    for field_spec in fields:
        field_upper = field_spec.upper()
        if field_upper in fieldset_map:
            # Expand FieldSet to its component fields
            for f in fieldset_map[field_upper].fields:
                if f not in seen:
                    seen.add(f)
                    expanded.append(f)
        else:
            # Raw Bloomberg field - preserve original case
            if field_spec not in seen:
                seen.add(field_spec)
                expanded.append(field_spec)

    return expanded


def _normalize_date(date_str: str) -> str:
    """Normalize date string to YYYYMMDD format.

    Accepts:
    - YYYYMMDD (passthrough)
    - YYYY-MM-DD (ISO format)
    - YYYY/MM/DD

    Returns YYYYMMDD format for Bloomberg API.
    """
    # Already in correct format
    if len(date_str) == 8 and date_str.isdigit():
        return date_str

    # Try ISO format YYYY-MM-DD
    if len(date_str) == 10 and date_str[4] in '-/':
        return date_str.replace('-', '').replace('/', '')

    # Fallback - return as-is and let Bloomberg validate
    return date_str


def _truncate_response(result: str) -> str:
    """Truncate response if it exceeds character limit."""
    if len(result) > CHARACTER_LIMIT:
        return result[:CHARACTER_LIMIT] + f"\n\n... Response truncated (exceeded {CHARACTER_LIMIT} characters)"
    return result


def _get_session():
    """Get Bloomberg session with configured host/port."""
    from bloomberg_mcp.core.session import BloombergSession

    session = BloombergSession.get_instance(host=BLOOMBERG_HOST, port=BLOOMBERG_PORT)

    if not session.is_connected():
        if not session.connect():
            raise RuntimeError(
                f"Failed to connect to Bloomberg Terminal at {BLOOMBERG_HOST}:{BLOOMBERG_PORT}. "
                "Ensure Bloomberg Terminal is running and the API is enabled."
            )
    return session
