"""Shared utility functions for Bloomberg MCP server."""

import os
from typing import List

# Constants
CHARACTER_LIMIT = 50000

# Bloomberg field limits per request type
_FIELD_LIMIT_REFERENCE = 400
_FIELD_LIMIT_HISTORICAL = 25
BLOOMBERG_HOST = os.environ.get("BLOOMBERG_HOST", "localhost")
BLOOMBERG_PORT = int(os.environ.get("BLOOMBERG_PORT", "8194"))


def _get_fieldset_map():
    """Lazy-load fieldset map to avoid circular imports.

    Single source of truth for FieldSet name -> FieldSet object mapping.
    Tries YAML config first (config/fieldsets.yaml), falls back to code-defined FieldSets.
    """
    from bloomberg_mcp.tools.dynamic_screening import FieldSets

    # Code-defined FieldSets (always available)
    code_map = {
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

    # Try YAML overlay — adds new FieldSets or overrides existing ones
    try:
        from bloomberg_mcp.config import load_fieldsets_yaml
        from bloomberg_mcp.tools.dynamic_screening.models import FieldSet

        yaml_fieldsets = load_fieldsets_yaml()
        for name, fields in yaml_fieldsets.items():
            if name not in code_map:
                # New FieldSet from YAML only
                code_map[name] = FieldSet(name.lower(), tuple(fields))
    except Exception:
        pass  # YAML overlay is best-effort

    return code_map


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


def _expand_and_chunk_fields(
    fields: List[str],
    max_per_request: int = _FIELD_LIMIT_HISTORICAL,
) -> List[List[str]]:
    """Expand FieldSet shortcuts then chunk into legal-sized batches.

    Use this when the expanded field list may exceed Bloomberg's per-request
    limit (400 for BDP, 25 for BDH).

    Returns:
        List of field-list batches, each within max_per_request.
    """
    expanded = _expand_fields(fields)
    if len(expanded) <= max_per_request:
        return [expanded]
    return [expanded[i:i + max_per_request] for i in range(0, len(expanded), max_per_request)]


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
