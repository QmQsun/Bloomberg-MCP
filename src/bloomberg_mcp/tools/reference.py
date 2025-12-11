"""Reference data tools for Bloomberg API.

Provides functions to retrieve current field values for securities.
"""

from typing import Any, Dict, List, Optional

from ..core.session import BloombergSession
from ..core.requests import build_reference_data_request
from ..core.responses import SecurityData, parse_reference_data_response


def get_reference_data(
    securities: List[str],
    fields: List[str],
    overrides: Optional[Dict[str, Any]] = None,
) -> List[SecurityData]:
    """Get current field values for securities.

    Args:
        securities: List of security identifiers (e.g., ["IBM US Equity", "AAPL US Equity"])
        fields: List of Bloomberg field mnemonics (e.g., ["PX_LAST", "NAME"])
        overrides: Optional field overrides as key-value pairs

    Returns:
        List of SecurityData objects containing field values for each security

    Example:
        >>> data = get_reference_data(
        ...     securities=["IBM US Equity", "AAPL US Equity"],
        ...     fields=["PX_LAST", "NAME", "MARKET_CAP"],
        ... )
        >>> for security in data:
        ...     print(f"{security.security}: {security.field_data}")
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the reference data service
    service = session.get_service("//blp/refdata")

    # Build the reference data request
    request = build_reference_data_request(
        service=service,
        securities=securities,
        fields=fields,
        overrides=overrides,
    )

    # Send the request and get response (with parser)
    results = session.send_request(
        request,
        service_name="//blp/refdata",
        parse_func=parse_reference_data_response
    )

    return results
