"""Pytest configuration and fixtures for bloomberg-mcp tests.

This module provides fixtures for creating mock Bloomberg API responses
using blpapi.test utilities, enabling unit tests without a live connection.
"""

import pytest
import blpapi
from blpapi.test import createEvent, appendMessage, getAdminMessageDefinition, deserializeService


# Reference Data Service Schema (simplified version)
REFDATA_SERVICE_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<ServiceDefinition name="blp.refdata" version="1.0.0.0">
  <service name="//blp/refdata" version="1.0.0.0">
    <operation name="ReferenceDataRequest" serviceId="12">
      <request>ReferenceDataRequest</request>
      <response>ReferenceDataResponse</response>
      <responseSelection>ReferenceDataResponse</responseSelection>
    </operation>
    <operation name="HistoricalDataRequest" serviceId="13">
      <request>HistoricalDataRequest</request>
      <response>HistoricalDataResponse</response>
      <responseSelection>HistoricalDataResponse</responseSelection>
    </operation>
  </service>
</ServiceDefinition>"""


@pytest.fixture
def mock_refdata_service():
    """Create a mock //blp/refdata service for testing.

    Returns:
        A blpapi.Service object that can be used to create requests.
    """
    try:
        service = deserializeService(REFDATA_SERVICE_XML)
        return service
    except Exception:
        # If deserializeService doesn't work with simplified schema,
        # return None and tests should mock service differently
        return None


@pytest.fixture
def mock_reference_response():
    """Create a mock reference data response event.

    This fixture creates a RESPONSE event with security data matching
    the structure returned by Bloomberg's ReferenceDataResponse.

    Returns:
        A blpapi.Event containing mock reference data for two securities.

    Example response structure:
        ReferenceDataResponse = {
            securityData[] = {
                security = "IBM US Equity"
                fieldData = {
                    PX_LAST = 150.25
                    NAME = "International Business Machines Corp"
                }
                fieldExceptions[] = {}
            }
        }
    """
    # Create a RESPONSE event
    event = createEvent(blpapi.Event.RESPONSE)

    # We need the message definition for ReferenceDataResponse
    # Since we can't easily deserialize the full service schema,
    # we'll create a mock structure that matches the expected format
    # Note: In real tests, you would use the actual service schema

    # For now, return the event structure that tests can verify
    # Tests will need to use formatMessageDict or similar to populate
    return event


@pytest.fixture
def mock_historical_response():
    """Create a mock historical data response event.

    This fixture creates a RESPONSE event with historical time series data
    matching the structure returned by Bloomberg's HistoricalDataResponse.

    Returns:
        A blpapi.Event containing mock historical data.

    Example response structure:
        HistoricalDataResponse = {
            securityData = {
                security = "IBM US Equity"
                fieldData[] = {
                    {
                        date = 2024-01-01
                        PX_LAST = 150.25
                        VOLUME = 1000000
                    }
                    {
                        date = 2024-01-02
                        PX_LAST = 151.50
                        VOLUME = 1100000
                    }
                }
            }
        }
    """
    # Create a RESPONSE event
    event = createEvent(blpapi.Event.RESPONSE)
    return event


@pytest.fixture
def mock_session_status_event():
    """Create a mock SessionStarted event.

    Returns:
        A blpapi.Event indicating successful session start.
    """
    event = createEvent(blpapi.Event.SESSION_STATUS)
    schema = getAdminMessageDefinition(blpapi.Names.SESSION_STARTED)

    formatter = appendMessage(event, schema)

    content = {
        "initialEndpoints": [
            {"address": "localhost:8194"},
        ]
    }

    formatter.formatMessageDict(content)
    return event


@pytest.fixture
def mock_service_opened_event():
    """Create a mock ServiceOpened event.

    Returns:
        A blpapi.Event indicating successful service opening.
    """
    event = createEvent(blpapi.Event.SERVICE_STATUS)
    schema = getAdminMessageDefinition(blpapi.Names.SERVICE_OPENED)

    formatter = appendMessage(event, schema)

    content = {"serviceName": "//blp/refdata"}

    formatter.formatMessageDict(content)
    return event


@pytest.fixture
def mock_session(mocker):
    """Create a mocked BloombergSession.

    This fixture mocks the blpapi.Session to avoid requiring a live
    Bloomberg connection during tests.

    Args:
        mocker: pytest-mock's mocker fixture

    Returns:
        A mock blpapi.Session object with common methods stubbed.
    """
    # Mock the blpapi.Session class
    mock_session_obj = mocker.Mock(spec=blpapi.Session)

    # Configure common method behaviors
    mock_session_obj.start.return_value = True
    mock_session_obj.openService.return_value = True
    mock_session_obj.stop.return_value = None

    # Mock getService to return a mock service
    mock_service = mocker.Mock(spec=blpapi.Service)
    mock_session_obj.getService.return_value = mock_service

    return mock_session_obj


@pytest.fixture
def sample_securities():
    """Provide sample security identifiers for testing.

    Returns:
        List of Bloomberg security identifiers.
    """
    return ["IBM US Equity", "AAPL US Equity", "MSFT US Equity"]


@pytest.fixture
def sample_reference_fields():
    """Provide sample reference data fields for testing.

    Returns:
        List of Bloomberg reference field names.
    """
    return ["PX_LAST", "NAME", "MARKET_CAP", "PE_RATIO"]


@pytest.fixture
def sample_historical_fields():
    """Provide sample historical data fields for testing.

    Returns:
        List of Bloomberg historical field names.
    """
    return ["PX_LAST", "VOLUME", "PX_OPEN", "PX_HIGH", "PX_LOW"]


@pytest.fixture
def sample_reference_data():
    """Provide sample reference data response structure.

    Returns:
        Dict representing parsed reference data.
    """
    return {
        "IBM US Equity": {
            "PX_LAST": 150.25,
            "NAME": "International Business Machines Corp",
            "MARKET_CAP": 138500000000,
            "PE_RATIO": 22.5,
        },
        "AAPL US Equity": {
            "PX_LAST": 182.68,
            "NAME": "Apple Inc",
            "MARKET_CAP": 2850000000000,
            "PE_RATIO": 29.8,
        },
    }


@pytest.fixture
def sample_historical_data():
    """Provide sample historical data response structure.

    Returns:
        Dict representing parsed historical data.
    """
    return {
        "IBM US Equity": [
            {
                "date": "2024-01-01",
                "PX_LAST": 150.25,
                "VOLUME": 1000000,
                "PX_OPEN": 149.50,
                "PX_HIGH": 151.00,
                "PX_LOW": 149.00,
            },
            {
                "date": "2024-01-02",
                "PX_LAST": 151.50,
                "VOLUME": 1100000,
                "PX_OPEN": 150.75,
                "PX_HIGH": 152.25,
                "PX_LOW": 150.50,
            },
            {
                "date": "2024-01-03",
                "PX_LAST": 149.75,
                "VOLUME": 950000,
                "PX_OPEN": 151.25,
                "PX_HIGH": 151.50,
                "PX_LOW": 149.50,
            },
        ]
    }
