"""
Unit tests for BIDS validator module.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bids_validator import BIDSValidator, validate_bids_dataset


@pytest.fixture
def valid_bids_dataset(tmp_path):
    """Create a minimal valid BIDS dataset."""
    dataset_root = tmp_path / "valid_dataset"
    dataset_root.mkdir()
    
    # Create dataset_description.json
    desc = {
        "Name": "Test Dataset",
        "BIDSVersion": "1.6.0",
        "Authors": ["Test Author"]
    }
    with open(dataset_root / "dataset_description.json", 'w') as f:
        json.dump(desc, f)
    
    # Create a subject directory
    sub_dir = dataset_root / "sub-001"
    sub_dir.mkdir()
    
    # Create anat directory with a file
    anat_dir = sub_dir / "anat"
    anat_dir.mkdir()
    (anat_dir / "sub-001_T1w.nii.gz").touch()
    
    # Create participants.tsv
    participants_content = "participant_id\tage\tsex\nsub-001\t30\tM\n"
    (dataset_root / "participants.tsv").write_text(participants_content)
    
    return dataset_root


@pytest.fixture
def invalid_bids_dataset(tmp_path):
    """Create an invalid BIDS dataset (missing required files)."""
    dataset_root = tmp_path / "invalid_dataset"
    dataset_root.mkdir()
    
    # Create subject but no dataset_description.json
    sub_dir = dataset_root / "sub-001"
    sub_dir.mkdir()
    
    return dataset_root


class TestBIDSValidator:
    """Test suite for BIDSValidator class."""
    
    def test_init(self, tmp_path):
        """Test BIDSValidator initialization."""
        validator = BIDSValidator(str(tmp_path))
        assert validator.bids_root == tmp_path
        assert isinstance(validator.errors, list)
        assert isinstance(validator.warnings, list)
    
    def test_validate_valid_dataset(self, valid_bids_dataset):
        """Test validation of a valid BIDS dataset."""
        validator = BIDSValidator(str(valid_bids_dataset))
        is_valid, errors, warnings = validator.validate()
        
        assert is_valid is True
        assert len(errors) == 0
        # May have warnings (README, CHANGES recommended)
    
    def test_validate_invalid_dataset_missing_description(self, invalid_bids_dataset):
        """Test validation catches missing dataset_description.json."""
        validator = BIDSValidator(str(invalid_bids_dataset))
        is_valid, errors, warnings = validator.validate()
        
        assert is_valid is False
        assert any("dataset_description.json" in err for err in errors)
    
    def test_validate_nonexistent_directory(self, tmp_path):
        """Test validation of non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        validator = BIDSValidator(str(nonexistent))
        is_valid, errors, warnings = validator.validate()
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("does not exist" in err for err in errors)
    
    def test_validate_dataset_description_missing_fields(self, tmp_path):
        """Test validation catches missing required fields in dataset_description.json."""
        dataset_root = tmp_path / "incomplete_desc"
        dataset_root.mkdir()
        
        # Create dataset_description.json with missing required field
        desc = {"Name": "Test"}  # Missing BIDSVersion
        with open(dataset_root / "dataset_description.json", 'w') as f:
            json.dump(desc, f)
        
        validator = BIDSValidator(str(dataset_root))
        is_valid, errors, warnings = validator.validate()
        
        assert is_valid is False
        assert any("BIDSVersion" in err for err in errors)
    
    def test_validate_subject_directories(self, valid_bids_dataset):
        """Test validation of subject directories."""
        validator = BIDSValidator(str(valid_bids_dataset))
        is_valid, errors, warnings = validator.validate()
        
        # Should detect subject directory
        assert is_valid is True
    
    def test_validate_no_subjects(self, tmp_path):
        """Test warning for dataset with no subjects."""
        dataset_root = tmp_path / "no_subjects"
        dataset_root.mkdir()
        
        # Create valid dataset_description.json
        desc = {"Name": "Test", "BIDSVersion": "1.6.0"}
        with open(dataset_root / "dataset_description.json", 'w') as f:
            json.dump(desc, f)
        
        validator = BIDSValidator(str(dataset_root))
        is_valid, errors, warnings = validator.validate()
        
        # Valid but should have warning
        assert is_valid is True
        assert any("No subject directories" in warn for warn in warnings)
    
    def test_validate_participants_file_missing(self, tmp_path):
        """Test warning for missing participants.tsv."""
        dataset_root = tmp_path / "no_participants"
        dataset_root.mkdir()
        
        # Create valid dataset_description.json
        desc = {"Name": "Test", "BIDSVersion": "1.6.0"}
        with open(dataset_root / "dataset_description.json", 'w') as f:
            json.dump(desc, f)
        
        # Create subject
        sub_dir = dataset_root / "sub-001"
        sub_dir.mkdir()
        anat_dir = sub_dir / "anat"
        anat_dir.mkdir()
        (anat_dir / "sub-001_T1w.nii.gz").touch()
        
        validator = BIDSValidator(str(dataset_root))
        is_valid, errors, warnings = validator.validate()
        
        assert is_valid is True
        assert any("participants.tsv" in warn for warn in warnings)
    
    def test_validate_participants_missing_column(self, tmp_path):
        """Test error for participants.tsv missing participant_id column."""
        dataset_root = tmp_path / "bad_participants"
        dataset_root.mkdir()
        
        # Create valid dataset_description.json
        desc = {"Name": "Test", "BIDSVersion": "1.6.0"}
        with open(dataset_root / "dataset_description.json", 'w') as f:
            json.dump(desc, f)
        
        # Create invalid participants.tsv (missing participant_id)
        participants_content = "age\tsex\n30\tM\n"
        (dataset_root / "participants.tsv").write_text(participants_content)
        
        validator = BIDSValidator(str(dataset_root))
        is_valid, errors, warnings = validator.validate()
        
        assert is_valid is False
        assert any("participant_id" in err for err in errors)
    
    def test_get_validation_summary(self, valid_bids_dataset):
        """Test validation summary generation."""
        validator = BIDSValidator(str(valid_bids_dataset))
        validator.validate()
        summary = validator.get_validation_summary()
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        # Should mention dataset is valid or have warnings
    
    def test_validate_with_sessions(self, tmp_path):
        """Test validation of dataset with session structure."""
        dataset_root = tmp_path / "with_sessions"
        dataset_root.mkdir()
        
        # Create dataset_description.json
        desc = {"Name": "Test", "BIDSVersion": "1.6.0"}
        with open(dataset_root / "dataset_description.json", 'w') as f:
            json.dump(desc, f)
        
        # Create subject with session
        sub_dir = dataset_root / "sub-001"
        sub_dir.mkdir()
        ses_dir = sub_dir / "ses-01"
        ses_dir.mkdir()
        anat_dir = ses_dir / "anat"
        anat_dir.mkdir()
        (anat_dir / "sub-001_ses-01_T1w.nii.gz").touch()
        
        validator = BIDSValidator(str(dataset_root))
        is_valid, errors, warnings = validator.validate()
        
        # Should be valid with session structure
        assert is_valid is True


class TestValidateBIDSDatasetFunction:
    """Test suite for validate_bids_dataset convenience function."""
    
    def test_validate_bids_dataset_valid(self, valid_bids_dataset):
        """Test convenience function with valid dataset."""
        is_valid, summary = validate_bids_dataset(str(valid_bids_dataset))
        
        assert isinstance(is_valid, bool)
        assert isinstance(summary, str)
        assert is_valid is True
    
    def test_validate_bids_dataset_invalid(self, invalid_bids_dataset):
        """Test convenience function with invalid dataset."""
        is_valid, summary = validate_bids_dataset(str(invalid_bids_dataset))
        
        assert is_valid is False
        assert "dataset_description.json" in summary


@pytest.mark.integration
class TestBIDSValidatorIntegration:
    """Integration tests for BIDS validator with real-world scenarios."""
    
    def test_complex_dataset_validation(self, tmp_path):
        """Test validation of complex dataset with multiple subjects and modalities."""
        dataset_root = tmp_path / "complex_dataset"
        dataset_root.mkdir()
        
        # Create dataset_description.json
        desc = {
            "Name": "Complex Test Dataset",
            "BIDSVersion": "1.6.0",
            "Authors": ["Author 1", "Author 2"],
            "DatasetDOI": "10.xxxx/xxxxx"
        }
        with open(dataset_root / "dataset_description.json", 'w') as f:
            json.dump(desc, f)
        
        # Create multiple subjects with different modalities
        for sub_id in ['001', '002', '003']:
            sub_dir = dataset_root / f"sub-{sub_id}"
            sub_dir.mkdir()
            
            # Anat
            anat_dir = sub_dir / "anat"
            anat_dir.mkdir()
            (anat_dir / f"sub-{sub_id}_T1w.nii.gz").touch()
            (anat_dir / f"sub-{sub_id}_T2w.nii.gz").touch()
            
            # Func
            func_dir = sub_dir / "func"
            func_dir.mkdir()
            (func_dir / f"sub-{sub_id}_task-rest_bold.nii.gz").touch()
        
        # Create participants.tsv
        participants_content = "participant_id\tage\tsex\n"
        participants_content += "sub-001\t25\tM\n"
        participants_content += "sub-002\t30\tF\n"
        participants_content += "sub-003\t28\tM\n"
        (dataset_root / "participants.tsv").write_text(participants_content)
        
        # Create README
        (dataset_root / "README").write_text("Test dataset")
        
        validator = BIDSValidator(str(dataset_root))
        is_valid, errors, warnings = validator.validate()
        
        assert is_valid is True
        assert len(errors) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
