"""Tests for the supply chain tool."""

import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock

from bloomberg_mcp.models.inputs import SupplyChainInput
from bloomberg_mcp.models.enums import ResponseFormat


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestSupplyChainInput:
    def test_defaults(self):
        inp = SupplyChainInput(security="AAPL US Equity")
        assert inp.relationship == "all"
        assert inp.max_rows == 50

    def test_specific_relationship(self):
        inp = SupplyChainInput(security="AAPL US Equity", relationship="suppliers")
        assert inp.relationship == "suppliers"

    def test_invalid_relationship(self):
        with pytest.raises(Exception):
            SupplyChainInput(security="AAPL US Equity", relationship="partners")

    def test_case_insensitive(self):
        inp = SupplyChainInput(security="AAPL US Equity", relationship="Suppliers")
        assert inp.relationship == "suppliers"


class TestSupplyChainHandler:
    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_all_relationships(self, mock_ref_data):
        from bloomberg_mcp.handlers.supply_chain import bloomberg_get_supply_chain

        def make_response(field_name, data):
            sec = MagicMock()
            sec.security = "AAPL US Equity"
            sec.errors = []
            sec.fields = {field_name: data}
            return [sec]

        mock_ref_data.side_effect = [
            make_response("SUPPLY_CHAIN_SUPPLIERS", [
                {"Company": "TSMC", "Revenue %": 25.0},
            ]),
            make_response("SUPPLY_CHAIN_CUSTOMERS", [
                {"Company": "Best Buy", "Revenue %": 10.0},
            ]),
            make_response("SUPPLY_CHAIN_COMPETITORS", [
                {"Company": "Samsung", "Revenue %": 0.0},
            ]),
        ]

        params = SupplyChainInput(security="AAPL US Equity")
        result = _run(bloomberg_get_supply_chain(params))

        data = json.loads(result)
        assert "suppliers" in data["relationships"]
        assert "customers" in data["relationships"]
        assert "competitors" in data["relationships"]
        assert data["relationships"]["suppliers"]["count"] == 1

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_single_relationship(self, mock_ref_data):
        from bloomberg_mcp.handlers.supply_chain import bloomberg_get_supply_chain

        sec = MagicMock()
        sec.security = "AAPL US Equity"
        sec.errors = []
        sec.fields = {
            "SUPPLY_CHAIN_SUPPLIERS": [
                {"Company": "TSMC"},
                {"Company": "Foxconn"},
            ]
        }
        mock_ref_data.return_value = [sec]

        params = SupplyChainInput(security="AAPL US Equity", relationship="suppliers")
        result = _run(bloomberg_get_supply_chain(params))

        data = json.loads(result)
        assert "suppliers" in data["relationships"]
        assert "customers" not in data["relationships"]
        assert data["relationships"]["suppliers"]["count"] == 2

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_truncation(self, mock_ref_data):
        from bloomberg_mcp.handlers.supply_chain import bloomberg_get_supply_chain

        sec = MagicMock()
        sec.security = "TEST Equity"
        sec.errors = []
        sec.fields = {
            "SUPPLY_CHAIN_SUPPLIERS": [{"Company": f"S{i}"} for i in range(100)]
        }
        mock_ref_data.return_value = [sec]

        params = SupplyChainInput(security="TEST Equity", relationship="suppliers", max_rows=5)
        result = _run(bloomberg_get_supply_chain(params))

        data = json.loads(result)
        assert data["relationships"]["suppliers"]["count"] == 5

    @patch("bloomberg_mcp.tools.get_reference_data")
    def test_markdown_output(self, mock_ref_data):
        from bloomberg_mcp.handlers.supply_chain import bloomberg_get_supply_chain

        sec = MagicMock()
        sec.security = "AAPL US Equity"
        sec.errors = []
        sec.fields = {"SUPPLY_CHAIN_CUSTOMERS": [{"Company": "BestBuy"}]}
        mock_ref_data.return_value = [sec]

        params = SupplyChainInput(
            security="AAPL US Equity",
            relationship="customers",
            response_format=ResponseFormat.MARKDOWN,
        )
        result = _run(bloomberg_get_supply_chain(params))
        assert "Supply Chain" in result
        assert "Customers" in result
        assert "BestBuy" in result
