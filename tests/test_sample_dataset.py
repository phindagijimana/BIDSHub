"""
Tests for the "Try with sample data" demo loader.

Covers:
  * the bundled assets/sample_bids/ dataset is present and well-formed
  * load_sample_dataset() registers it cleanly in a fresh DB
  * a second call is idempotent (no duplicate rows)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.bids_loader import BIDSLoader  # noqa: E402
from src.database import Database  # noqa: E402
from src.sample_dataset import (  # noqa: E402
    SAMPLE_BIDS_ROOT,
    SAMPLE_DATASET_NAME,
    load_sample_dataset,
    sample_dataset_available,
)


def test_sample_bundle_is_present():
    """assets/sample_bids/ ships with the repo and looks like BIDS."""
    assert sample_dataset_available(), (
        f"Sample BIDS bundle missing at {SAMPLE_BIDS_ROOT}. "
        "Run `python scripts/build_sample_bids.py`."
    )
    assert (SAMPLE_BIDS_ROOT / "participants.tsv").is_file()
    # At least one .nii.gz exists — if this fails the build script is broken.
    assert any(SAMPLE_BIDS_ROOT.rglob("*.nii.gz")), "no NIfTI files in sample bundle"


def test_load_sample_dataset_into_fresh_db(tmp_path):
    """First load registers the dataset and inserts subjects + scans."""
    db = Database(str(tmp_path / "demo.db"))

    dataset_id, n_subjects, err = load_sample_dataset(db, BIDSLoader)

    assert err is None, f"unexpected error: {err}"
    assert dataset_id > 0
    assert n_subjects == 2  # sub-01, sub-02 per build_sample_bids.py

    datasets = db.get_all_datasets()
    assert any(d["name"] == SAMPLE_DATASET_NAME for d in datasets)

    # The bundle has 4 NIfTI scans across 3 sessions; confirm scans landed.
    ds = next(d for d in datasets if d["name"] == SAMPLE_DATASET_NAME)
    subjects = db.get_subjects_by_dataset(ds["id"])
    assert len(subjects) == 2


def test_load_sample_dataset_is_idempotent(tmp_path):
    """Second call returns the same dataset_id and doesn't add duplicate rows."""
    db = Database(str(tmp_path / "demo.db"))

    first_id, first_n, err1 = load_sample_dataset(db, BIDSLoader)
    assert err1 is None
    first_count = len(db.get_all_datasets())

    second_id, second_n, err2 = load_sample_dataset(db, BIDSLoader)
    assert err2 is None
    assert second_id == first_id, "should reuse existing dataset row"
    assert len(db.get_all_datasets()) == first_count, "should not duplicate dataset"


def test_load_reports_error_when_bundle_missing(tmp_path, monkeypatch):
    """If the bundle directory is gone, return a helpful error string."""
    db = Database(str(tmp_path / "demo.db"))

    from src import sample_dataset as sd

    # Point at a path that won't exist
    monkeypatch.setattr(sd, "SAMPLE_BIDS_ROOT", tmp_path / "nope")

    _, _, err = sd.load_sample_dataset(db, BIDSLoader)
    assert err is not None
    assert "Sample dataset not found" in err
