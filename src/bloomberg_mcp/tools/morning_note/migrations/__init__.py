"""Database migrations for morning note historical data.

This module manages schema evolution for the morning_note_history.db database.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from ..historical import get_db_connection, DEFAULT_DB_PATH


def get_applied_migrations(db_path: Optional[Path] = None) -> List[str]:
    """Get list of applied migration names."""
    conn = get_db_connection(db_path)
    try:
        # Create migrations table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        cursor = conn.execute("SELECT name FROM _migrations ORDER BY applied_at")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def mark_migration_applied(name: str, db_path: Optional[Path] = None) -> None:
    """Mark a migration as applied."""
    conn = get_db_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
            (name, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def run_migration(
    name: str,
    sql: str,
    db_path: Optional[Path] = None,
    force: bool = False,
) -> bool:
    """Run a single migration.

    Args:
        name: Migration name (e.g., "001_beta_schema")
        sql: SQL to execute
        db_path: Database path
        force: Re-run even if already applied

    Returns:
        True if migration was applied, False if skipped
    """
    applied = get_applied_migrations(db_path)

    if name in applied and not force:
        print(f"Migration {name} already applied, skipping")
        return False

    conn = get_db_connection(db_path)
    try:
        # SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS
        # So we need to handle each column carefully
        for statement in sql.strip().split(";"):
            statement = statement.strip()
            if not statement:
                continue
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    # Column already exists, skip
                    continue
                raise

        conn.commit()
        mark_migration_applied(name, db_path)
        print(f"Migration {name} applied successfully")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Migration {name} failed: {e}")
        raise
    finally:
        conn.close()


def run_all_migrations(db_path: Optional[Path] = None) -> int:
    """Run all pending migrations.

    Returns:
        Number of migrations applied
    """
    from . import beta_schema
    from . import news_events
    from . import news_published_date

    migrations = [
        ("001_beta_schema", beta_schema.MIGRATION_SQL),
        ("002_news_events", news_events.MIGRATION_SQL),
        ("003_news_published_date", news_published_date.MIGRATION_SQL),
    ]

    applied_count = 0
    for name, sql in migrations:
        if run_migration(name, sql, db_path):
            applied_count += 1

    return applied_count
