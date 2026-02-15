"""Bloomberg API Request Builder Module.

This module provides functions to build blpapi Request objects using the fromPy()
pattern for clean dict-based request building. All Name objects are pre-defined at
module level for performance.

Based on Bloomberg API examples:
- ReferenceDataRequests.py
- HistoricalDataRequest.py
- IntradayBarRequests.py
- IntradayTickRequests.py
- InstrumentListRequests.py
- FieldSearchRequests.py
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

import blpapi

# Pre-defined Name objects for performance
# Reference Data Request Names
SECURITIES = blpapi.Name("securities")
FIELDS = blpapi.Name("fields")
OVERRIDES = blpapi.Name("overrides")
FIELD_ID = blpapi.Name("fieldId")
VALUE = blpapi.Name("value")

# Historical Data Request Names
PERIODICITY_ADJUSTMENT = blpapi.Name("periodicityAdjustment")
PERIODICITY_SELECTION = blpapi.Name("periodicitySelection")
START_DATE = blpapi.Name("startDate")
END_DATE = blpapi.Name("endDate")
MAX_DATA_POINTS = blpapi.Name("maxDataPoints")
RETURN_EIDS = blpapi.Name("returnEids")

# Intraday Bar Request Names
SECURITY = blpapi.Name("security")
EVENT_TYPE = blpapi.Name("eventType")
INTERVAL = blpapi.Name("interval")
START_DATE_TIME = blpapi.Name("startDateTime")
END_DATE_TIME = blpapi.Name("endDateTime")
GAP_FILL_INITIAL_BAR = blpapi.Name("gapFillInitialBar")

# Intraday Tick Request Names
EVENT_TYPES = blpapi.Name("eventTypes")
INCLUDE_CONDITION_CODES = blpapi.Name("includeConditionCodes")

# Instrument Search Request Names
QUERY = blpapi.Name("query")
MAX_RESULTS = blpapi.Name("maxResults")
YELLOW_KEY_FILTER = blpapi.Name("yellowKeyFilter")

# Field Search Request Names
SEARCH_SPEC = blpapi.Name("searchSpec")
FIELD_TYPE = blpapi.Name("fieldType")
RETURN_FIELD_DOC = blpapi.Name("returnFieldDocumentation")
EXCLUDE = blpapi.Name("exclude")

# Field Info Request Names
ID = blpapi.Name("id")

# BEQS (Bloomberg Equity Screening) Request Names
SCREEN_NAME = blpapi.Name("screenName")
SCREEN_TYPE = blpapi.Name("screenType")
GROUP = blpapi.Name("Group")
LANGUAGE_ID = blpapi.Name("languageId")


def build_reference_data_request(
    service: blpapi.Service,
    securities: List[str],
    fields: List[str],
    overrides: Optional[Dict[str, Any]] = None,
) -> blpapi.Request:
    """Build a ReferenceDataRequest for retrieving static reference data.

    This request retrieves current snapshot data for securities, such as pricing,
    fundamentals, and other static data fields.

    Args:
        service: The opened //blp/refdata service
        securities: List of security identifiers (e.g., ["IBM US Equity", "AAPL US Equity"])
        fields: List of field mnemonics to retrieve (e.g., ["PX_LAST", "VOLUME"])
        overrides: Optional dict of field overrides {field_id: value}

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> service = session.getService("//blp/refdata")
        >>> request = build_reference_data_request(
        ...     service,
        ...     ["IBM US Equity"],
        ...     ["PX_LAST", "VOLUME"],
        ...     overrides={"PRICING_SOURCE": "BGN"}
        ... )
    """
    request = service.createRequest("ReferenceDataRequest")

    request_dict = {
        SECURITIES: securities,
        FIELDS: fields,
    }

    if overrides:
        request_dict[OVERRIDES] = [
            {FIELD_ID: field_id, VALUE: value}
            for field_id, value in overrides.items()
        ]

    request.fromPy(request_dict)
    return request


def build_historical_data_request(
    service: blpapi.Service,
    securities: List[str],
    fields: List[str],
    start_date: str,
    end_date: str,
    periodicity: str = "DAILY",
    periodicity_adjustment: str = "ACTUAL",
    max_data_points: Optional[int] = None,
    return_eids: bool = False,
) -> blpapi.Request:
    """Build a HistoricalDataRequest for time series data.

    This request retrieves historical time series data for securities over a
    specified date range with configurable periodicity.

    Args:
        service: The opened //blp/refdata service
        securities: List of security identifiers
        fields: List of field mnemonics to retrieve
        start_date: Start date in YYYYMMDD format (e.g., "20200101")
        end_date: End date in YYYYMMDD format (e.g., "20201231")
        periodicity: Data frequency - one of:
            "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "SEMI_ANNUALLY", "YEARLY"
        periodicity_adjustment: How to adjust for corporate actions - one of:
            "ACTUAL", "CALENDAR", "FISCAL"
        max_data_points: Maximum number of data points to return (optional)
        return_eids: Whether to return entitlement identifiers

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> service = session.getService("//blp/refdata")
        >>> request = build_historical_data_request(
        ...     service,
        ...     ["IBM US Equity"],
        ...     ["PX_LAST", "VOLUME"],
        ...     "20240101",
        ...     "20241231",
        ...     periodicity="MONTHLY"
        ... )
    """
    request = service.createRequest("HistoricalDataRequest")

    request_dict = {
        SECURITIES: securities,
        FIELDS: fields,
        PERIODICITY_ADJUSTMENT: periodicity_adjustment,
        PERIODICITY_SELECTION: periodicity,
        START_DATE: start_date,
        END_DATE: end_date,
        RETURN_EIDS: return_eids,
    }

    if max_data_points is not None:
        request_dict[MAX_DATA_POINTS] = max_data_points

    request.fromPy(request_dict)
    return request


def build_intraday_bar_request(
    service: blpapi.Service,
    security: str,
    start: datetime,
    end: datetime,
    interval: int = 5,
    event_type: str = "TRADE",
    gap_fill_initial_bar: bool = False,
) -> blpapi.Request:
    """Build an IntradayBarRequest for intraday bar data.

    This request retrieves aggregated bar data (OHLCV) for a single security
    at specified time intervals within a datetime range. Note that only one
    security can be requested per call.

    Args:
        service: The opened //blp/refdata service
        security: Single security identifier (e.g., "IBM US Equity")
        start: Start datetime (must be in GMT/UTC)
        end: End datetime (must be in GMT/UTC)
        interval: Bar interval in minutes (1-1440). Common values:
            1, 5, 15, 30, 60 (hourly), 1440 (daily)
        event_type: Type of event - one of:
            "TRADE" - Trade ticks
            "BID" - Bid ticks
            "ASK" - Ask ticks
            "BID_BEST" - Best bid
            "ASK_BEST" - Best ask
            "BEST_BID" - alias for BID_BEST
            "BEST_ASK" - alias for ASK_BEST
        gap_fill_initial_bar: Whether to fill initial bar with previous values

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> from datetime import datetime
        >>> service = session.getService("//blp/refdata")
        >>> request = build_intraday_bar_request(
        ...     service,
        ...     "IBM US Equity",
        ...     datetime(2024, 1, 2, 14, 30),  # GMT
        ...     datetime(2024, 1, 2, 21, 0),   # GMT
        ...     interval=15,
        ...     event_type="TRADE"
        ... )
    """
    request = service.createRequest("IntradayBarRequest")

    request_dict = {
        SECURITY: security,
        EVENT_TYPE: event_type,
        INTERVAL: interval,
        START_DATE_TIME: start,
        END_DATE_TIME: end,
    }

    if gap_fill_initial_bar:
        request_dict[GAP_FILL_INITIAL_BAR] = gap_fill_initial_bar

    request.fromPy(request_dict)
    return request


def build_intraday_tick_request(
    service: blpapi.Service,
    security: str,
    start: datetime,
    end: datetime,
    event_types: List[str] = None,
    include_condition_codes: bool = False,
) -> blpapi.Request:
    """Build an IntradayTickRequest for tick-level data.

    This request retrieves individual tick data for a single security within
    a datetime range. Each tick represents an individual market event (trade, quote, etc.).

    Args:
        service: The opened //blp/refdata service
        security: Single security identifier (e.g., "IBM US Equity")
        start: Start datetime (must be in GMT/UTC)
        end: End datetime (must be in GMT/UTC)
        event_types: List of event types to retrieve. Can include:
            "TRADE" - Trade ticks
            "BID" - Bid ticks
            "ASK" - Ask ticks
            "BID_BEST" - Best bid
            "ASK_BEST" - Best ask
            "MID_PRICE" - Mid price
            "AT_TRADE" - Automated trade
            "BEST_BID" - alias for BID_BEST
            "BEST_ASK" - alias for ASK_BEST
            If None, defaults to ["TRADE"]
        include_condition_codes: Whether to include condition codes in response

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> from datetime import datetime
        >>> service = session.getService("//blp/refdata")
        >>> request = build_intraday_tick_request(
        ...     service,
        ...     "IBM US Equity",
        ...     datetime(2024, 1, 2, 14, 30),  # GMT
        ...     datetime(2024, 1, 2, 15, 0),   # GMT
        ...     event_types=["TRADE", "BID", "ASK"]
        ... )
    """
    request = service.createRequest("IntradayTickRequest")

    # Default to TRADE if no event types specified
    if event_types is None:
        event_types = ["TRADE"]

    request_dict = {
        SECURITY: security,
        EVENT_TYPES: event_types,
        START_DATE_TIME: start,
        END_DATE_TIME: end,
    }

    if include_condition_codes:
        request_dict[INCLUDE_CONDITION_CODES] = include_condition_codes

    request.fromPy(request_dict)
    return request


def build_instrument_search_request(
    service: blpapi.Service,
    query: str,
    max_results: int = 10,
    yellow_key: Optional[str] = None,
) -> blpapi.Request:
    """Build an instrumentListRequest for searching securities.

    This request searches for securities matching a query string and returns
    security identifiers and descriptions. Useful for security lookup and validation.

    Args:
        service: The opened //blp/instruments service
        query: Search query string (e.g., "IBM", "Apple", "US Treasury")
        max_results: Maximum number of results to return (default: 10)
        yellow_key: Optional market sector filter - one of:
            "Govt" - Government
            "Corp" - Corporate
            "Mtge" - Mortgage
            "M-Mkt" - Money Market
            "Muni" - Municipal
            "Pfd" - Preferred
            "Equity" - Equity
            "Comdty" - Commodity
            "Index" - Index
            "Curncy" - Currency

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> service = session.getService("//blp/instruments")
        >>> request = build_instrument_search_request(
        ...     service,
        ...     "IBM",
        ...     max_results=20,
        ...     yellow_key="Equity"
        ... )
    """
    request = service.createRequest("instrumentListRequest")

    request_dict = {
        QUERY: query,
        MAX_RESULTS: max_results,
    }

    if yellow_key is not None:
        request_dict[YELLOW_KEY_FILTER] = yellow_key

    request.fromPy(request_dict)
    return request


def build_field_search_request(
    service: blpapi.Service,
    search_spec: str,
    field_type: Optional[str] = None,
    return_field_documentation: bool = False,
) -> blpapi.Request:
    """Build a FieldSearchRequest for searching Bloomberg fields.

    This request searches for Bloomberg data fields matching a search specification
    and returns field metadata. Useful for discovering available fields.

    Args:
        service: The opened //blp/apiflds service
        search_spec: Search specification string (e.g., "last price", "volume")
        field_type: Optional field type to filter results. Can be:
            "Static" - Static reference data
            "RealTime" - Real-time streaming data
            "Historical" - Historical time series data
            If provided, this type will be EXCLUDED from results
        return_field_documentation: Whether to return detailed field documentation

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> service = session.getService("//blp/apiflds")
        >>> request = build_field_search_request(
        ...     service,
        ...     "last price",
        ...     field_type="Static",  # Exclude static fields
        ...     return_field_documentation=True
        ... )
    """
    request = service.createRequest("FieldSearchRequest")

    request_dict = {
        SEARCH_SPEC: search_spec,
        RETURN_FIELD_DOC: return_field_documentation,
    }

    # Note: field_type is used as an EXCLUSION filter
    if field_type is not None:
        request_dict[EXCLUDE] = {FIELD_TYPE: field_type}

    request.fromPy(request_dict)
    return request


def build_field_info_request(
    service: blpapi.Service,
    field_ids: List[str],
    return_field_documentation: bool = True,
) -> blpapi.Request:
    """Build a FieldInfoRequest for retrieving detailed field metadata.

    This request retrieves detailed information about specific Bloomberg fields,
    including descriptions, data types, categories, and documentation.

    Args:
        service: The opened //blp/apiflds service
        field_ids: List of field mnemonics (e.g., ["PX_LAST", "VOLUME", "NAME"])
        return_field_documentation: Whether to return detailed field documentation

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> service = session.getService("//blp/apiflds")
        >>> request = build_field_info_request(
        ...     service,
        ...     ["PX_LAST", "VOLUME", "NAME"],
        ...     return_field_documentation=True
        ... )
    """
    request = service.createRequest("FieldInfoRequest")

    request_dict = {
        ID: field_ids,
        RETURN_FIELD_DOC: return_field_documentation,
    }

    request.fromPy(request_dict)
    return request


def build_beqs_request(
    service: blpapi.Service,
    screen_name: str,
    screen_type: str = "PRIVATE",
    group: Optional[str] = None,
    language_id: Optional[str] = None,
) -> blpapi.Request:
    """Build a BeqsRequest for running Bloomberg equity screens.

    This request runs a pre-saved equity screen from Bloomberg EQS and returns
    the list of securities matching the screen criteria along with any output
    fields defined in the screen.

    Args:
        service: The opened //blp/refdata service
        screen_name: Name of the saved screen (e.g., "Japan_ADR_Universe")
        screen_type: Type of screen - one of:
            "PRIVATE" - User's personal saved screens (default)
            "GLOBAL" - Bloomberg's pre-defined example screens
        group: Optional folder/group name if screen is organized in folders
        language_id: Optional language identifier for localized screens

    Returns:
        A configured blpapi.Request object ready to send

    Example:
        >>> service = session.getService("//blp/refdata")
        >>> request = build_beqs_request(
        ...     service,
        ...     "Japan_ADR_Universe",
        ...     screen_type="PRIVATE"
        ... )

    Note:
        Screens must be created and saved in Bloomberg Terminal EQS <GO>
        before they can be accessed via API. The screen name must match
        exactly as saved.
    """
    request = service.createRequest("BeqsRequest")

    # Build request using set() since BeqsRequest doesn't support fromPy well
    request.set(SCREEN_NAME, screen_name)
    request.set(SCREEN_TYPE, screen_type)

    if group is not None:
        request.set(GROUP, group)

    if language_id is not None:
        request.set(LANGUAGE_ID, language_id)

    return request


__all__ = [
    "build_reference_data_request",
    "build_historical_data_request",
    "build_intraday_bar_request",
    "build_intraday_tick_request",
    "build_instrument_search_request",
    "build_field_search_request",
    "build_field_info_request",
    "build_beqs_request",
]
