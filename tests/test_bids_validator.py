"""
Unit tests for BIDS validator (aligned with validate_local_bids / validate_bids_dataset).
"""

import pytest
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bids_validator import BIDSValidator, validate_bids_dataset


@pytest.fixture
def valid_bids_dataset(tmp_path):
    """Create a minimal valid BIDS dataset."""
    dataset_root = tmp_path / "valid_dataset"
    dataset_root.mkdir()

    desc = {
        "Name": "Test Dataset",
        "BIDSVersion": "1.6.0",
        "Authors": ["Test Author"],
    }
    with open(dataset_root / "dataset_description.json", "w") as f:
        json.dump(desc, f)

    sub_dir = dataset_root / "sub-001"
    sub_dir.mkdir()
    anat_dir = sub_dir / "anat"
    anat_dir.mkdir()
    (anat_dir / "sub-001_T1w.nii.gz").touch()

    participants_content = "participant_id\tage\tsex\nsub-001\t25\tM\n"
    (dataset_root / "participants.tsv").write_text(participants_content)

    return dataset_root


@pytest.fixture
def invalid_bids_dataset(tmp_path):
    """Dataset root without dataset_description.json."""
    dataset_root = tmp_path / "invalid_dataset"
    dataset_root.mkdir()
    return dataset_root


class TestValidateLocalBids:
    """Tests for BIDSValidator.validate_local_bids."""

    def test_valid_dataset(self, valid_bids_dataset):
        v = BIDSValidator()
        ok, msg = v.validate_local_bids(str(valid_bids_dataset))
        assert ok is True
        assert isinstance(msg, str)

    def test_missing_description(self, invalid_bids_dataset):
        v = BIDSValidator()
        ok, msg = v.validate_local_bids(str(invalid_bids_dataset))
        assert ok is False
        assert "dataset_description.json" in msg

    def test_nonexistent_path(self, tmp_path):
        v = BIDSValidator()
        ok, msg = v.validate_local_bids(str(tmp_path / "nope"))
        assert ok is False
        assert "not found" in msg.lower() or "Directory" in msg

    def test_missing_bidsversion_in_description(self, tmp_path):
        root = tmp_path / "bad_desc"
        root.mkdir()
        with open(root / "dataset_description.json", "w") as f:
            json.dump({"Name": "X"}, f)
        sub = root / "sub-01"
        sub.mkdir()
        (sub / "anat").mkdir()
        (sub / "anat" / "sub-01_T1w.nii.gz").touch()

        v = BIDSValidator()
        ok, msg = v.validate_local_bids(str(root))
        assert ok is False
        assert "BIDSVersion" in msg


class TestValidateBidsDatasetFunction:
    def test_convenience_valid(self, valid_bids_dataset):
        ok, msg = validate_bids_dataset(str(valid_bids_dataset))
        assert ok is True
        assert isinstance(msg, str)

    def test_convenience_invalid(self, invalid_bids_dataset):
        ok, msg = validate_bids_dataset(str(invalid_bids_dataset))
        assert ok is False


@pytest.mark.integration
def test_multisubject_dataset(tmp_path):
    """Larger tree still validates."""
    root = tmp_path / "multi"
    root.mkdir()
    with open(root / "dataset_description.json", "w") as f:
        json.dump({"Name": "C", "BIDSVersion": "1.6.0"}, f)
    (root / "participants.tsv").write_text("participant_id\nsub-001\n")
    for sid in ("001", "002"):
        d = root / f"sub-{sid}" / "anat"
        d.mkdir(parents=True)
        (d / f"sub-{sid}_T1w.nii.gz").touch()
    v = BIDSValidator()
    ok, _ = v.validate_local_bids(str(root))
    assert ok is True
