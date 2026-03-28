"""Tests for new FieldSets and fieldset map consistency."""

import pytest

from bloomberg_mcp.tools.dynamic_screening.models import FieldSet, FieldSets
from bloomberg_mcp.utils import _get_fieldset_map, _expand_fields


class TestNewFieldSets:
    """Test that all new PHASE 1 FieldSets are properly defined."""

    def test_estimates_consensus(self):
        fs = FieldSets.ESTIMATES_CONSENSUS
        assert isinstance(fs, FieldSet)
        assert "BEST_EPS" in fs.fields
        assert "BEST_TARGET_PRICE" in fs.fields
        assert len(fs.fields) == 10

    def test_profitability(self):
        fs = FieldSets.PROFITABILITY
        assert "GROSS_MARGIN" in fs.fields
        assert "RETURN_ON_EQUITY" in fs.fields
        assert len(fs.fields) == 7

    def test_cash_flow(self):
        fs = FieldSets.CASH_FLOW
        assert "CF_FREE_CASH_FLOW" in fs.fields
        assert len(fs.fields) == 6

    def test_balance_sheet(self):
        fs = FieldSets.BALANCE_SHEET
        assert "CUR_RATIO" in fs.fields
        assert "NET_DEBT" in fs.fields
        assert len(fs.fields) == 6

    def test_ownership(self):
        fs = FieldSets.OWNERSHIP
        assert "PCT_HELD_BY_INSIDERS" in fs.fields
        assert len(fs.fields) == 5

    def test_governance(self):
        fs = FieldSets.GOVERNANCE
        assert "ESG_DISCLOSURE_SCORE" in fs.fields
        assert len(fs.fields) == 4

    def test_risk(self):
        fs = FieldSets.RISK
        assert "BETA_RAW_OVERRIDABLE" in fs.fields
        assert "VOLATILITY_260D" in fs.fields
        assert len(fs.fields) == 6

    def test_valuation_extended(self):
        fs = FieldSets.VALUATION_EXTENDED
        assert "PE_RATIO" in fs.fields
        assert "EV_TO_T12M_EBITDA" in fs.fields
        assert len(fs.fields) == 9

    def test_earnings_surprise(self):
        fs = FieldSets.EARNINGS_SURPRISE
        assert "BEST_EPS_SURPRISE" in fs.fields
        assert len(fs.fields) == 6

    def test_growth(self):
        fs = FieldSets.GROWTH
        assert "SALES_GROWTH" in fs.fields
        assert "BEST_EST_LONG_TERM_GROWTH" in fs.fields
        assert len(fs.fields) == 4


class TestFieldSetMapConsistency:
    """Test that _get_fieldset_map includes all new FieldSets."""

    def test_new_fieldsets_in_map(self):
        fsmap = _get_fieldset_map()
        new_names = [
            "ESTIMATES_CONSENSUS", "PROFITABILITY", "CASH_FLOW",
            "BALANCE_SHEET", "OWNERSHIP", "GOVERNANCE", "RISK",
            "VALUATION_EXTENDED", "EARNINGS_SURPRISE", "GROWTH",
        ]
        for name in new_names:
            assert name in fsmap, f"{name} missing from fieldset map"

    def test_expand_new_fieldsets(self):
        """_expand_fields correctly expands new FieldSet names."""
        fields = _expand_fields(["PROFITABILITY", "PX_LAST"])
        assert "GROSS_MARGIN" in fields
        assert "RETURN_ON_EQUITY" in fields
        assert "PX_LAST" in fields

    def test_expand_deduplicates(self):
        """Shared fields between FieldSets are not duplicated."""
        fields = _expand_fields(["RISK", "TECHNICAL"])
        # BETA_RAW_OVERRIDABLE is in both RISK and TECHNICAL
        assert fields.count("BETA_RAW_OVERRIDABLE") == 1

    def test_fieldset_addition(self):
        """FieldSets can be combined with + operator."""
        combined = FieldSets.PROFITABILITY + FieldSets.GROWTH
        assert "GROSS_MARGIN" in combined.fields
        assert "SALES_GROWTH" in combined.fields
