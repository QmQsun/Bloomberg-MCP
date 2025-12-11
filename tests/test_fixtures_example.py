"""Example tests demonstrating how to use the test fixtures.

This file contains working examples that show how to use the blpapi.test
utilities and the fixtures defined in conftest.py. These tests will pass
even without the actual bloomberg_mcp modules being implemented.
"""

import pytest
import blpapi
from blpapi.test import createEvent, appendMessage, getAdminMessageDefinition


class TestFixtureExamples:
    """Example tests showing fixture usage."""

    def test_sample_securities_fixture(self, sample_securities):
        """Example: Using the sample_securities fixture."""
        # The fixture provides a list of sample security identifiers
        assert isinstance(sample_securities, list)
        assert len(sample_securities) == 3
        assert "IBM US Equity" in sample_securities
        assert "AAPL US Equity" in sample_securities

    def test_sample_reference_fields_fixture(self, sample_reference_fields):
        """Example: Using the sample_reference_fields fixture."""
        # The fixture provides a list of common reference data fields
        assert isinstance(sample_reference_fields, list)
        assert "PX_LAST" in sample_reference_fields
        assert "NAME" in sample_reference_fields

    def test_sample_reference_data_fixture(self, sample_reference_data):
        """Example: Using the sample_reference_data fixture."""
        # The fixture provides sample parsed reference data
        assert isinstance(sample_reference_data, dict)
        assert "IBM US Equity" in sample_reference_data
        assert sample_reference_data["IBM US Equity"]["PX_LAST"] == 150.25

    def test_sample_historical_data_fixture(self, sample_historical_data):
        """Example: Using the sample_historical_data fixture."""
        # The fixture provides sample parsed historical data
        assert isinstance(sample_historical_data, dict)
        assert "IBM US Equity" in sample_historical_data
        data_points = sample_historical_data["IBM US Equity"]
        assert len(data_points) == 3
        assert data_points[0]["date"] == "2024-01-01"
        assert data_points[0]["PX_LAST"] == 150.25

    def test_mock_session_fixture(self, mock_session):
        """Example: Using the mock_session fixture."""
        # The fixture provides a mocked blpapi.Session
        assert mock_session is not None

        # Mock methods are already configured
        assert mock_session.start() is True
        assert mock_session.openService() is True

        # Can verify method calls
        mock_session.start.assert_called_once()

    def test_mock_session_status_event_fixture(self, mock_session_status_event):
        """Example: Using the mock_session_status_event fixture."""
        # The fixture provides a SessionStarted event
        assert mock_session_status_event is not None
        assert mock_session_status_event.eventType() == blpapi.Event.SESSION_STATUS

        # Can iterate over messages in the event
        messages = list(mock_session_status_event)
        assert len(messages) > 0

    def test_mock_service_opened_event_fixture(self, mock_service_opened_event):
        """Example: Using the mock_service_opened_event fixture."""
        # The fixture provides a ServiceOpened event
        assert mock_service_opened_event is not None
        assert mock_service_opened_event.eventType() == blpapi.Event.SERVICE_STATUS


class TestBlpapiTestUtilities:
    """Examples showing how to use blpapi.test utilities directly."""

    def test_create_session_started_event(self):
        """Example: Creating a SessionStarted event from scratch."""
        # Create a SESSION_STATUS event
        event = createEvent(blpapi.Event.SESSION_STATUS)

        # Get the message definition for SessionStarted
        schema = getAdminMessageDefinition(blpapi.Names.SESSION_STARTED)

        # Append a message to the event
        formatter = appendMessage(event, schema)

        # Format the message content
        content = {
            "initialEndpoints": [
                {"address": "localhost:8194"},
            ]
        }
        formatter.formatMessageDict(content)

        # Verify we can read the event
        assert event.eventType() == blpapi.Event.SESSION_STATUS
        messages = list(event)
        assert len(messages) == 1

        # Verify message content
        msg = messages[0]
        assert msg.messageType() == blpapi.Names.SESSION_STARTED

        # Convert message to Python dict and verify
        msg_dict = msg.toPy()
        assert "initialEndpoints" in msg_dict
        assert len(msg_dict["initialEndpoints"]) == 1
        assert msg_dict["initialEndpoints"][0]["address"] == "localhost:8194"

    def test_create_service_opened_event(self):
        """Example: Creating a ServiceOpened event from scratch."""
        event = createEvent(blpapi.Event.SERVICE_STATUS)
        schema = getAdminMessageDefinition(blpapi.Names.SERVICE_OPENED)
        formatter = appendMessage(event, schema)

        content = {"serviceName": "//blp/refdata"}
        formatter.formatMessageDict(content)

        # Verify
        messages = list(event)
        msg_dict = messages[0].toPy()
        assert msg_dict["serviceName"] == "//blp/refdata"

    def test_create_multiple_messages_in_event(self):
        """Example: Creating multiple messages in a single event."""
        event = createEvent(blpapi.Event.SERVICE_STATUS)
        schema = getAdminMessageDefinition(blpapi.Names.SERVICE_OPENED)

        # Add first message
        formatter1 = appendMessage(event, schema)
        formatter1.formatMessageDict({"serviceName": "//blp/refdata"})

        # Add second message
        formatter2 = appendMessage(event, schema)
        formatter2.formatMessageDict({"serviceName": "//blp/mktdata"})

        # Verify both messages are in the event
        messages = list(event)
        assert len(messages) == 2

        service_names = [msg.toPy()["serviceName"] for msg in messages]
        assert "//blp/refdata" in service_names
        assert "//blp/mktdata" in service_names

    def test_create_error_event(self):
        """Example: Creating an error event."""
        event = createEvent(blpapi.Event.SESSION_STATUS)
        schema = getAdminMessageDefinition(blpapi.Names.SESSION_STARTUP_FAILURE)
        formatter = appendMessage(event, schema)

        content = {
            "reason": {
                "source": "TestUtil",
                "errorCode": -1,
                "category": "CATEGORY",
                "description": "Connection failed",
                "subcategory": "SUBCATEGORY",
            }
        }
        formatter.formatMessageDict(content)

        # Verify error message
        messages = list(event)
        msg_dict = messages[0].toPy()
        assert msg_dict["reason"]["description"] == "Connection failed"
        assert msg_dict["reason"]["errorCode"] == -1


class TestMockingBestPractices:
    """Examples showing best practices for mocking."""

    def test_mock_with_pytest_mock(self, mocker):
        """Example: Using pytest-mock to create mocks."""
        # Create a mock for a specific class
        mock_service = mocker.Mock(spec=blpapi.Service)

        # Configure return values
        mock_request = mocker.Mock()
        mock_service.createRequest.return_value = mock_request

        # Use the mock
        request = mock_service.createRequest("ReferenceDataRequest")

        # Verify interactions
        mock_service.createRequest.assert_called_once_with("ReferenceDataRequest")
        assert request is mock_request

    def test_mock_with_side_effects(self, mocker):
        """Example: Using side effects for dynamic mock behavior."""
        # Create a mock that raises an exception on second call
        mock_session = mocker.Mock()
        mock_session.start.side_effect = [True, RuntimeError("Already started")]

        # First call succeeds
        assert mock_session.start() is True

        # Second call raises exception
        with pytest.raises(RuntimeError, match="Already started"):
            mock_session.start()

    def test_patch_decorator_example(self, mocker):
        """Example: Using patch to replace modules/classes."""
        # This would be used in actual tests to patch the Bloomberg session
        # mock_session_class = mocker.patch('bloomberg_mcp.core.session.BloombergSession')

        # For this example, just show the pattern
        mock_obj = mocker.Mock()
        mock_obj.method.return_value = "mocked result"

        assert mock_obj.method() == "mocked result"


class TestDataStructureExamples:
    """Examples showing expected Bloomberg response structures."""

    def test_reference_data_response_structure(self):
        """Example: Expected structure of reference data response."""
        # This is what a parsed reference data response should look like
        response = {
            "securityData": [
                {
                    "security": "IBM US Equity",
                    "fieldData": {
                        "PX_LAST": 150.25,
                        "NAME": "International Business Machines Corp",
                        "MARKET_CAP": 138500000000,
                    },
                    "fieldExceptions": [],
                }
            ]
        }

        # Verify structure
        assert "securityData" in response
        assert len(response["securityData"]) == 1

        security_data = response["securityData"][0]
        assert security_data["security"] == "IBM US Equity"
        assert "fieldData" in security_data
        assert security_data["fieldData"]["PX_LAST"] == 150.25

    def test_historical_data_response_structure(self):
        """Example: Expected structure of historical data response."""
        response = {
            "securityData": {
                "security": "IBM US Equity",
                "fieldData": [
                    {
                        "date": "2024-01-01",
                        "PX_LAST": 150.25,
                        "VOLUME": 1000000,
                    },
                    {
                        "date": "2024-01-02",
                        "PX_LAST": 151.50,
                        "VOLUME": 1100000,
                    },
                ],
            }
        }

        # Verify structure
        assert "securityData" in response
        security_data = response["securityData"]
        assert security_data["security"] == "IBM US Equity"
        assert len(security_data["fieldData"]) == 2
        assert security_data["fieldData"][0]["date"] == "2024-01-01"
