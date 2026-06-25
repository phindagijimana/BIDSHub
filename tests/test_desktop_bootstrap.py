"""Tests for the desktop first-launch bootstrap (Phase 1).

Verify that pointing BIDSHUB_DATA_DIR at a fresh per-user directory produces a
usable database on the current schema, without touching the repo's ./data.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from desktop import bootstrap as boot


@pytest.fixture
def clean_env(monkeypatch):
    """Isolate BIDSHUB_DATA_DIR for the test and restore it afterwards.

    bootstrap() writes os.environ directly (not via monkeypatch), so we capture
    and restore the originals ourselves to avoid leaking a data dir into the
    rest of the suite (Database() resolves its default path from this env).
    """
    saved = {k: os.environ.get(k) for k in ("BIDSHUB_DATA_DIR", "BIDSHUB_DOWNLOAD_DIR")}
    os.environ.pop("BIDSHUB_DATA_DIR", None)
    os.environ.pop("BIDSHUB_DOWNLOAD_DIR", None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_prepare_environment_sets_and_creates_dir(clean_env, monkeypatch):
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / "BIDSHub"
    resolved = boot.prepare_environment(str(target))
    assert os.environ["BIDSHUB_DATA_DIR"] == str(target)
    assert resolved == target
    assert target.is_dir()


def test_prepare_environment_writes_navy_theme(clean_env):
    # The embedded server reads .streamlit/config.toml from the data dir (its
    # cwd); without the navy primaryColor the app shows Streamlit's red accent.
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / "BIDSHub"
    boot.prepare_environment(str(target))
    cfg = target / ".streamlit" / "config.toml"
    assert cfg.exists()
    assert 'primaryColor = "#002d72"' in cfg.read_text()


def test_prepare_environment_respects_existing_env(clean_env, monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("BIDSHUB_DATA_DIR", tmp)
    # No explicit data_dir -> must not override the caller's env value.
    resolved = boot.prepare_environment()
    assert os.environ["BIDSHUB_DATA_DIR"] == tmp
    assert resolved == Path(tmp)


def test_bootstrap_creates_database_with_current_schema(clean_env):
    tmp = tempfile.mkdtemp()
    info = boot.bootstrap(str(Path(tmp) / "BIDSHub"))

    db_path = info["db_path"]
    # DB lives under the per-user dir, not repo ./data
    assert info["data_dir"] in db_path
    assert Path(db_path).exists()

    conn = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert {"datasets", "subjects", "scans", "subject_sessions",
                "download_queue", "qc_history", "metadata"} <= tables

        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets'"
        ).fetchone()[0]
        # Current platform constraint must allow hpc + remote_server
        assert "'hpc'" in schema and "'remote_server'" in schema
    finally:
        conn.close()


def test_bootstrap_is_idempotent_and_preserves_data(clean_env):
    tmp = tempfile.mkdtemp()
    target = str(Path(tmp) / "BIDSHub")
    info = boot.bootstrap(target)
    db_path = info["db_path"]

    # Insert a row, then bootstrap again: it must not wipe or recreate the DB.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO datasets (name, platform, status) VALUES ('keep', 'hpc', 'active')"
    )
    conn.commit()
    conn.close()

    info2 = boot.bootstrap(target)
    assert info2["db_path"] == db_path

    conn = sqlite3.connect(db_path)
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM datasets")]
    finally:
        conn.close()
    assert "keep" in names  # survived the second bootstrap


def test_bootstrap_db_accepts_hpc_dataset(clean_env):
    """A fresh desktop DB must accept the platforms the app actually uses."""
    from src.database import Database

    tmp = tempfile.mkdtemp()
    boot.bootstrap(str(Path(tmp) / "BIDSHub"))
    db = Database()  # resolves path via app_paths / BIDSHUB_DATA_DIR

    assert db.add_dataset(name="hpc-ds", platform="hpc") is not None
    assert db.add_dataset(name="remote-ds", platform="remote_server") is not None
