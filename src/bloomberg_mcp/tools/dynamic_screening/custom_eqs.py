"""CustomEqsRequest implementation for dynamic screening.

CustomEqsRequest is a Bloomberg API request type that:
- Takes a list of securities and fields as input
- Returns field data for each security
- Supports PARTIAL_RESPONSE events (batches of ~10 securities)

This differs from BeqsRequest which runs saved screens.
CustomEqsRequest is essentially like ReferenceDataRequest but through the EQS engine,
which may support different fields (like NEWS_SENTIMENT).

Usage:
    >>> from bloomberg_mcp.tools.dynamic_screening.custom_eqs import get_custom_eqs_data
    >>>
    >>> data = get_custom_eqs_data(
    ...     securities=["AAPL US Equity", "MSFT US Equity"],
    ...     fields=["PX_LAST", "NEWS_SENTIMENT", "VOLUME"],
    ... )
    >>> for rec in data:
    ...     print(f"{rec.security}: {rec.fields}")
"""

import logging
from typing import Any, Dict, List, Optional

import blpapi

from ...core.session import BloombergSession
from .models import SecurityRecord

logger = logging.getLogger(__name__)

# Pre-defined Name objects for CustomEqsRequest
SECURITIES = blpapi.Name("securities")
FIELDS = blpapi.Name("fields")
DATA = blpapi.Name("data")
SECURITY_DATA = blpapi.Name("securityData")
SECURITY = blpapi.Name("security")
FIELD_DATA = blpapi.Name("fieldData")
RESPONSE_ERROR = blpapi.Name("responseError")


def build_custom_eqs_request(
    service: blpapi.Service,
    securities: List[str],
    fields: List[str],
) -> blpapi.Request:
    """Build a CustomEqsRequest for fetching field data.

    Args:
        service: The opened //blp/refdata service
        securities: List of security identifiers
        fields: List of Bloomberg field mnemonics

    Returns:
        Configured blpapi.Request object

    Example:
        >>> service = session.getService("//blp/refdata")
        >>> request = build_custom_eqs_request(
        ...     service,
        ...     ["AAPL US Equity", "MSFT US Equity"],
        ...     ["PX_LAST", "NEWS_SENTIMENT"],
        ... )
    """
    request = service.createRequest("CustomEqsRequest")

    # Add securities
    securities_elem = request.getElement(SECURITIES)
    for sec in securities:
        securities_elem.appendValue(sec)

    # Add fields
    fields_elem = request.getElement(FIELDS)
    for field in fields:
        fields_elem.appendValue(field)

    return request


def parse_custom_eqs_response(msg: blpapi.Message) -> List[SecurityRecord]:
    """Parse a CustomEqsResponse message into SecurityRecord objects.

    CustomEqsResponse messages contain a data.securityData array with:
    - security: The security identifier
    - fieldData: Dict of field name -> value

    Args:
        msg: Bloomberg API message (CustomEqsResponse)

    Returns:
        List of SecurityRecord objects
    """
    results = []

    # Check for response error
    if msg.hasElement(RESPONSE_ERROR):
        error = str(msg.getElement(RESPONSE_ERROR))
        logger.error(f"CustomEqsResponse error: {error}")
        return results

    # Navigate to data.securityData
    if not msg.hasElement(DATA):
        return results

    data_elem = msg.getElement(DATA)
    if not data_elem.hasElement(SECURITY_DATA):
        return results

    security_data = data_elem.getElement(SECURITY_DATA)

    for i in range(security_data.numValues()):
        sec_elem = security_data.getValueAsElement(i)
        security = sec_elem.getElementAsString(SECURITY)

        fields_dict: Dict[str, Any] = {}

        if sec_elem.hasElement(FIELD_DATA):
            field_data = sec_elem.getElement(FIELD_DATA)
            num_fields = field_data.numElements()

            for j in range(num_fields):
                field_elem = field_data.getElement(j)
                field_name = str(field_elem.name())

                # Use toPy() for proper type conversion
                try:
                    field_value = field_elem.toPy()
                    fields_dict[field_name] = field_value
                except Exception as e:
                    logger.warning(f"Failed to parse field {field_name}: {e}")

        results.append(SecurityRecord(security=security, fields=fields_dict))

    return results


def get_custom_eqs_data(
    securities: List[str],
    fields: List[str],
    timeout_ms: int = 60000,
) -> List[SecurityRecord]:
    """Get field data for securities using CustomEqsRequest.

    This function handles the Bloomberg session management and
    PARTIAL_RESPONSE events automatically.

    Args:
        securities: List of security identifiers
        fields: List of Bloomberg field mnemonics
        timeout_ms: Timeout in milliseconds for response

    Returns:
        List of SecurityRecord objects with field data

    Raises:
        RuntimeError: If Bloomberg connection fails

    Example:
        >>> data = get_custom_eqs_data(
        ...     securities=["AAPL US Equity", "MSFT US Equity"],
        ...     fields=["PX_LAST", "CHG_PCT_1D", "NEWS_SENTIMENT"],
        ... )
        >>> for rec in data:
        ...     print(f"{rec.security}: ${rec.PX_LAST:.2f}")
    """
    # Get Bloomberg session
    session = BloombergSession.get_instance()

    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get service and build request
    service = session.get_service("//blp/refdata")
    request = build_custom_eqs_request(service, securities, fields)

    # Send request - use internal session for direct control
    internal_session = session._session
    internal_session.sendRequest(request)

    # Collect results from PARTIAL_RESPONSE and RESPONSE events
    results: List[SecurityRecord] = []
    done = False

    while not done:
        event = internal_session.nextEvent(timeout=timeout_ms)
        event_type = event.eventType()

        for msg in event:
            msg_type = str(msg.messageType())

            if msg_type == "CustomEqsResponse":
                parsed = parse_custom_eqs_response(msg)
                results.extend(parsed)

                # RESPONSE (type 5) means we're done
                # PARTIAL_RESPONSE (type 6) means more data coming
                if event_type == blpapi.Event.RESPONSE:
                    done = True

            elif event_type == blpapi.Event.REQUEST_STATUS:
                logger.warning(f"Request status: {msg}")
                done = True

            elif event_type == blpapi.Event.TIMEOUT:
                logger.error("CustomEqsRequest timed out")
                done = True

    logger.info(f"CustomEqsRequest returned {len(results)} securities")
    return results


def get_universe_from_screen(
    screen_name: str,
    screen_type: str = "PRIVATE",
) -> List[str]:
    """Get list of securities from a saved Bloomberg EQS screen.

    This is a convenience function that wraps the existing run_screen
    function from the screening module.

    Note: Bloomberg screens often return tickers without the " Equity" suffix
    (e.g., "TOELY US" instead of "TOELY US Equity"). This function normalizes
    them to the full Bloomberg identifier format.

    Args:
        screen_name: Name of the saved screen
        screen_type: "PRIVATE" or "GLOBAL"

    Returns:
        List of security identifiers in full Bloomberg format

    Example:
        >>> securities = get_universe_from_screen("Japan_Liquid_ADRs")
        >>> print(f"Found {len(securities)} ADRs")
    """
    from ..screening import run_screen

    result = run_screen(screen_name, screen_type)

    # Normalize security identifiers to full Bloomberg format
    # Screens often return "TOELY US" instead of "TOELY US Equity"
    normalized = []
    for sec in result.securities:
        if not sec.endswith(("Equity", "Index", "Comdty", "Curncy", "Corp", "Govt")):
            # Assume equity if no asset class suffix
            sec = f"{sec} Equity"
        normalized.append(sec)

    return normalized


def get_index_constituents(
    index_ticker: str,
) -> List[str]:
    """Get constituent securities of an index.

    Uses Bloomberg's INDX_MEMBERS field to get index constituents.

    Args:
        index_ticker: Index identifier (e.g., "SPX Index", "NKY Index")

    Returns:
        List of security identifiers

    Example:
        >>> constituents = get_index_constituents("SPX Index")
        >>> print(f"SPX has {len(constituents)} members")
    """
    from ..reference import get_reference_data

    # Get index members
    results = get_reference_data([index_ticker], ["INDX_MEMBERS"])

    if not results or not results[0].fields:
        logger.warning(f"No constituents found for {index_ticker}")
        return []

    members = results[0].fields.get("INDX_MEMBERS", [])

    # INDX_MEMBERS returns a list of dicts with "Member Ticker and Exchange Code"
    securities = []
    if isinstance(members, list):
        for member in members:
            if isinstance(member, dict):
                ticker = member.get("Member Ticker and Exchange Code")
                if ticker:
                    securities.append(ticker)
            elif isinstance(member, str):
                securities.append(member)

    return securities
