"""Tests for the desktop versioned migration runner."""

import os
import sqlite3
import tempfile
from pathlib import Path

from scripts.init_db import init_database
from desktop import migrations


def _fresh_db() -> str:
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "bidshub.db")
    assert init_database(db_path)
    return db_path


def test_apply_pending_runs_baseline_and_records_it():
    db = _fresh_db()
    ran = migrations.apply_pending(db)
    assert "0001_platforms_hpc_remote" in ran
    # Recorded in schema_migrations
    assert "0001_platforms_hpc_remote" in migrations.applied_migrations(db)
    # Effect: datasets CHECK now allows hpc + remote_server
    conn = sqlite3.connect(db)
    try:
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert "'hpc'" in schema and "'remote_server'" in schema


def test_apply_pending_is_idempotent():
    db = _fresh_db()
    first = migrations.apply_pending(db)
    second = migrations.apply_pending(db)
    assert first  # something ran the first time
    assert second == []  # nothing left to do


def test_applied_migrations_empty_before_table_exists():
    db = _fresh_db()
    # init_db doesn't create schema_migrations; query must not raise.
    assert migrations.applied_migrations(db) == set()


def test_failure_stops_and_does_not_record(monkeypatch):
    db = _fresh_db()

    def boom(_db_path):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(migrations, "MIGRATIONS", [("9999_boom", boom)])
    ran = migrations.apply_pending(db)
    assert ran == []
    assert "9999_boom" not in migrations.applied_migrations(db)
