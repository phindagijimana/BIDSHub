"""Phase 1 — make BIDSHub run against a writable per-user data directory.

A packaged desktop app runs from a read-only location (a macOS ``.app`` or a
Windows ``Program Files`` install), so it cannot keep its SQLite database under
the bundle the way the native ``./hub`` flow keeps it under ``./data``. This
module relocates all mutable state to the OS per-user app-data dir and ensures
the database exists and is on the current schema before the app starts.

It is the single thing the desktop entry point must call first::

    from desktop.bootstrap import bootstrap
    info = bootstrap()          # sets env, creates/migrates the DB
    # ... now safe to import app code / start Streamlit ...

Everything here is idempotent and safe to run on every launch. The native and
Docker flows never call it, so they keep using repo-relative ``./data``.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bidshub.desktop")


def prepare_environment(data_dir: Optional[str] = None) -> Path:
    """Point BIDSHub at a writable per-user data directory.

    Sets ``BIDSHUB_DATA_DIR`` (so :mod:`src.app_paths` resolves the database,
    downloads and cohorts under it) unless it is already set — an explicit
    value from the caller/env always wins, which keeps tests and power users in
    control. Returns the resolved, created directory.
    """
    # Import here so setting the env var happens before app_paths is first used.
    from src.app_paths import platform_data_dir, ensure_data_dir

    if data_dir:
        os.environ["BIDSHUB_DATA_DIR"] = str(Path(data_dir).expanduser())
    elif not os.environ.get("BIDSHUB_DATA_DIR"):
        os.environ["BIDSHUB_DATA_DIR"] = str(platform_data_dir())

    resolved = ensure_data_dir()
    logger.info("BIDSHub data directory: %s", resolved)
    return resolved


def _platform_constraint_current(db_path: str) -> bool:
    """True if the datasets CHECK already allows the v3.1.1 platforms."""
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets'"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    schema = row[0] if row else ""
    return "'hpc'" in schema and "'remote_server'" in schema


def ensure_database() -> str:
    """Create the database on first run and migrate it to the current schema.

    - If the DB file is missing, initialise it with the canonical schema.
    - Apply any pending versioned migrations (recorded in ``schema_migrations``)
      so a database created by an older release upgrades cleanly.

    Returns the resolved database path. Idempotent: a fully-migrated DB runs no
    migrations.
    """
    from src.app_paths import db_path as resolve_db_path
    from desktop.migrations import apply_pending

    db_path = resolve_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    if not Path(db_path).exists():
        logger.info("Initialising new database at %s", db_path)
        from scripts.init_db import init_database
        if not init_database(db_path):
            raise RuntimeError(f"Failed to initialise database at {db_path}")

    newly = apply_pending(db_path)
    if newly:
        logger.info("Applied migrations: %s", ", ".join(newly))

    return db_path


def bootstrap(data_dir: Optional[str] = None) -> dict:
    """Run the full first-launch preparation and return resolved paths.

    Order matters: the environment must be pointed at the data dir *before* the
    database path is resolved, so do not reorder these two calls.
    """
    resolved_dir = prepare_environment(data_dir)
    db_path = ensure_database()
    return {"data_dir": str(resolved_dir), "db_path": db_path}


if __name__ == "__main__":  # manual smoke check: `python -m desktop.bootstrap`
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    info = bootstrap()
    print("data_dir:", info["data_dir"])
    print("db_path :", info["db_path"])
