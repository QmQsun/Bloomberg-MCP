"""Tests for the ownership tool."""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock

from bloomberg_mcp.models.inputs import OwnershipInput
from bloomberg_mcp.models.enums import ResponseFormat


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestOwnershipInput:
    def test_defaults(self):
        inp = OwnershipInput(security="AAPL US Equity")
        assert inp.max_holders == 20
        assert inp.response_format == ResponseFormat.JSON

    def test_custom(self):
        inp = OwnershipInput(security="MSFT US Equity", max_holders=10)
        assert inp.max_holders == 10

    def test_empty_security_rejected(self):
        with pytest.raises(Exception):
            OwnershipInput(security="")


class TestOwnershipHandler:
    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_combines_summary_and_holders(self, mock_ref_data):
        from bloomberg_mcp.handlers.ownership import bloomberg_get_ownership

        # First call: summary BDP fields
        summary_sec = MagicMock()
        summary_sec.security = "AAPL US Equity"
        summary_sec.errors = []
        summary_sec.fields = {
            "PCT_HELD_BY_INSIDERS": 0.07,
            "PCT_HELD_BY_INSTITUTIONS": 60.5,
            "NUM_OF_INSTITUTIONAL_HOLDERS": 5200,
        }

        # Second call: BDS holder list
        holder_sec = MagicMock()
        holder_sec.security = "AAPL US Equity"
        holder_sec.errors = []
        holder_sec.fields = {
            "TOP_20_HOLDERS_PUBLIC_FILINGS": [
                {"Holder Name": "Vanguard", "Position": 1200000000, "Percent Outstanding": 8.1},
                {"Holder Name": "BlackRock", "Position": 1000000000, "Percent Outstanding": 6.8},
                {"Holder Name": "Berkshire", "Position": 900000000, "Percent Outstanding": 6.1},
            ]
        }

        mock_ref_data.side_effect = [[summary_sec], [holder_sec]]

        params = OwnershipInput(security="AAPL US Equity", max_holders=2)
        result = _run(bloomberg_get_ownership(params))

        data = json.loads(result)
        assert data["security"] == "AAPL US Equity"
        assert data["summary"]["PCT_HELD_BY_INSTITUTIONS"] == 60.5
        assert len(data["holders"]["data"]) == 2  # max_holders=2
        assert data["holders"]["data"][0]["Holder Name"] == "Vanguard"

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_markdown_output(self, mock_ref_data):
        from bloomberg_mcp.handlers.ownership import bloomberg_get_ownership

        summary_sec = MagicMock()
        summary_sec.security = "AAPL US Equity"
        summary_sec.errors = []
        summary_sec.fields = {"PCT_HELD_BY_INSTITUTIONS": 60.0}

        holder_sec = MagicMock()
        holder_sec.security = "AAPL US Equity"
        holder_sec.errors = []
        holder_sec.fields = {"TOP_20_HOLDERS_PUBLIC_FILINGS": [{"Holder": "Vanguard"}]}

        mock_ref_data.side_effect = [[summary_sec], [holder_sec]]

        params = OwnershipInput(
            security="AAPL US Equity",
            response_format=ResponseFormat.MARKDOWN,
        )
        result = _run(bloomberg_get_ownership(params))
        assert "Ownership" in result
        assert "Summary" in result
        assert "Vanguard" in result

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_handles_empty_holders(self, mock_ref_data):
        from bloomberg_mcp.handlers.ownership import bloomberg_get_ownership

        sec = MagicMock()
        sec.security = "TEST Equity"
        sec.errors = []
        sec.fields = {}

        mock_ref_data.return_value = [sec]

        params = OwnershipInput(security="TEST Equity")
        result = _run(bloomberg_get_ownership(params))
        data = json.loads(result)
        assert data["holders"]["data"] == []
