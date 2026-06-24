"""Regression tests for multi-dataset Browse / QC / Viewer / Subject Detail.

These lock in three fixes that only surface once data spanning multiple
platforms (and sharing BIDS subject labels) is loaded:

1. The subjects table sources demographics from participants.tsv and
   session/scan/modality counts from the database (the v3 ``subjects`` table
   no longer carries them as columns).
2. Scan lookups are scoped to the selected dataset, so a label like
   ``sub-01`` present in several datasets resolves to the right file.
3. A subject can be fetched scoped to its dataset by either its BIDS label
   or its local id.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.database import Database
from src.utils import (
    enrich_subjects_for_display,
    create_subject_dataframe,
    get_session_labels,
    _format_modalities,
)


def _write_participants(root: Path, rows):
    """rows: list of (participant_id, age, sex, diagnosis)."""
    root.mkdir(parents=True, exist_ok=True)
    lines = ["participant_id\tage\tsex\tdiagnosis"]
    lines += ["\t".join(str(c) for c in r) for r in rows]
    (root / "participants.tsv").write_text("\n".join(lines) + "\n")


@pytest.fixture
def multi_ds():
    """Two datasets that both contain ``sub-01`` (label collision).

    Dataset A (local):   sub-01 with anat T1w + func bold, downloaded on disk.
    Dataset B (pennsieve): sub-01 with dwi, NOT downloaded.
    Each has a participants.tsv with distinct demographics.
    """
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    db = Database(db_path)

    root_a = Path(tmp) / "ds_a"
    root_b = Path(tmp) / "ds_b"
    _write_participants(root_a, [("sub-01", 28, "M", "TBI")])
    _write_participants(root_b, [("sub-01", 51, "F", "stroke")])

    id_a = db.add_dataset(name="DS A", platform="local", root_path=str(root_a))
    id_b = db.add_dataset(name="DS B", platform="pennsieve", root_path=str(root_b))

    # Dataset A: sub-01, one session, two modalities, files on disk
    db.add_subject(dataset_id=id_a, subject_id="sub-01", local_subject_id="01")
    for suffix, mod in [("T1w", "anat"), ("bold", "func")]:
        f = root_a / "sub-01" / "ses-01" / mod / f"sub-01_ses-01_{suffix}.nii.gz"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 1024)
        db.add_scan(subject_id="sub-01", dataset_id=id_a, session="ses-01",
                    modality=mod, suffix=suffix, file_path=str(f),
                    file_size_bytes=1024, is_downloaded=True)
    db.add_subject_session(subject_id="sub-01", dataset_id=id_a,
                           session_id="ses-01", scan_count=2)

    # Dataset B: sub-01, different session/modality, NOT downloaded
    db.add_subject(dataset_id=id_b, subject_id="sub-01", local_subject_id="01")
    fb = root_b / "sub-01" / "ses-99" / "dwi" / "sub-01_ses-99_dwi.nii.gz"
    db.add_scan(subject_id="sub-01", dataset_id=id_b, session="ses-99",
                modality="dwi", suffix="dwi", file_path=str(fb),
                file_size_bytes=9_000_000, is_downloaded=False)
    db.add_subject_session(subject_id="sub-01", dataset_id=id_b,
                           session_id="ses-99", scan_count=1)

    yield {"db": db, "id_a": id_a, "id_b": id_b, "root_a": root_a, "root_b": root_b}

    try:
        os.remove(db_path)
    except OSError:
        pass


# --- Fix #1: display stats + enrichment ------------------------------------

def test_display_stats_per_dataset(multi_ds):
    db, id_a, id_b = multi_ds["db"], multi_ds["id_a"], multi_ds["id_b"]

    stats_a = db.get_display_stats_for_dataset(id_a)
    assert "sub-01" in stats_a
    assert stats_a["sub-01"]["scan_count"] == 2
    assert stats_a["sub-01"]["session_labels"] == "ses-01"
    assert sorted(stats_a["sub-01"]["modalities"]) == ["anat", "func"]

    stats_b = db.get_display_stats_for_dataset(id_b)
    assert stats_b["sub-01"]["scan_count"] == 1
    assert stats_b["sub-01"]["modalities"] == ["dwi"]
    assert stats_b["sub-01"]["session_labels"] == "ses-99"


def test_enrich_populates_demographics_and_counts(multi_ds):
    db, id_a = multi_ds["db"], multi_ds["id_a"]
    subjects = db.get_subjects_by_dataset(id_a)
    enrich_subjects_for_display(subjects, db)

    s = subjects[0]
    # Demographics from participants.tsv
    assert s["age"] == 28
    assert s["sex"] == "M"
    assert s["diagnosis"] == "TBI"
    # Counts from the database
    assert s["scan_count"] == 2
    assert s["session_labels"] == "ses-01"
    assert sorted(s["modalities_list"]) == ["anat", "func"]


def test_subject_dataframe_shows_enriched_values(multi_ds):
    db, id_a = multi_ds["db"], multi_ds["id_a"]
    subjects = db.get_subjects_by_dataset(id_a)
    enrich_subjects_for_display(subjects, db)
    df = create_subject_dataframe(subjects)

    row = df.iloc[0]
    assert float(row["Age"]) == 28.0
    assert row["Sex"] == "M"
    assert row["Diagnosis"] == "TBI"
    assert row["Sessions"] == "ses-01"
    assert row["Scans"] == "2"
    assert row["Modalities"]  # non-empty (e.g. "T1/T2, fMRI")
    # The regression we are guarding against: blanks / "None" / "0".
    assert row["Sessions"] != "None"
    assert row["Scans"] != "0"


def test_demographics_blank_without_regression_when_no_tsv(multi_ds):
    """Enrichment must not crash when a dataset has no participants.tsv."""
    db = multi_ds["db"]
    root_c = multi_ds["root_a"].parent / "ds_c"
    root_c.mkdir(parents=True, exist_ok=True)  # no participants.tsv
    id_c = db.add_dataset(name="DS C", platform="xnat", root_path=str(root_c))
    db.add_subject(dataset_id=id_c, subject_id="sub-07", local_subject_id="07")

    subjects = db.get_subjects_by_dataset(id_c)
    enrich_subjects_for_display(subjects, db)  # should be a no-op, not raise
    assert subjects[0].get("age") is None
    assert subjects[0]["scan_count"] == 0
    assert subjects[0]["session_labels"] == "None"


# --- Fix #2: dataset-scoped scan lookup ------------------------------------

def test_scans_scoped_to_selected_dataset(multi_ds):
    db, id_a, id_b = multi_ds["db"], multi_ds["id_a"], multi_ds["id_b"]

    scans_a = db.get_scans_by_subject("sub-01", dataset_id=id_a)
    assert {s["modality"] for s in scans_a} == {"anat", "func"}
    assert all(s["dataset_id"] == id_a for s in scans_a)
    # Dataset B's undownloaded dwi must NOT leak in.
    assert all(s["modality"] != "dwi" for s in scans_a)

    scans_b = db.get_scans_by_subject("sub-01", dataset_id=id_b)
    assert {s["modality"] for s in scans_b} == {"dwi"}
    assert all(s["dataset_id"] == id_b for s in scans_b)


def test_unscoped_lookup_sees_both_datasets(multi_ds):
    """Documents why scoping matters: the label exists in both datasets."""
    db = multi_ds["db"]
    all_scans = db.get_scans_by_subject("sub-01")  # no dataset_id
    mods = {s["modality"] for s in all_scans}
    assert mods == {"anat", "func", "dwi"}


# --- Fix #3: dataset-scoped subject fetch ----------------------------------

def test_get_subject_scoped_by_bids_label(multi_ds):
    db, id_a, id_b = multi_ds["db"], multi_ds["id_a"], multi_ds["id_b"]

    sub_a = db.get_subject("sub-01", dataset_id=id_a)
    sub_b = db.get_subject("sub-01", dataset_id=id_b)
    assert sub_a is not None and sub_b is not None
    assert sub_a["dataset_id"] == id_a
    assert sub_b["dataset_id"] == id_b
    assert sub_a["id"] != sub_b["id"]


def test_get_subject_scoped_by_local_id(multi_ds):
    """Scoped lookup still matches the local id (backwards compatibility)."""
    db, id_a = multi_ds["db"], multi_ds["id_a"]
    sub = db.get_subject("01", dataset_id=id_a)
    assert sub is not None
    assert sub["dataset_id"] == id_a
    assert sub["subject_id"] == "sub-01"
