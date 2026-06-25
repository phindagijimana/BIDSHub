"""Central resolution of where BIDSHub reads/writes mutable state.

Why this exists
---------------
The native ``./hub`` flow and Docker write the database under the repo
(``data/bidshub.db``). A packaged desktop app (PyInstaller bundle) runs from a
*read-only* location (e.g. a macOS ``.app``), so it must keep its database and
downloads in a per-user, writable directory instead.

This module is the single source of truth for those paths. Behaviour is driven
by environment variables so existing flows are untouched:

- ``BIDSHUB_DATA_DIR``  — overrides the data directory (DB lives here). The
  desktop launcher sets this to the OS-specific app-data dir.
- ``BIDSHUB_DOWNLOAD_DIR`` — overrides the default downloads directory.

With no env set, ``data_dir()`` returns the repo-relative ``data/`` so
``./hub``, Docker, ``scripts/init_db.py`` and the test suite behave exactly as
before.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "BIDSHub"


def platform_data_dir() -> Path:
    """OS-appropriate per-user application-data directory for BIDSHub.

    Used by the desktop launcher to populate ``BIDSHUB_DATA_DIR``. Not used by
    the native/Docker flows (which keep the repo-relative ``data/``).
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    # Linux / other: follow the XDG base-directory spec.
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def data_dir() -> Path:
    """Directory holding the database (and other mutable app state)."""
    override = os.environ.get("BIDSHUB_DATA_DIR")
    if override:
        return Path(override).expanduser()
    # Default preserves legacy behaviour: repo-relative ./data
    return Path("data")


def ensure_data_dir() -> Path:
    """Return :func:`data_dir`, creating it if needed."""
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> str:
    """Absolute/relative path to the SQLite database file."""
    return str(data_dir() / "bidshub.db")


def downloads_dir() -> Path:
    """Default directory new downloads are saved to.

    In desktop mode (``BIDSHUB_DATA_DIR`` set) this lives under the app-data
    dir; otherwise it preserves the legacy ``~/data-explorer/datasets``
    default so the native flow is unchanged.
    """
    override = os.environ.get("BIDSHUB_DOWNLOAD_DIR")
    if override:
        return Path(override).expanduser()
    if os.environ.get("BIDSHUB_DATA_DIR"):
        return data_dir() / "datasets"
    return Path.home() / "data-explorer" / "datasets"


def dataset_metadata_dir(dataset_id) -> Path:
    """Per-dataset cache dir for synced metadata (e.g. a participants.tsv).

    Cloud datasets that haven't been downloaded have no on-disk BIDS tree, so
    when a Sync fetches subject demographics from the platform we cache them
    here as a participants.tsv. The Browse/QC tables read this as a fallback so
    age/sex/diagnosis show up for cloud datasets too. Kept under the data dir
    (not the dataset's root_path) so it never gets confused with downloaded data.
    """
    return data_dir() / "metadata_cache" / f"dataset_{dataset_id}"


def cohorts_dir() -> Path:
    """Default directory exported cohorts are written to.

    Mirrors :func:`downloads_dir`: in desktop mode (``BIDSHUB_DATA_DIR`` set)
    it lives under the app-data dir; otherwise it preserves the legacy
    ``~/data-explorer/cohorts`` default so the native flow is unchanged.
    """
    if os.environ.get("BIDSHUB_DATA_DIR"):
        return data_dir() / "cohorts"
    return Path.home() / "data-explorer" / "cohorts"
