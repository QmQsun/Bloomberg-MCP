"""Search tools for Bloomberg API.

Provides functions to search for securities and fields.
"""

from typing import List, Optional

from ..core.session import BloombergSession
from ..core.requests import build_instrument_search_request, build_field_search_request, build_field_info_request
from ..core.responses import parse_instrument_search_response, parse_field_search_response, parse_field_info_response


def search_securities(
    query: str,
    max_results: int = 10,
    yellow_key: Optional[str] = None,
) -> List[dict]:
    """Search for securities by name/ticker.

    Args:
        query: Search query (partial ticker, company name, ISIN, etc.)
        max_results: Maximum number of results to return (default: 10)
        yellow_key: Optional Bloomberg yellow key filter
                   ("Govt", "Corp", "Mtge", "M-Mkt", "Muni", "Pfd", "Equity",
                    "Comdty", "Index", "Curncy")

    Returns:
        List of security dictionaries with keys like:
        - security: Full Bloomberg identifier
        - description: Security description

    Example:
        >>> results = search_securities(
        ...     query="Apple",
        ...     max_results=5,
        ...     yellow_key="Equity",
        ... )
        >>> for result in results:
        ...     print(f"{result['security']}: {result['description']}")
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the instruments service
    service = session.get_service("//blp/instruments")

    # Build the instrument search request
    request = build_instrument_search_request(
        service=service,
        query=query,
        max_results=max_results,
        yellow_key=yellow_key,
    )

    # Send the request and get response (with parser)
    results = session.send_request(
        request,
        service_name="//blp/instruments",
        parse_func=parse_instrument_search_response
    )

    # Results is a list of lists, flatten it
    flattened = []
    for item in results:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)

    return flattened


def search_fields(
    query: str,
    field_type: Optional[str] = None,
) -> List[dict]:
    """Search for Bloomberg fields.

    Args:
        query: Search query (partial field mnemonic or description)
        field_type: Optional field type to EXCLUDE from results
                   ("Static", "RealTime", "Historical")

    Returns:
        List of field dictionaries with keys like:
        - id: Field mnemonic (e.g., "PX_LAST")
        - mnemonic: Field mnemonic (same as id)
        - description: Field description
        - datatype: Field data type
        - categoryName: Field category
        - documentation: Field documentation (if requested)

    Example:
        >>> results = search_fields(
        ...     query="last price",
        ...     field_type="Static",  # Exclude static fields
        ... )
        >>> for result in results:
        ...     print(f"{result.get('id', result.get('mnemonic'))}: {result['description']}")
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the API fields service
    service = session.get_service("//blp/apiflds")

    # Build the field search request
    request = build_field_search_request(
        service=service,
        search_spec=query,
        field_type=field_type,
        return_field_documentation=False,
    )

    # Send the request and get response (with parser)
    results = session.send_request(
        request,
        service_name="//blp/apiflds",
        parse_func=parse_field_search_response
    )

    # Results is a list of lists, flatten it
    flattened = []
    for item in results:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)

    return flattened


def get_field_info(
    field_ids: List[str],
    return_documentation: bool = True,
) -> List[dict]:
    """Get detailed information about specific Bloomberg fields.

    Args:
        field_ids: List of field mnemonics (e.g., ["PX_LAST", "VOLUME", "NAME"])
        return_documentation: Whether to return detailed field documentation

    Returns:
        List of field metadata dictionaries with keys like:
        - id: Field mnemonic (e.g., "PX_LAST")
        - mnemonic: Field mnemonic (same as id)
        - description: Field description
        - datatype: Field data type
        - categoryName: Field category
        - documentation: Field documentation (if requested)
        - ftype: Field type (Static, RealTime, Historical)

    Example:
        >>> results = get_field_info(
        ...     field_ids=["PX_LAST", "VOLUME"],
        ...     return_documentation=True,
        ... )
        >>> for result in results:
        ...     print(f"{result.get('id', result.get('mnemonic'))}: {result['description']}")
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the API fields service
    service = session.get_service("//blp/apiflds")

    # Build the field info request
    request = build_field_info_request(
        service=service,
        field_ids=field_ids,
        return_field_documentation=return_documentation,
    )

    # Send the request and get response (with parser)
    results = session.send_request(
        request,
        service_name="//blp/apiflds",
        parse_func=parse_field_info_response
    )

    # Results is a list of lists, flatten it
    flattened = []
    for item in results:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)

    return flattened
