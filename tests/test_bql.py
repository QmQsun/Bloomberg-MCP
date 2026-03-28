"""Tests for the BQL tool."""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from bloomberg_mcp.models.inputs import BQLInput
from bloomberg_mcp.models.enums import ResponseFormat
from bloomberg_mcp.handlers.bql import _parse_bql_results


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestBQLInput:
    def test_valid(self):
        inp = BQLInput(expression="get(px_last()) for(['AAPL US Equity'])")
        assert "px_last" in inp.expression

    def test_empty_expression_rejected(self):
        with pytest.raises(Exception):
            BQLInput(expression="")


class TestParseBqlResults:
    """Test the BQL result parser."""

    def test_list_results(self):
        raw = [{"results": [{"security": "AAPL", "PX_LAST": 150.0}]}]
        parsed = _parse_bql_results(raw)
        assert parsed["total_records"] == 1
        assert parsed["records"][0]["PX_LAST"] == 150.0

    def test_nested_dict_results(self):
        raw = [{"results": {"data": [{"security": "AAPL", "val": 100}]}}]
        parsed = _parse_bql_results(raw)
        assert parsed["total_records"] == 1

    def test_error_response(self):
        raw = [{"responseError": {"message": "Invalid expression"}}]
        parsed = _parse_bql_results(raw)
        assert len(parsed["errors"]) == 1
        assert parsed["total_records"] == 0

    def test_empty_results(self):
        parsed = _parse_bql_results([])
        assert parsed["total_records"] == 0
        assert parsed["records"] == []

    def test_non_dict_ignored(self):
        parsed = _parse_bql_results(["not a dict", 42])
        assert parsed["total_records"] == 0


class TestBQLHandler:
    @patch("bloomberg_mcp.core.session.BloombergSession.get_instance")
    def test_service_unavailable_graceful(self, mock_session_cls):
        """BQL returns graceful error when //blp/bqlsvc unavailable."""
        from bloomberg_mcp.handlers.bql import bloomberg_run_bql

        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_session.get_service.return_value = None  # Service not available
        mock_session_cls.return_value = mock_session

        params = BQLInput(expression="get(px_last()) for(['AAPL US Equity'])")
        result = _run(bloomberg_run_bql(params))

        assert "not available" in result.lower()
        assert "//blp/bqlsvc" in result
        assert "alternative" in result.lower()

    @patch("bloomberg_mcp.core.session.BloombergSession.get_instance")
    def test_connection_failure(self, mock_session_cls):
        """BQL returns error when cannot connect."""
        from bloomberg_mcp.handlers.bql import bloomberg_run_bql

        mock_session = MagicMock()
        mock_session.is_connected.return_value = False
        mock_session.connect.return_value = False
        mock_session_cls.return_value = mock_session

        params = BQLInput(expression="get(px_last()) for(['AAPL US Equity'])")
        result = _run(bloomberg_run_bql(params))
        assert "Failed to connect" in result

    @patch("bloomberg_mcp.core.session.BloombergSession.get_instance")
    def test_successful_query(self, mock_session_cls):
        """BQL returns parsed results on success."""
        from bloomberg_mcp.handlers.bql import bloomberg_run_bql

        mock_session = MagicMock()
        mock_session.is_connected.return_value = True

        mock_service = MagicMock()
        mock_session.get_service.return_value = mock_service

        mock_session.send_request.return_value = [
            {"results": [
                {"security": "AAPL US Equity", "PX_LAST": 175.5},
                {"security": "MSFT US Equity", "PX_LAST": 420.0},
            ]}
        ]
        mock_session_cls.return_value = mock_session

        params = BQLInput(
            expression="get(px_last()) for(['AAPL US Equity','MSFT US Equity'])"
        )
        result = _run(bloomberg_run_bql(params))

        data = json.loads(result)
        assert data["total_records"] == 2
        assert data["records"][0]["PX_LAST"] == 175.5

    @patch("bloomberg_mcp.core.session.BloombergSession.get_instance")
    def test_markdown_output(self, mock_session_cls):
        """BQL markdown format works."""
        from bloomberg_mcp.handlers.bql import bloomberg_run_bql

        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_service = MagicMock()
        mock_session.get_service.return_value = mock_service
        mock_session.send_request.return_value = [
            {"results": [{"security": "AAPL", "PX_LAST": 175.5}]}
        ]
        mock_session_cls.return_value = mock_session

        params = BQLInput(
            expression="get(px_last()) for(['AAPL US Equity'])",
            response_format=ResponseFormat.MARKDOWN,
        )
        result = _run(bloomberg_run_bql(params))
        assert "BQL Query Results" in result
        assert "AAPL" in result

    @patch("bloomberg_mcp.core.session.BloombergSession.get_instance")
    def test_bql_sends_expression(self, mock_session_cls):
        """BQL correctly sets expression on request."""
        from bloomberg_mcp.handlers.bql import bloomberg_run_bql

        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_service.createRequest.return_value = mock_request
        mock_session.get_service.return_value = mock_service
        mock_session.send_request.return_value = [{"results": []}]
        mock_session_cls.return_value = mock_session

        expr = "get(px_last()) for(['AAPL US Equity'])"
        params = BQLInput(expression=expr)
        _run(bloomberg_run_bql(params))

        mock_service.createRequest.assert_called_with("sendQuery")
        mock_request.set.assert_called_with("expression", expr)
