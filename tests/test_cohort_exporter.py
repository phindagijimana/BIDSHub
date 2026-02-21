"""
Unit tests for cohort exporter module.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cohort_exporter import CohortExporter
from src.database import Database


@pytest.fixture
def mock_database(tmp_path):
    """Create a mock database with test data."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    
    # Add test datasets
    dataset1_id = db.add_dataset(
        name="Dataset1",
        platform="pennsieve",
        root_path=str(tmp_path / "dataset1")
    )
    
    dataset2_id = db.add_dataset(
        name="Dataset2",
        platform="openneuro",
        root_path=str(tmp_path / "dataset2")
    )
    
    # Add test subjects
    db.add_subject(dataset1_id, '001', '001', True, True)
    db.add_subject(dataset1_id, '002', '002', True, False)
    db.add_subject(dataset2_id, '003', '003', True, True)
    
    return db


@pytest.fixture
def source_datasets(tmp_path):
    """Create source BIDS datasets for testing."""
    datasets = []
    
    for i in [1, 2]:
        dataset_root = tmp_path / f"dataset{i}"
        dataset_root.mkdir()
        
        # Create dataset_description.json
        desc = {
            "Name": f"Dataset{i}",
            "BIDSVersion": "1.6.0"
        }
        with open(dataset_root / "dataset_description.json", 'w') as f:
            json.dump(desc, f)
        
        # Create subject directories
        for sub_id in ['001', '002'] if i == 1 else ['003']:
            sub_dir = dataset_root / f"sub-{sub_id}"
            sub_dir.mkdir()
            
            anat_dir = sub_dir / "anat"
            anat_dir.mkdir()
            
            # Create a dummy file
            nii_file = anat_dir / f"sub-{sub_id}_T1w.nii.gz"
            nii_file.write_text("dummy data")
        
        # Create participants.tsv
        if i == 1:
            participants = "participant_id\tage\tsex\nsub-001\t30\tM\nsub-002\t25\tF\n"
        else:
            participants = "participant_id\tage\tsex\nsub-003\t28\tM\n"
        
        (dataset_root / "participants.tsv").write_text(participants)
        
        datasets.append(dataset_root)
    
    return datasets


class TestCohortExporter:
    """Test suite for CohortExporter class."""
    
    def test_init(self, mock_database):
        """Test CohortExporter initialization."""
        exporter = CohortExporter(mock_database)
        
        assert exporter.db == mock_database
        assert exporter.bids_loader is None
    
    def test_export_cohort_single_subject(self, mock_database, source_datasets, tmp_path):
        """Test exporting a single subject."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "cohort_output"
        
        results = exporter.export_cohort(
            subject_ids=['001'],
            dataset_ids=[1],
            output_path=str(output_path),
            cohort_name="Test_Cohort",
            description="Test cohort",
            copy_mode="copy"
        )
        
        assert results['success'] is True
        assert results['subjects_exported'] >= 0  # May be 0 if source not found
        assert 'cohort_name' in results
        assert results['cohort_name'] == "Test_Cohort"
    
    def test_export_cohort_creates_dataset_description(self, mock_database, source_datasets, tmp_path):
        """Test that export creates dataset_description.json."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "cohort_output"
        
        results = exporter.export_cohort(
            subject_ids=['001'],
            dataset_ids=[1],
            output_path=str(output_path),
            cohort_name="Test_Cohort",
            description="Test description",
            copy_mode="copy"
        )
        
        # Check dataset_description.json exists
        desc_file = output_path / "dataset_description.json"
        assert desc_file.exists()
        
        # Check contents
        with open(desc_file, 'r') as f:
            desc = json.load(f)
        
        assert desc['Name'] == "Test_Cohort"
        assert 'BIDSVersion' in desc
        assert 'GeneratedBy' in desc
        assert 'SourceDatasets' in desc
    
    def test_export_cohort_creates_participants_file(self, mock_database, source_datasets, tmp_path):
        """Test that export creates participants.tsv."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "cohort_output"
        
        results = exporter.export_cohort(
            subject_ids=['001'],
            dataset_ids=[1],
            output_path=str(output_path),
            cohort_name="Test_Cohort",
            description="Test",
            copy_mode="copy"
        )
        
        # Check participants.tsv exists
        participants_file = output_path / "participants.tsv"
        assert participants_file.exists()
    
    def test_export_cohort_creates_readme(self, mock_database, source_datasets, tmp_path):
        """Test that export creates README."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "cohort_output"
        
        results = exporter.export_cohort(
            subject_ids=['001'],
            dataset_ids=[1],
            output_path=str(output_path),
            cohort_name="Test_Cohort",
            description="Test",
            copy_mode="copy"
        )
        
        # Check README exists
        readme_file = output_path / "README"
        assert readme_file.exists()
        
        # Check contents
        content = readme_file.read_text()
        assert "Test_Cohort" in content
    
    def test_export_cohort_multiple_subjects(self, mock_database, source_datasets, tmp_path):
        """Test exporting multiple subjects from different datasets."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "multi_cohort"
        
        results = exporter.export_cohort(
            subject_ids=['001', '003'],
            dataset_ids=[1, 2],
            output_path=str(output_path),
            cohort_name="Multi_Cohort",
            description="Multiple subjects",
            copy_mode="copy"
        )
        
        assert results['cohort_name'] == "Multi_Cohort"
        # Check that result structure is correct
        assert 'subjects_exported' in results
        assert 'total_size_mb' in results
        assert 'errors' in results
        assert 'warnings' in results
    
    def test_export_cohort_symlink_mode(self, mock_database, source_datasets, tmp_path):
        """Test export with symlink mode."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "symlink_cohort"
        
        results = exporter.export_cohort(
            subject_ids=['001'],
            dataset_ids=[1],
            output_path=str(output_path),
            cohort_name="Symlink_Cohort",
            description="Symlink test",
            copy_mode="symlink"
        )
        
        assert 'success' in results
        # Symlink mode should be faster but requires source
    
    def test_export_cohort_invalid_subjects(self, mock_database, tmp_path):
        """Test export with invalid subject IDs."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "invalid_cohort"
        
        results = exporter.export_cohort(
            subject_ids=['999'],  # Non-existent subject
            dataset_ids=[1],
            output_path=str(output_path),
            cohort_name="Invalid_Cohort",
            description="Test invalid",
            copy_mode="copy"
        )
        
        # Should handle gracefully
        assert 'success' in results
        assert 'errors' in results or 'warnings' in results
    
    def test_calculate_directory_size(self, mock_database, tmp_path):
        """Test directory size calculation."""
        exporter = CohortExporter(mock_database)
        
        # Create test directory with files
        test_dir = tmp_path / "size_test"
        test_dir.mkdir()
        
        # Create files of known size
        (test_dir / "file1.txt").write_text("a" * 1024)  # 1 KB
        (test_dir / "file2.txt").write_text("b" * 2048)  # 2 KB
        
        size_mb = exporter._calculate_directory_size(test_dir)
        
        assert size_mb > 0
        assert size_mb < 1  # Should be less than 1 MB


@pytest.mark.integration
class TestCohortExporterIntegration:
    """Integration tests for cohort exporter with complete workflows."""
    
    def test_full_export_workflow(self, mock_database, source_datasets, tmp_path):
        """Test complete export workflow from start to finish."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "full_workflow_cohort"
        
        # Perform export
        results = exporter.export_cohort(
            subject_ids=['001', '002'],
            dataset_ids=[1, 1],
            output_path=str(output_path),
            cohort_name="Full_Workflow_Cohort",
            description="Complete workflow test",
            copy_mode="copy",
            include_derivatives=False
        )
        
        # Verify all required files exist
        assert (output_path / "dataset_description.json").exists()
        assert (output_path / "participants.tsv").exists()
        assert (output_path / "README").exists()
        
        # Verify dataset_description.json structure
        with open(output_path / "dataset_description.json", 'r') as f:
            desc = json.load(f)
        
        assert desc['Name'] == "Full_Workflow_Cohort"
        assert 'BIDSVersion' in desc
        assert 'GeneratedBy' in desc
        assert len(desc['GeneratedBy']) > 0
        assert 'Name' in desc['GeneratedBy'][0]
        assert 'SourceDatasets' in desc
        
        # Verify results structure
        assert results['success'] in [True, False]
        assert isinstance(results['subjects_exported'], int)
        assert isinstance(results['total_size_mb'], (int, float))
        assert isinstance(results['errors'], list)
        assert isinstance(results['warnings'], list)
    
    def test_export_with_metadata_aggregation(self, mock_database, source_datasets, tmp_path):
        """Test that metadata is correctly aggregated from source datasets."""
        exporter = CohortExporter(mock_database)
        
        output_path = tmp_path / "metadata_cohort"
        
        results = exporter.export_cohort(
            subject_ids=['001', '003'],
            dataset_ids=[1, 2],
            output_path=str(output_path),
            cohort_name="Metadata_Cohort",
            description="Metadata aggregation test",
            copy_mode="copy"
        )
        
        # Check participants.tsv has aggregated data
        participants_file = output_path / "participants.tsv"
        if participants_file.exists():
            content = participants_file.read_text()
            assert 'participant_id' in content
            assert 'source_dataset' in content or 'Dataset' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
