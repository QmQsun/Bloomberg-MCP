"""Tests for technical analysis tool and request builder."""

import pytest
from unittest.mock import MagicMock, patch

from bloomberg_mcp.models.inputs import TechnicalAnalysisInput
from bloomberg_mcp.models.enums import ResponseFormat
from bloomberg_mcp.core.requests import (
    build_study_request,
    STUDY_ATTRIBUTES_MAP,
    STUDY_DEFAULT_PERIODS,
)
from bloomberg_mcp.core.responses import StudyDataPoint, StudyResult, parse_study_response


class TestTechnicalAnalysisInput:
    """Test TechnicalAnalysisInput model validation."""

    def test_valid_input(self):
        inp = TechnicalAnalysisInput(
            security="AAPL US Equity",
            study="rsi",
            start_date="20240101",
            end_date="20240630",
        )
        assert inp.study == "rsi"
        assert inp.period is None

    def test_with_period(self):
        inp = TechnicalAnalysisInput(
            security="AAPL US Equity",
            study="sma",
            start_date="20240101",
            end_date="20240630",
            period=50,
        )
        assert inp.period == 50

    def test_iso_date_normalized(self):
        inp = TechnicalAnalysisInput(
            security="AAPL US Equity",
            study="rsi",
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        assert inp.start_date == "20240101"
        assert inp.end_date == "20240630"

    def test_invalid_study_rejected(self):
        with pytest.raises(Exception):
            TechnicalAnalysisInput(
                security="AAPL US Equity",
                study="invalid_study",
                start_date="20240101",
                end_date="20240630",
            )

    def test_study_case_insensitive(self):
        inp = TechnicalAnalysisInput(
            security="AAPL US Equity",
            study="RSI",
            start_date="20240101",
            end_date="20240630",
        )
        assert inp.study == "rsi"

    def test_all_valid_studies(self):
        for study in ["rsi", "macd", "sma", "ema", "bollinger", "dmi", "stochastic"]:
            inp = TechnicalAnalysisInput(
                security="AAPL US Equity",
                study=study,
                start_date="20240101",
                end_date="20240630",
            )
            assert inp.study == study


class TestStudyAttributesMap:
    """Test the study attributes mapping constants."""

    def test_all_studies_have_attributes(self):
        expected = {"rsi", "macd", "sma", "ema", "bollinger", "dmi", "stochastic"}
        assert set(STUDY_ATTRIBUTES_MAP.keys()) == expected

    def test_all_studies_have_default_periods(self):
        for study in STUDY_ATTRIBUTES_MAP:
            assert study in STUDY_DEFAULT_PERIODS

    def test_attribute_names_format(self):
        """All attribute names should end with 'StudyAttributes'."""
        for name in STUDY_ATTRIBUTES_MAP.values():
            assert name.endswith("StudyAttributes")


class TestBuildStudyRequest:
    """Test build_study_request with mocked service."""

    def _make_mock_service(self):
        """Create a mock //blp/tasvc service with nested element structure."""
        service = MagicMock()
        request = MagicMock()
        service.createRequest.return_value = request

        # Mock the nested element chain:
        # request.getElement("priceSource") -> price_source
        # price_source.getElement("securityName") -> sec_name_elem
        # price_source.getElement("dataRange") -> data_range
        # data_range.getElement("historical") -> historical
        # request.getElement("studyAttributes") -> study_attrs

        price_source = MagicMock()
        sec_name = MagicMock()
        data_range = MagicMock()
        historical = MagicMock()
        study_attrs = MagicMock()
        study_elem = MagicMock()

        price_source.getElement.side_effect = lambda name: {
            "securityName": sec_name,
            "dataRange": data_range,
        }[name]

        data_range.getElement.return_value = historical

        study_attrs.getElement.return_value = study_elem

        request.getElement.side_effect = lambda name: {
            "priceSource": price_source,
            "studyAttributes": study_attrs,
        }[name]

        return service, request, {
            "price_source": price_source,
            "sec_name": sec_name,
            "data_range": data_range,
            "historical": historical,
            "study_attrs": study_attrs,
            "study_elem": study_elem,
        }

    def test_rsi_request(self):
        """RSI request sets correct study attributes."""
        service, request, elems = self._make_mock_service()

        build_study_request(service, "AAPL US Equity", "rsi", "20240101", "20240630")

        service.createRequest.assert_called_with("studyRequest")
        elems["sec_name"].setValue.assert_called_with("AAPL US Equity")
        elems["data_range"].setChoice.assert_called_with("historical")
        elems["historical"].getElement.return_value.setValue.assert_any_call("20240101")
        elems["study_attrs"].setChoice.assert_called_with("rsiStudyAttributes")
        elems["study_elem"].getElement.return_value.setValue.assert_called_with(14)

    def test_macd_request(self):
        """MACD request sets fast/slow/signal periods."""
        service, request, elems = self._make_mock_service()

        build_study_request(service, "AAPL US Equity", "macd", "20240101", "20240630")

        elems["study_attrs"].setChoice.assert_called_with("macdStudyAttributes")
        # MACD should call getElement for fastPeriod, slowPeriod, signalPeriod
        get_elem_calls = [c.args[0] for c in elems["study_elem"].getElement.call_args_list]
        assert "fastPeriod" in get_elem_calls
        assert "slowPeriod" in get_elem_calls
        assert "signalPeriod" in get_elem_calls

    def test_custom_period(self):
        """Custom period overrides default."""
        service, request, elems = self._make_mock_service()

        build_study_request(service, "AAPL US Equity", "sma", "20240101", "20240630", period=50)

        elems["study_elem"].getElement.return_value.setValue.assert_called_with(50)

    def test_invalid_study_raises(self):
        service = MagicMock()
        with pytest.raises(ValueError, match="Unknown study"):
            build_study_request(service, "AAPL US Equity", "invalid", "20240101", "20240630")


class TestStudyDataPoint:
    """Test StudyDataPoint dataclass."""

    def test_basic(self):
        dp = StudyDataPoint(date="2024-01-02", values={"RSI": 55.3})
        assert dp.date == "2024-01-02"
        assert dp.values["RSI"] == 55.3

    def test_multiple_values(self):
        """Bollinger bands return multiple values."""
        dp = StudyDataPoint(
            date="2024-01-02",
            values={"upperBand": 155.0, "middleBand": 150.0, "lowerBand": 145.0}
        )
        assert len(dp.values) == 3


class TestParseStudyResponse:
    """Test parse_study_response with mock messages."""

    def test_parse_rsi_response(self):
        msg = MagicMock()
        msg.toPy.return_value = {
            "studyData": [
                {"date": "2024-01-02", "RSI": 55.3},
                {"date": "2024-01-03", "RSI": 58.1},
                {"date": "2024-01-04", "RSI": 52.7},
            ]
        }

        result = parse_study_response(msg)
        assert len(result) == 3
        assert result[0].date == "2024-01-02"
        assert result[0].values["RSI"] == 55.3

    def test_parse_bollinger_response(self):
        msg = MagicMock()
        msg.toPy.return_value = {
            "studyData": [
                {"date": "2024-01-02", "upperBand": 155.0, "middleBand": 150.0, "lowerBand": 145.0},
            ]
        }

        result = parse_study_response(msg)
        assert len(result) == 1
        assert result[0].values["upperBand"] == 155.0
        assert result[0].values["lowerBand"] == 145.0

    def test_parse_empty_response(self):
        msg = MagicMock()
        msg.toPy.return_value = {"studyData": []}
        assert parse_study_response(msg) == []

    def test_parse_error_response(self):
        msg = MagicMock()
        msg.toPy.return_value = {"responseError": {"message": "Service unavailable"}}
        assert parse_study_response(msg) == []
