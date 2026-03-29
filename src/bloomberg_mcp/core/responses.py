"""Response dataclasses for Bloomberg API responses."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import blpapi

logger = logging.getLogger(__name__)


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
class ScreenResult:
    """Represents results from a Bloomberg equity screen (BEQS).

    Contains the list of securities matching the screen criteria along with
    any output fields defined in the screen.
    """

    screen_name: str
    securities: List[str] = field(default_factory=list)
    field_data: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class StudyDataPoint:
    """Represents a single technical analysis data point from //blp/tasvc."""

    date: Any  # datetime or string
    values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StudyResult:
    """Represents technical analysis results from //blp/tasvc."""

    security: str
    study: str
    data: List[StudyDataPoint] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


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
        logger.error("Reference data response error: %s", error_msg)
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
        logger.error("Historical data response error: %s", msg.getElement(RESPONSE_ERROR))
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
        logger.error("Intraday bar response error: %s", msg_dict["responseError"])
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
        logger.error("Intraday tick response error: %s", msg_dict["responseError"])
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
        logger.error("Instrument search response error: %s", msg_dict["responseError"])
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
        logger.error("Field info response error: %s", msg_dict["responseError"])
        return result

    fields = msg_dict.get("fieldData", [])
    for field_info in fields:
        result.append(field_info)

    return result


def parse_beqs_response(msg: blpapi.Message, screen_name: str) -> ScreenResult:
    """
    Parse a BeqsResponse message into a ScreenResult object.

    Args:
        msg: Bloomberg API message containing BEQS response
        screen_name: Name of the screen that was run

    Returns:
        ScreenResult object with securities and field data
    """
    result = ScreenResult(screen_name=screen_name)

    # Check for response-level errors
    if msg.hasElement(RESPONSE_ERROR):
        error_elem = msg.getElement(RESPONSE_ERROR)
        result.errors.append(str(error_elem))
        return result

    # Use toPy() to convert message to dict
    msg_dict = msg.toPy()

    if "responseError" in msg_dict:
        result.errors.append(str(msg_dict["responseError"]))
        return result

    # Handle nested data structure - response may have data.securityData
    data = msg_dict.get("data", msg_dict)
    security_data = data.get("securityData", [])

    if not isinstance(security_data, list):
        return result

    # Extract columns from first security's fieldData
    if security_data and "fieldData" in security_data[0]:
        result.columns = list(security_data[0]["fieldData"].keys())

    # Extract securities and field data
    for sec in security_data:
        ticker = sec.get("security", "")
        if ticker:
            result.securities.append(ticker)

            # Include full record with security and fields
            record = {"security": ticker}
            field_data = sec.get("fieldData", {})
            record.update(field_data)

            # Include any field exceptions
            if sec.get("fieldExceptions"):
                record["_fieldExceptions"] = sec["fieldExceptions"]

            result.field_data.append(record)

    return result


def parse_study_response(msg: blpapi.Message) -> List[StudyDataPoint]:
    """Parse a studyResponse from //blp/tasvc into StudyDataPoint objects.

    The tasvc response structure:
        studyData[] = {
            date = 2024-01-02
            RSI = 55.3
        }

    Args:
        msg: Bloomberg API message containing study response

    Returns:
        List of StudyDataPoint objects with date and computed values
    """
    result = []

    # Use toPy() — the study response is straightforward
    msg_dict = msg.toPy()

    if "responseError" in msg_dict:
        logger.error("Study response error: %s", msg_dict["responseError"])
        return result

    # studyData is the array of data points
    study_data = msg_dict.get("studyData", [])

    for point in study_data:
        date_val = point.get("date", None)
        # All non-date keys are study output values
        values = {k: v for k, v in point.items() if k != "date"}
        result.append(StudyDataPoint(date=date_val, values=values))

    return result
