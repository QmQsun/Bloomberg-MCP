"""Response dataclasses for Bloomberg API responses."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import blpapi


@dataclass
class SecurityData:
    """Represents reference data for a single security."""

    security: str
    fields: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class HistoricalDataPoint:
    """Represents a single historical data point."""

    date: datetime
    fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HistoricalData:
    """Represents historical data for a single security."""

    security: str
    data: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class IntradayBar:
    """Represents a single intraday bar."""

    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    num_events: int = 0


@dataclass
class IntradayBarData:
    """Represents intraday bar data for a single security."""

    security: str
    bars: List[IntradayBar] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# Field names used in Bloomberg API responses
SECURITY_DATA = blpapi.Name("securityData")
SECURITY = blpapi.Name("security")
FIELD_DATA = blpapi.Name("fieldData")
SECURITY_ERROR = blpapi.Name("securityError")
FIELD_EXCEPTIONS = blpapi.Name("fieldExceptions")
FIELD_ID = blpapi.Name("fieldId")
ERROR_INFO = blpapi.Name("errorInfo")
RESPONSE_ERROR = blpapi.Name("responseError")

# Historical data field names
HISTORICAL_DATA = blpapi.Name("historicalData")
FIELD_DATA_ARRAY = blpapi.Name("fieldData")
DATE = blpapi.Name("date")

# Intraday bar field names (using strings for toPy() compatibility)
BAR_DATA = "barData"
BAR_TICK_DATA = "barTickData"
TIME = "time"
OPEN = "open"
HIGH = "high"
LOW = "low"
CLOSE = "close"
VOLUME = "volume"
NUM_EVENTS = "numEvents"


def parse_reference_data_response(msg: blpapi.Message) -> List[SecurityData]:
    """
    Parse a ReferenceDataResponse message into SecurityData objects.

    Args:
        msg: Bloomberg API message containing reference data response

    Returns:
        List of SecurityData objects, one per security
    """
    result = []

    if msg.hasElement(RESPONSE_ERROR):
        error_msg = str(msg.getElement(RESPONSE_ERROR))
        # Return empty list with error - caller should handle
        return result

    securities = msg.getElement(SECURITY_DATA)
    num_securities = securities.numValues()

    for i in range(num_securities):
        security = securities.getValueAsElement(i)
        ticker = security.getElementAsString(SECURITY)

        sec_data = SecurityData(security=ticker)

        # Check for security-level errors
        if security.hasElement(SECURITY_ERROR):
            error = str(security.getElement(SECURITY_ERROR))
            sec_data.errors.append(error)
            result.append(sec_data)
            continue

        # Extract field data
        if security.hasElement(FIELD_DATA):
            fields = security.getElement(FIELD_DATA)
            num_elements = fields.numElements()
            for j in range(num_elements):
                field = fields.getElement(j)
                field_name = str(field.name())
                # Use toPy() to get the Python representation
                field_value = field.toPy()
                sec_data.fields[field_name] = field_value

        # Extract field exceptions (field-level errors)
        if security.hasElement(FIELD_EXCEPTIONS):
            field_exceptions = security.getElement(FIELD_EXCEPTIONS)
            num_exceptions = field_exceptions.numValues()
            for k in range(num_exceptions):
                field_exception = field_exceptions.getValueAsElement(k)
                field_id = field_exception.getElementAsString(FIELD_ID)
                error_info = str(field_exception.getElement(ERROR_INFO))
                sec_data.errors.append(f"{field_id}: {error_info}")

        result.append(sec_data)

    return result


def parse_historical_data_response(msg: blpapi.Message) -> List[HistoricalData]:
    """
    Parse a HistoricalDataResponse message into HistoricalData objects.

    Args:
        msg: Bloomberg API message containing historical data response

    Returns:
        List of HistoricalData objects, one per security
    """
    result = []

    if msg.hasElement(RESPONSE_ERROR):
        return result

    # Historical data response has a single securityData element (not an array)
    # Unlike reference data which has an array of securityData elements
    if not msg.hasElement(SECURITY_DATA):
        return result

    security_data = msg.getElement(SECURITY_DATA)
    ticker = security_data.getElementAsString(SECURITY)

    hist_data = HistoricalData(security=ticker)

    # Check for security-level errors
    if security_data.hasElement(SECURITY_ERROR):
        error = str(security_data.getElement(SECURITY_ERROR))
        hist_data.errors.append(error)
        result.append(hist_data)
        return result

    # Extract historical field data
    if security_data.hasElement(FIELD_DATA_ARRAY):
        field_data_array = security_data.getElement(FIELD_DATA_ARRAY)
        num_points = field_data_array.numValues()

        for j in range(num_points):
            field_data = field_data_array.getValueAsElement(j)
            # Convert to Python dict using toPy()
            data_point = field_data.toPy()
            hist_data.data.append(data_point)

    # Extract field exceptions
    if security_data.hasElement(FIELD_EXCEPTIONS):
        field_exceptions = security_data.getElement(FIELD_EXCEPTIONS)
        num_exceptions = field_exceptions.numValues()
        for k in range(num_exceptions):
            field_exception = field_exceptions.getValueAsElement(k)
            field_id = field_exception.getElementAsString(FIELD_ID)
            error_info = str(field_exception.getElement(ERROR_INFO))
            hist_data.errors.append(f"{field_id}: {error_info}")

    result.append(hist_data)

    return result


def parse_intraday_bar_response(msg: blpapi.Message) -> List[IntradayBar]:
    """
    Parse an IntradayBarResponse message into a list of IntradayBar objects.

    Args:
        msg: Bloomberg API message containing intraday bar response

    Returns:
        List of IntradayBar objects
    """
    result = []

    # Use toPy() to convert message to dict
    msg_dict = msg.toPy()

    if "responseError" in msg_dict:
        return result

    if BAR_DATA not in msg_dict:
        return result

    bar_data_dict = msg_dict[BAR_DATA]

    if BAR_TICK_DATA not in bar_data_dict:
        return result

    bars = bar_data_dict[BAR_TICK_DATA]

    for bar in bars:
        intraday_bar = IntradayBar(
            time=bar[TIME],
            open=float(bar[OPEN]),
            high=float(bar[HIGH]),
            low=float(bar[LOW]),
            close=float(bar[CLOSE]),
            volume=int(bar[VOLUME]),
            num_events=int(bar.get(NUM_EVENTS, 0)),
        )
        result.append(intraday_bar)

    return result


def parse_intraday_tick_response(msg: blpapi.Message) -> List[Dict[str, Any]]:
    """
    Parse an IntradayTickResponse message into a list of tick dictionaries.

    Args:
        msg: Bloomberg API message containing intraday tick response

    Returns:
        List of tick dictionaries with time, type, value, size fields
    """
    result = []

    # Use toPy() to convert message to dict
    msg_dict = msg.toPy()

    if "responseError" in msg_dict:
        return result

    tick_data = msg_dict.get("tickData", {})
    ticks = tick_data.get("tickData", [])

    for tick in ticks:
        result.append(tick)

    return result


def parse_instrument_search_response(msg: blpapi.Message) -> List[Dict[str, Any]]:
    """
    Parse an instrumentListResponse message into a list of search results.

    Args:
        msg: Bloomberg API message containing instrument search response

    Returns:
        List of dictionaries with security and description fields
    """
    result = []

    msg_dict = msg.toPy()

    if "responseError" in msg_dict:
        return result

    results = msg_dict.get("results", [])
    for item in results:
        result.append({
            "security": item.get("security", ""),
            "description": item.get("description", "")
        })

    return result


def parse_field_search_response(msg: blpapi.Message) -> List[Dict[str, Any]]:
    """
    Parse a FieldSearchResponse message into a list of field info dictionaries.

    Args:
        msg: Bloomberg API message containing field search response

    Returns:
        List of dictionaries with field information
    """
    result = []

    msg_dict = msg.toPy()

    if "responseError" in msg_dict:
        return result

    fields = msg_dict.get("fieldData", [])
    for field_info in fields:
        result.append(field_info)

    return result


def parse_field_info_response(msg: blpapi.Message) -> List[Dict[str, Any]]:
    """
    Parse a FieldInfoResponse message into a list of field metadata dictionaries.

    Args:
        msg: Bloomberg API message containing field info response

    Returns:
        List of dictionaries with detailed field metadata
    """
    result = []

    msg_dict = msg.toPy()

    if "responseError" in msg_dict:
        return result

    fields = msg_dict.get("fieldData", [])
    for field_info in fields:
        result.append(field_info)

    return result
