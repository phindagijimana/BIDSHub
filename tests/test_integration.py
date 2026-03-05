"""
Integration tests for BIDSHub workflows.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.metadata_filter import MetadataFilter
from src.automated_qc import AutomatedQC


@pytest.fixture
def setup_test_environment(tmp_path):
    """Setup complete test environment."""
    # Create test BIDS structure
    bids_root = tmp_path / "bids"
    bids_root.mkdir()
    
    # Create participants.tsv
    participants_data = """participant_id\tage\tsex\tdiagnosis
sub-001\t28\tM\tTBI
sub-002\t34\tF\tControl
sub-003\t45\tM\tTBI
"""
    (bids_root / "participants.tsv").write_text(participants_data)
    
    # Create subject directories
    for subject_id in ['001', '002', '003']:
        for session in ['2WK', '6MO']:
            session_dir = bids_root / f'sub-{subject_id}' / f'ses-{session}' / 'anat'
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Create scan files
            for suffix in ['T1w', 'T2w']:
                file_path = session_dir / f'sub-{subject_id}_ses-{session}_{suffix}.nii.gz'
                file_path.write_bytes(b'x' * 5 * 1024 * 1024)  # 5 MB
                
                # JSON sidecar
                json_path = file_path.with_suffix('.json')
                json_path.write_text('{"EchoTime": 0.0025}')
    
    # Initialize database
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    
    return {
        'bids_root': str(bids_root),
        'database': db,
        'tmp_path': tmp_path
    }


class TestMetadataFilteringWorkflow:
    """Test complete metadata filtering workflow."""
    
    def test_filter_and_summary(self, setup_test_environment):
        """Test filtering subjects and getting summary."""
        env = setup_test_environment
        
        # Initialize filter (single dataset mode)
        mf = MetadataFilter(bids_root=env['bids_root'])
        
        # Filter by sex (returns list of strings in single-dataset mode)
        filtered = mf.filter_subjects({'sex': ['M']})
        assert len(filtered) == 2  # sub-001, sub-003
        
        # Get summary
        summary = mf.get_filter_summary({'sex': ['M']})
        assert summary['total_subjects'] == 2
        assert 'demographics' in summary
    
    def test_filter_export_workflow(self, setup_test_environment):
        """Test filtering and exporting."""
        env = setup_test_environment
        
        mf = MetadataFilter(bids_root=env['bids_root'])
        
        # Filter and export
        output_file = env['tmp_path'] / "filtered_export.csv"
        result = mf.export_filtered_list(
            {'diagnosis': ['TBI']},
            str(output_file)
        )
        
        assert result is True
        assert output_file.exists()


class TestAutomatedQCWorkflow:
    """Test complete automated QC workflow."""
    
    def test_qc_all_subjects(self, setup_test_environment):
        """Test running QC on all subjects."""
        env = setup_test_environment
        
        # Mock BIDS loader
        loader = Mock()
        
        def mock_get_scans(subject_id, session):
            bids_root = Path(env['bids_root'])
            session_dir = bids_root / f'sub-{subject_id}' / f'ses-{session}' / 'anat'
            
            scans = []
            for file in session_dir.glob('*.nii.gz'):
                suffix = file.stem.split('_')[-1]
                scans.append({
                    'file_path': str(file),
                    'suffix': suffix,
                    'size': file.stat().st_size
                })
            return scans
        
        loader.get_subject_scans = Mock(side_effect=mock_get_scans)
        loader.is_stub_file = Mock(return_value=False)
        
        # Initialize QC
        qc = AutomatedQC(loader, env['database'])
        
        # Create dataset and add subjects (v1.5+)
        dataset_id = env['database'].add_dataset("TestDataset", "pennsieve", root_path=env['bids_root'])
        
        for subject_id in ['001', '002', '003']:
            env['database'].add_subject(
                dataset_id=dataset_id,
                subject_id=f'sub-{subject_id}',
                local_subject_id=subject_id,
                has_2wk=True,
                has_6mo=True,
                scan_count_2wk=2,
                scan_count_6mo=2
            )
        
        # Run batch QC
        results = qc.run_batch_qc(['001', '002', '003'])
        
        assert len(results) == 3
        assert all(subject_id in results for subject_id in ['001', '002', '003'])
        
        # Check summary
        summary = qc.get_qc_summary()
        assert summary['total'] == 3


class TestDatabaseOperations:
    """Test database operations."""
    
    def test_add_and_retrieve_subjects(self, setup_test_environment):
        """Test adding and retrieving subjects (v1.5+ multi-dataset)."""
        db = setup_test_environment['database']
        
        # Create dataset first (v1.5+)
        dataset_id = db.add_dataset("TestDataset", "pennsieve", root_path=setup_test_environment['bids_root'])
        
        # Add subjects with dataset_id
        db.add_subject(dataset_id, 'sub-001', '001', has_2wk=True, has_6mo=True)
        db.add_subject(dataset_id, 'sub-002', '002', has_2wk=True, has_6mo=False)
        
        # Retrieve
        all_subjects = db.get_subjects_by_dataset(dataset_id)
        assert len(all_subjects) == 2
        
        subject_001 = db.get_subject('001', dataset_id)
        assert subject_001['local_subject_id'] == '001'
        assert subject_001['has_2wk'] == 1  # SQLite returns int for boolean
        assert subject_001['has_6mo'] == 1
    
    def test_update_automated_qc(self, setup_test_environment):
        """Test updating automated QC status (v1.5+ multi-dataset)."""
        db = setup_test_environment['database']
        
        # Create dataset and add subject (v1.5+)
        dataset_id = db.add_dataset("TestDataset", "pennsieve", root_path=setup_test_environment['bids_root'])
        db.add_subject(dataset_id, 'sub-001', '001', has_2wk=True, has_6mo=True)
        
        # Update QC (uses subject_id which is 'sub-001')
        results_json = json.dumps({'status': 'pass', 'issues': []})
        success = db.update_automated_qc('sub-001', 'pass', results_json)
        
        assert success is True
        
        # Verify update
        subject = db.get_subject('001', dataset_id)
        assert subject['automated_qc_status'] == 'pass'


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    def test_filter_qc_download_workflow(self, setup_test_environment):
        """Test complete workflow: filter -> QC -> download."""
        env = setup_test_environment
        
        # Step 1: Initialize database with subjects (v1.5+)
        db = env['database']
        dataset_id = db.add_dataset("TestDataset", "pennsieve", root_path=env['bids_root'])
        
        for subject_id in ['001', '002', '003']:
            db.add_subject(dataset_id, f'sub-{subject_id}', subject_id, has_2wk=True, has_6mo=True)
        
        # Step 2: Filter subjects by metadata (single dataset mode)
        mf = MetadataFilter(bids_root=env['bids_root'])
        filtered = mf.filter_subjects({'sex': ['M']})
        assert len(filtered) == 2
        
        # Step 3: Run automated QC on filtered subjects
        loader = Mock()
        loader.get_subject_scans = Mock(return_value=[])
        loader.is_stub_file = Mock(return_value=False)
        
        qc = AutomatedQC(loader, db)
        qc_results = qc.run_batch_qc(filtered)
        
        assert len(qc_results) == 2
        
        # Step 4: Verify database has QC results
        for subject_id in filtered:
            subject = db.get_subject(subject_id)
            assert 'automated_qc_status' in subject


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
