"""Regression tests for remote BIDS validation (no network — file list stubbed).

Remote file listings from these platforms are one directory level deep, so
nested modality folders aren't visible. Missing modality folders must therefore
be a *warning*, not a hard failure (otherwise valid datasets like OpenNeuro are
rejected). dataset_description.json remains required.
"""

from src.bids_validator import BIDSValidator


def test_missing_modality_folders_is_warning_not_failure(monkeypatch):
    v = BIDSValidator()
    # Top-level BIDS listing: description + participants + subject folders,
    # but no visible modality folders (they're nested, not in this listing).
    monkeypatch.setattr(
        v, "_get_file_list",
        lambda agent, ds, plat: ["dataset_description.json", "participants.tsv", "sub-01", "sub-02"],
    )
    monkeypatch.setattr(
        v, "_validate_dataset_description",
        lambda agent, ds, plat, files: (True, "", "1.8.0"),
    )
    ok, msg, details = v.validate_remote_dataset(agent=None, dataset_id="ds000003", platform="openneuro")
    assert ok is True, msg
    assert details["subject_count"] == 2


def test_missing_dataset_description_fails(monkeypatch):
    v = BIDSValidator()
    # No dataset_description.json (typical of a non-BIDS DANDI/NWB dandiset).
    monkeypatch.setattr(
        v, "_get_file_list",
        lambda agent, ds, plat: ["sub-01", "data.nwb"],
    )
    ok, msg, _ = v.validate_remote_dataset(agent=None, dataset_id="000003", platform="dandi")
    assert ok is False
    assert "dataset_description.json" in msg


def test_no_subjects_fails(monkeypatch):
    v = BIDSValidator()
    monkeypatch.setattr(
        v, "_get_file_list",
        lambda agent, ds, plat: ["dataset_description.json", "README"],
    )
    monkeypatch.setattr(
        v, "_validate_dataset_description",
        lambda agent, ds, plat, files: (True, "", "1.8.0"),
    )
    ok, msg, _ = v.validate_remote_dataset(agent=None, dataset_id="x", platform="openneuro")
    assert ok is False
    assert "subject" in msg.lower()
