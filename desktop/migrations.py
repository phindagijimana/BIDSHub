"""Versioned schema migrations for the desktop app.

A packaged app can't run the repo's ad-hoc migration scripts by hand, and a
user's database must survive upgrades from one release to the next. This is a
tiny forward-only migration runner: an ordered registry of named, idempotent
steps, each recorded in a ``schema_migrations`` table once applied.

To add a migration for a future release, append a ``(id, fn)`` to
:data:`MIGRATIONS` — never reorder or rename existing ids. ``fn(db_path)`` must
be idempotent (safe to run on an already-current DB) and return True on success.

The baseline here is "init_db + platform constraint", which is what the first
desktop release ships. Older pre-v3 repo databases are out of scope — desktop
users start from a freshly initialised DB.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable, List, Tuple

logger = logging.getLogger("bidshub.desktop")


def _ensure_table(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def applied_migrations(db_path: str) -> set:
    conn = sqlite3.connect(db_path)
    try:
        try:
            return {r[0] for r in conn.execute("SELECT id FROM schema_migrations")}
        except sqlite3.OperationalError:
            return set()  # table not created yet
    finally:
        conn.close()


def _record(db_path: str, migration_id: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (id) VALUES (?)", (migration_id,)
        )
        conn.commit()
    finally:
        conn.close()


# --- migration steps -------------------------------------------------------

def _m_platforms_hpc_remote(db_path: str) -> bool:
    """Ensure the datasets platform CHECK allows hpc + remote_server."""
    from scripts.add_hpc_remote_platforms import migrate_database
    return bool(migrate_database(db_path))


# Ordered, append-only. (id, callable)
MIGRATIONS: List[Tuple[str, Callable[[str], bool]]] = [
    ("0001_platforms_hpc_remote", _m_platforms_hpc_remote),
]


def apply_pending(db_path: str) -> List[str]:
    """Apply every not-yet-applied migration in order; return the ids run.

    Stops at the first failure (so a broken upgrade doesn't cascade) and leaves
    earlier successes recorded. Idempotent: a fully-migrated DB runs nothing.
    """
    _ensure_table(db_path)
    done = applied_migrations(db_path)
    newly: List[str] = []
    for migration_id, fn in MIGRATIONS:
        if migration_id in done:
            continue
        logger.info("Applying migration %s", migration_id)
        try:
            ok = fn(db_path)
        except Exception as exc:
            logger.error("Migration %s raised: %s", migration_id, exc)
            break
        if not ok:
            logger.error("Migration %s reported failure; stopping", migration_id)
            break
        _record(db_path, migration_id)
        newly.append(migration_id)
    return newly
