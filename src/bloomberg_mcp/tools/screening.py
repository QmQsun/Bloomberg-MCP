"""Equity screening tools for Bloomberg API.

Provides functions to run pre-saved Bloomberg equity screens (EQS).
"""

from typing import Optional

from ..core.session import BloombergSession
from ..core.requests import build_beqs_request
from ..core.responses import ScreenResult, parse_beqs_response


def run_screen(
    screen_name: str,
    screen_type: str = "PRIVATE",
    group: Optional[str] = None,
) -> ScreenResult:
    """Run a pre-saved Bloomberg equity screen (EQS).

    Executes a saved screen from Bloomberg's Equity Screening tool and returns
    the list of matching securities along with any output fields defined in
    the screen.

    Args:
        screen_name: Name of the saved screen (e.g., "Japan_ADR_Universe").
            Must match exactly as saved in Bloomberg Terminal.
        screen_type: Type of screen - one of:
            "PRIVATE" - User's personal saved screens (default)
            "GLOBAL" - Bloomberg's pre-defined example screens
        group: Optional folder/group name if screen is organized in folders

    Returns:
        ScreenResult object containing:
            - securities: List of matching security identifiers
            - field_data: List of dicts with security and field values
            - columns: List of column names from the screen
            - errors: Any errors encountered

    Example:
        >>> result = run_screen("Japan_ADR_Universe")
        >>> print(f"Found {len(result.securities)} securities")
        >>> for sec in result.field_data[:5]:
        ...     print(f"{sec['security']}: {sec.get('Und Tkr', 'N/A')}")

    Note:
        Screens must be created and saved in Bloomberg Terminal EQS <GO>
        before they can be accessed via API.
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the reference data service (BEQS uses //blp/refdata)
    service = session.get_service("//blp/refdata")

    # Build the BEQS request
    request = build_beqs_request(
        service=service,
        screen_name=screen_name,
        screen_type=screen_type,
        group=group,
    )

    # Send the request and get response
    # Note: parse_beqs_response needs screen_name, so we use a lambda
    results = session.send_request(
        request,
        service_name="//blp/refdata",
        parse_func=lambda msg: parse_beqs_response(msg, screen_name)
    )

    # send_request returns a list, but BEQS returns a single result
    # Aggregate all results in case of multiple messages
    if not results:
        return ScreenResult(screen_name=screen_name, errors=["No response received"])

    # Combine results from all response messages
    combined = ScreenResult(screen_name=screen_name)
    for result in results:
        if isinstance(result, ScreenResult):
            combined.securities.extend(result.securities)
            combined.field_data.extend(result.field_data)
            combined.errors.extend(result.errors)
            if result.columns and not combined.columns:
                combined.columns = result.columns

    return combined
