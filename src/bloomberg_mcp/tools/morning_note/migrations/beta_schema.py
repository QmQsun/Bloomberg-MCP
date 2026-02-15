"""Beta schema migration - adds VIX, gold, yield curve, intraday fields.

Migration: 001_beta_schema
Created: 2024-12-23

This migration adds:
1. VIX and Gold tracking to session_snapshots
2. Full yield curve data (2Y, 10Y, spread)
3. Intraday character classification
4. Enhanced notes_archive metadata
"""

MIGRATION_SQL = """
-- =============================================================================
-- SESSION SNAPSHOTS ENHANCEMENTS
-- =============================================================================

-- VIX tracking
ALTER TABLE session_snapshots ADD COLUMN vix_close REAL;
ALTER TABLE session_snapshots ADD COLUMN vix_change_pct REAL;

-- Gold tracking
ALTER TABLE session_snapshots ADD COLUMN gold_close REAL;
ALTER TABLE session_snapshots ADD COLUMN gold_change_pct REAL;

-- Full yield curve (2Y already referenced as us_10y, adding 2Y and spread)
ALTER TABLE session_snapshots ADD COLUMN us_2y_yield REAL;

-- Intraday character classification
ALTER TABLE session_snapshots ADD COLUMN intraday_character TEXT;
ALTER TABLE session_snapshots ADD COLUMN spx_intraday_range_pct REAL;
ALTER TABLE session_snapshots ADD COLUMN volume_vs_20d_avg REAL;

-- =============================================================================
-- NOTES ARCHIVE ENHANCEMENTS
-- =============================================================================

-- Hypothesis testing metadata
ALTER TABLE notes_archive ADD COLUMN hypotheses_tested INTEGER DEFAULT 0;
ALTER TABLE notes_archive ADD COLUMN hypotheses_confirmed INTEGER DEFAULT 0;

-- Key tickers mentioned in note (JSON array)
ALTER TABLE notes_archive ADD COLUMN key_tickers TEXT;

-- Pipeline execution metadata
ALTER TABLE notes_archive ADD COLUMN execution_time_seconds REAL;
ALTER TABLE notes_archive ADD COLUMN model_used TEXT;

-- Risk tone and session type for quick filtering
ALTER TABLE notes_archive ADD COLUMN risk_tone TEXT;
ALTER TABLE notes_archive ADD COLUMN session_type TEXT
"""


def get_migration_info() -> dict:
    """Return migration metadata."""
    return {
        "name": "001_beta_schema",
        "description": "Add VIX, gold, yield curve, intraday fields for beta release",
        "tables_modified": ["session_snapshots", "notes_archive"],
        "new_columns": {
            "session_snapshots": [
                "vix_close",
                "vix_change_pct",
                "gold_close",
                "gold_change_pct",
                "us_2y_yield",
                "intraday_character",
                "spx_intraday_range_pct",
                "volume_vs_20d_avg",
            ],
            "notes_archive": [
                "hypotheses_tested",
                "hypotheses_confirmed",
                "key_tickers",
                "execution_time_seconds",
                "model_used",
                "risk_tone",
                "session_type",
            ],
        },
    }
