"""Connection management and initialization for the Database manager."""

import sqlite3
from pathlib import Path


class DatabaseBase:
    """Owns the connection lifecycle shared by every mixin."""

    def __init__(self, db_path=None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, resolved via
                src.app_paths (repo-relative data/bidshub.db by default, or the
                per-user app-data dir when BIDSHUB_DATA_DIR is set — e.g. the
                desktop app). Explicit paths (tests, scripts) are used as-is.
        """
        if db_path is None:
            from src.app_paths import db_path as _resolve_db_path
            db_path = _resolve_db_path()
        self.db_path = db_path

        # Ensure parent directory exists
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Ensure database file exists and is initialized."""
        if not Path(self.db_path).exists():
            from scripts.init_db import init_database
            init_database(self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
