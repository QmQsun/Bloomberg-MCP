"""Tests for the estimates detail tool."""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock

from bloomberg_mcp.models.inputs import EstimatesDetailInput
from bloomberg_mcp.models.enums import ResponseFormat


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestEstimatesDetailInput:
    """Test EstimatesDetailInput model validation."""

    def test_defaults(self):
        inp = EstimatesDetailInput(securities=["AAPL US Equity"])
        assert inp.metrics == ["EPS", "SALES", "EBITDA"]
        assert inp.periods == ["1FY", "2FY", "1FQ", "2FQ"]
        assert inp.include_revisions is True
        assert inp.include_surprise is True

    def test_custom_metrics(self):
        inp = EstimatesDetailInput(
            securities=["AAPL US Equity"],
            metrics=["EPS", "FCF"],
            periods=["1FY"],
        )
        assert inp.metrics == ["EPS", "FCF"]
        assert inp.periods == ["1FY"]

    def test_empty_securities_rejected(self):
        with pytest.raises(Exception):
            EstimatesDetailInput(securities=[])


class TestEstimatesDetailHandler:
    """Test bloomberg_get_estimates_detail handler."""

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_multi_period_fetch(self, mock_ref_data):
        """Handler calls get_reference_data once per period with correct override."""
        from bloomberg_mcp.handlers.estimates import bloomberg_get_estimates_detail

        mock_sec = MagicMock()
        mock_sec.security = "AAPL US Equity"
        mock_sec.errors = []
        mock_sec.fields = {
            "BEST_EPS": 6.50,
            "BEST_EPS_MEDIAN": 6.48,
            "BEST_EPS_HIGH": 7.20,
            "BEST_EPS_LOW": 5.80,
            "BEST_EPS_NUM_EST": 38,
            "BEST_EPS_4WK_CHG": 0.15,
            "BEST_EPS_SURPRISE": 0.12,
        }
        mock_ref_data.return_value = [mock_sec]

        params = EstimatesDetailInput(
            securities=["AAPL US Equity"],
            metrics=["EPS"],
            periods=["1FY", "2FY"],
        )
        result = _run(bloomberg_get_estimates_detail(params))

        # Should have been called twice: once for 1FY, once for 2FY
        assert mock_ref_data.call_count == 2

        # Check override values in the calls
        calls = mock_ref_data.call_args_list
        assert calls[0].kwargs["overrides"] == {"BEST_FPERIOD_OVERRIDE": "1FY"}
        assert calls[1].kwargs["overrides"] == {"BEST_FPERIOD_OVERRIDE": "2FY"}

        # Result should be valid JSON
        data = json.loads(result)
        assert "AAPL US Equity" in data["securities"]
        assert "1FY" in data["securities"]["AAPL US Equity"]
        assert "2FY" in data["securities"]["AAPL US Equity"]

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_markdown_output(self, mock_ref_data):
        """Handler produces markdown table."""
        from bloomberg_mcp.handlers.estimates import bloomberg_get_estimates_detail

        mock_sec = MagicMock()
        mock_sec.security = "MSFT US Equity"
        mock_sec.errors = []
        mock_sec.fields = {"BEST_EPS": 12.0, "BEST_EPS_MEDIAN": 11.9,
                           "BEST_EPS_HIGH": 13.0, "BEST_EPS_LOW": 11.0,
                           "BEST_EPS_NUM_EST": 45, "BEST_EPS_4WK_CHG": 0.3,
                           "BEST_EPS_SURPRISE": 0.05}
        mock_ref_data.return_value = [mock_sec]

        params = EstimatesDetailInput(
            securities=["MSFT US Equity"],
            metrics=["EPS"],
            periods=["1FY"],
            response_format=ResponseFormat.MARKDOWN,
        )
        result = _run(bloomberg_get_estimates_detail(params))
        assert "Consensus Estimates" in result
        assert "MSFT US Equity" in result
        assert "1FY" in result

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_multiple_metrics(self, mock_ref_data):
        """Handler requests fields for all specified metrics."""
        from bloomberg_mcp.handlers.estimates import bloomberg_get_estimates_detail

        mock_sec = MagicMock()
        mock_sec.security = "AAPL US Equity"
        mock_sec.errors = []
        mock_sec.fields = {}
        mock_ref_data.return_value = [mock_sec]

        params = EstimatesDetailInput(
            securities=["AAPL US Equity"],
            metrics=["EPS", "SALES"],
            periods=["1FY"],
        )
        _run(bloomberg_get_estimates_detail(params))

        # Check that both BEST_EPS and BEST_SALES fields were requested
        call_fields = mock_ref_data.call_args_list[0].kwargs["fields"]
        assert "BEST_EPS" in call_fields
        assert "BEST_SALES" in call_fields
