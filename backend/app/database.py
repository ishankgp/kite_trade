"""Database utilities for the @nifty_ml backend."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import get_settings


def init_db() -> None:
    """Ensure the target database exists and has expected tables."""
    settings = get_settings()
    db_path = Path(settings.database_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database {db_path} not found. Run scripts/fetch_price_history.py to create it."
        )

    # Verify schema
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        required_tables = {"instruments", "price_bars"}
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        missing = required_tables - tables
        if missing:
            raise RuntimeError(
                f"Database missing tables: {missing}. Ensure fetch_price_history.py populated the schema."
            )


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


