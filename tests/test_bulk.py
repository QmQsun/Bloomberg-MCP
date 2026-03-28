"""Tests for the BDS (bulk data) tool."""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock

from bloomberg_mcp.models.inputs import BulkDataInput
from bloomberg_mcp.models.enums import ResponseFormat


class TestBulkDataInput:
    """Test BulkDataInput model validation."""

    def test_valid_input(self):
        inp = BulkDataInput(
            security="AAPL US Equity",
            field="TOP_20_HOLDERS_PUBLIC_FILINGS"
        )
        assert inp.security == "AAPL US Equity"
        assert inp.field == "TOP_20_HOLDERS_PUBLIC_FILINGS"
        assert inp.max_rows == 100
        assert inp.response_format == ResponseFormat.JSON

    def test_with_overrides(self):
        inp = BulkDataInput(
            security="AAPL US Equity",
            field="DVD_HIST_ALL",
            overrides={"DVD_START_DT": "20200101"}
        )
        assert inp.overrides == {"DVD_START_DT": "20200101"}

    def test_custom_max_rows(self):
        inp = BulkDataInput(
            security="AAPL US Equity",
            field="INDX_MEMBERS",
            max_rows=500
        )
        assert inp.max_rows == 500

    def test_max_rows_validation(self):
        with pytest.raises(Exception):
            BulkDataInput(
                security="AAPL US Equity",
                field="INDX_MEMBERS",
                max_rows=0
            )

    def test_empty_security_rejected(self):
        with pytest.raises(Exception):
            BulkDataInput(security="", field="TOP_20_HOLDERS_PUBLIC_FILINGS")

    def test_empty_field_rejected(self):
        with pytest.raises(Exception):
            BulkDataInput(security="AAPL US Equity", field="")

    def test_markdown_format(self):
        inp = BulkDataInput(
            security="AAPL US Equity",
            field="TOP_20_HOLDERS_PUBLIC_FILINGS",
            response_format=ResponseFormat.MARKDOWN
        )
        assert inp.response_format == ResponseFormat.MARKDOWN


def _run(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestBulkDataHandler:
    """Test bloomberg_get_bulk_data handler logic."""

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_bulk_data_list_response(self, mock_ref_data):
        """Handler correctly processes list-type BDS response."""
        from bloomberg_mcp.handlers.bulk import bloomberg_get_bulk_data

        mock_sec = MagicMock()
        mock_sec.security = "AAPL US Equity"
        mock_sec.errors = []
        mock_sec.fields = {
            "TOP_20_HOLDERS_PUBLIC_FILINGS": [
                {"Holder Name": "Vanguard", "Position": 1000000, "Percent Outstanding": 7.5},
                {"Holder Name": "BlackRock", "Position": 800000, "Percent Outstanding": 6.0},
            ]
        }
        mock_ref_data.return_value = [mock_sec]

        params = BulkDataInput(
            security="AAPL US Equity",
            field="TOP_20_HOLDERS_PUBLIC_FILINGS"
        )
        result = _run(bloomberg_get_bulk_data(params))

        data = json.loads(result)
        assert data["security"] == "AAPL US Equity"
        assert data["total_rows"] == 2
        assert data["truncated"] is False
        assert len(data["data"]) == 2
        assert data["columns"] == ["Holder Name", "Position", "Percent Outstanding"]

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_bulk_data_truncation(self, mock_ref_data):
        """Handler truncates to max_rows."""
        from bloomberg_mcp.handlers.bulk import bloomberg_get_bulk_data

        mock_sec = MagicMock()
        mock_sec.security = "SPX Index"
        mock_sec.errors = []
        mock_sec.fields = {
            "INDX_MEMBERS": [{"Ticker": f"SEC_{i}"} for i in range(500)]
        }
        mock_ref_data.return_value = [mock_sec]

        params = BulkDataInput(
            security="SPX Index",
            field="INDX_MEMBERS",
            max_rows=10
        )
        result = _run(bloomberg_get_bulk_data(params))

        data = json.loads(result)
        assert data["total_rows"] == 500
        assert data["truncated"] is True
        assert len(data["data"]) == 10

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_bulk_data_scalar_warning(self, mock_ref_data):
        """Handler warns when a non-bulk field is used."""
        from bloomberg_mcp.handlers.bulk import bloomberg_get_bulk_data

        mock_sec = MagicMock()
        mock_sec.security = "AAPL US Equity"
        mock_sec.errors = []
        mock_sec.fields = {"PX_LAST": 150.0}
        mock_ref_data.return_value = [mock_sec]

        params = BulkDataInput(
            security="AAPL US Equity",
            field="PX_LAST"
        )
        result = _run(bloomberg_get_bulk_data(params))

        data = json.loads(result)
        assert data["value"] == 150.0
        assert "scalar" in data["note"].lower()

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_bulk_data_error_handling(self, mock_ref_data):
        """Handler returns error string on security error."""
        from bloomberg_mcp.handlers.bulk import bloomberg_get_bulk_data

        mock_sec = MagicMock()
        mock_sec.security = "INVALID Equity"
        mock_sec.errors = ["Unknown security"]
        mock_sec.fields = {}
        mock_ref_data.return_value = [mock_sec]

        params = BulkDataInput(
            security="INVALID Equity",
            field="TOP_20_HOLDERS_PUBLIC_FILINGS"
        )
        result = _run(bloomberg_get_bulk_data(params))
        assert "Error" in result or "error" in result.lower()
