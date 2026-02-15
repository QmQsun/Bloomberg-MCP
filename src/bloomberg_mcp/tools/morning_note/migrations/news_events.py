"""Migration: Add news_events table for historical news context.

This migration creates the news_events table which stores:
- Classified news articles by type (macro, central_bank, sector, thematic)
- Sentiment and Japan relevance scoring
- Ticker/sector/theme associations for querying

The table links to session_snapshots via session_date and enables:
- Historical news pattern analysis
- Theme tracking across sessions
- Japan readthrough documentation
"""

MIGRATION_SQL = """
-- News events table for historical news context
CREATE TABLE IF NOT EXISTS news_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date DATE NOT NULL,
    news_type TEXT NOT NULL,
    headline TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    source_url TEXT,
    tickers_json TEXT,
    sectors_json TEXT,
    themes_json TEXT,
    sentiment TEXT,
    japan_relevance REAL,
    japan_readthroughs_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_date, headline)
);

CREATE INDEX IF NOT EXISTS idx_news_events_date ON news_events(session_date);
CREATE INDEX IF NOT EXISTS idx_news_events_type ON news_events(news_type);
CREATE INDEX IF NOT EXISTS idx_news_events_sentiment ON news_events(sentiment);
"""
