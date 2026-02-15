"""Migration: Add published_date to news_events for article dating.

This migration adds:
- published_date: The actual article publication timestamp (when available)

The session_date remains as "which session this news was collected for",
while published_date captures when the article was actually published.
"""

MIGRATION_SQL = """
ALTER TABLE news_events ADD COLUMN published_date TIMESTAMP;
"""
