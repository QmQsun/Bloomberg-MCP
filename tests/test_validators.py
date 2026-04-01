"""Tests for response validators — quality gates for Bloomberg data."""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List

from bloomberg_mcp.core.validators import (
    validate_field_count,
    validate_reference_response,
    validate_historical_response,
    validate_bulk_response,
)


@dataclass
class MockSecurityData:
    security: str
    fields: Dict[str, Any]
    errors: List[str] = field(default_factory=list)


@dataclass
class MockHistoricalData:
    security: str
    data: List[Dict[str, Any]]
    errors: List[str] = field(default_factory=list)


class TestValidateFieldCount:
    def test_within_reference_limit(self):
        validate_field_count(["F1", "F2", "F3"], "reference")  # Should not raise

    def test_exceeds_reference_limit(self):
        fields = [f"F{i}" for i in range(401)]
        with pytest.raises(ValueError, match="max 400"):
            validate_field_count(fields, "reference")

    def test_within_historical_limit(self):
        validate_field_count(["F1", "F2"], "historical")  # Should not raise

    def test_exceeds_historical_limit(self):
        fields = [f"F{i}" for i in range(26)]
        with pytest.raises(ValueError, match="max 25"):
            validate_field_count(fields, "historical")

    def test_unknown_type_no_limit(self):
        fields = [f"F{i}" for i in range(1000)]
        validate_field_count(fields, "unknown_type")  # Should not raise


class TestValidateReferenceResponse:
    def test_normal_response_no_warnings(self):
        data = [MockSecurityData("AAPL US Equity", {"PX_LAST": 150.0, "PE_RATIO": 25.0})]
        warnings = validate_reference_response(data)
        assert len(warnings) == 0

    def test_all_fields_empty(self):
        data = [MockSecurityData("BAD Equity", {})]
        warnings = validate_reference_response(data)
        assert len(warnings) == 1
        assert warnings[0].code == "EMPTY_RESPONSE"
        # Should also inject into errors
        assert len(data[0].errors) == 1

    def test_all_fields_none(self):
        data = [MockSecurityData("BAD Equity", {"PX_LAST": None, "PE_RATIO": None})]
        warnings = validate_reference_response(data)
        assert any(w.code == "EMPTY_RESPONSE" for w in warnings)

    def test_high_null_ratio(self):
        data = [MockSecurityData("AAPL US Equity", {
            "PX_LAST": 150.0,
            "PE_RATIO": None,
            "VOLUME": None,
            "EPS": None,
        })]
        warnings = validate_reference_response(data)
        assert any(w.code == "HIGH_NULL_RATIO" for w in warnings)

    def test_missing_fields_detected(self):
        data = [MockSecurityData("AAPL US Equity", {"PX_LAST": 150.0})]
        warnings = validate_reference_response(data, requested_fields=["PX_LAST", "PE_RATIO"])
        assert any(w.code == "MISSING_FIELDS" for w in warnings)


class TestValidateHistoricalResponse:
    def test_normal_response_no_warnings(self):
        data = [MockHistoricalData("AAPL US Equity", [
            {"date": "2024-01-01", "PX_LAST": 150.0},
            {"date": "2024-01-02", "PX_LAST": 151.0},
        ])]
        warnings = validate_historical_response(data)
        assert len(warnings) == 0

    def test_empty_series(self):
        data = [MockHistoricalData("AAPL US Equity", [])]
        warnings = validate_historical_response(data)
        assert len(warnings) == 1
        assert warnings[0].code == "EMPTY_SERIES"

    def test_short_series_for_long_range(self):
        data = [MockHistoricalData("AAPL US Equity", [
            {"date": "2024-01-01", "PX_LAST": 150.0},
            {"date": "2024-01-02", "PX_LAST": 151.0},
        ])]
        warnings = validate_historical_response(data, "20240101", "20240630")
        assert any(w.code == "SHORT_SERIES" for w in warnings)


class TestValidateBulkResponse:
    def test_normal_list_no_warnings(self):
        warnings = validate_bulk_response(
            [{"name": "Vanguard", "pct": 5.0}],
            "TOP_20_HOLDERS_PUBLIC_FILINGS",
            "AAPL US Equity",
        )
        assert len(warnings) == 0

    def test_scalar_detected(self):
        warnings = validate_bulk_response(150.0, "PX_LAST", "AAPL US Equity")
        assert len(warnings) == 1
        assert warnings[0].code == "SCALAR_BULK_FIELD"
        assert "BDP field" in warnings[0].message

    def test_none_detected(self):
        warnings = validate_bulk_response(None, "BOGUS_FIELD", "AAPL US Equity")
        assert len(warnings) == 1
        assert warnings[0].code == "NULL_BULK_FIELD"

    def test_empty_list_detected(self):
        warnings = validate_bulk_response([], "DVD_HIST_ALL", "AAPL US Equity")
        assert len(warnings) == 1
        assert warnings[0].code == "EMPTY_BULK_FIELD"
