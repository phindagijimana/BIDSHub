"""
Unit tests for Automated QC.
"""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.automated_qc import AutomatedQC


@pytest.fixture
def mock_bids_loader():
    """Create mock BIDS loader."""
    loader = Mock()
    
    # Mock get_subject_scans to return sample scans
    def mock_get_scans(subject_id, session):
        return [
            {
                'file_path': f'/data/sub-{subject_id}/ses-{session}/anat/sub-{subject_id}_T1w.nii.gz',
                'suffix': 'T1w',
                'size': 10 * 1024 * 1024  # 10 MB
            },
            {
                'file_path': f'/data/sub-{subject_id}/ses-{session}/anat/sub-{subject_id}_T2w.nii.gz',
                'suffix': 'T2w',
                'size': 10 * 1024 * 1024
            }
        ]
    
    loader.get_subject_scans = Mock(side_effect=mock_get_scans)
    loader.is_stub_file = Mock(return_value=False)
    
    return loader


@pytest.fixture
def mock_database():
    """Create mock database."""
    db = Mock()
    
    db.get_subject = Mock(return_value={
        'subject_id': '001',
        'has_2wk': True,
        'has_6mo': True
    })
    
    db.get_all_subjects = Mock(return_value=[
        {'subject_id': '001', 'has_2wk': True, 'has_6mo': True},
        {'subject_id': '002', 'has_2wk': True, 'has_6mo': False}
    ])
    
    db.update_automated_qc = Mock(return_value=True)
    
    return db


class TestAutomatedQC:
    
    def test_init(self, mock_bids_loader, mock_database):
        """Test AutomatedQC initialization."""
        qc = AutomatedQC(mock_bids_loader, mock_database)
        
        assert qc.bids_loader is mock_bids_loader
        assert qc.db is mock_database
        assert len(qc.expected_modalities) > 0
    
    def test_run_subject_qc_pass(self, mock_bids_loader, mock_database, tmp_path):
        """Test successful QC run with no issues."""
        qc = AutomatedQC(mock_bids_loader, mock_database)
        
        # Create actual files
        for session in ['2WK', '6MO']:
            for suffix in ['T1w', 'T2w']:
                file_path = tmp_path / f'sub-001' / f'ses-{session}' / 'anat' / f'sub-001_{suffix}.nii.gz'
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(b'x' * 10 * 1024 * 1024)  # 10 MB
                
                # Create JSON sidecar
                json_path = file_path.with_suffix('.json')
                json_path.write_text('{}')
        
        # Update mock to use real paths
        def mock_get_scans(subject_id, session):
            return [
                {
                    'file_path': str(tmp_path / f'sub-{subject_id}' / f'ses-{session}' / 'anat' / f'sub-{subject_id}_T1w.nii.gz'),
                    'suffix': 'T1w',
                    'size': 10 * 1024 * 1024
                },
                {
                    'file_path': str(tmp_path / f'sub-{subject_id}' / f'ses-{session}' / 'anat' / f'sub-{subject_id}_T2w.nii.gz'),
                    'suffix': 'T2w',
                    'size': 10 * 1024 * 1024
                }
            ]
        
        mock_bids_loader.get_subject_scans = Mock(side_effect=mock_get_scans)
        
        results = qc.run_subject_qc('001')
        
        assert results['status'] in ['pass', 'warning']  # May have warnings for missing modalities
        assert 'sessions' in results
        assert '2WK' in results['sessions']
        assert '6MO' in results['sessions']
    
    def test_run_subject_qc_with_stubs(self, mock_bids_loader, mock_database, tmp_path):
        """Test QC detects stub files."""
        qc = AutomatedQC(mock_bids_loader, mock_database)
        
        # Create stub file (0 bytes)
        stub_file = tmp_path / 'sub-001' / 'ses-2WK' / 'anat' / 'sub-001_T1w.nii.gz'
        stub_file.parent.mkdir(parents=True, exist_ok=True)
        stub_file.touch()
        
        mock_bids_loader.get_subject_scans = Mock(return_value=[
            {'file_path': str(stub_file), 'suffix': 'T1w', 'size': 0}
        ])
        mock_bids_loader.is_stub_file = Mock(return_value=True)
        
        results = qc.run_subject_qc('001')
        
        assert results['status'] in ['warning', 'fail']
        assert any('stub' in str(w).lower() for w in results.get('warnings', []))
    
    def test_run_subject_qc_missing_files(self, mock_bids_loader, mock_database, tmp_path):
        """Test QC detects missing files."""
        qc = AutomatedQC(mock_bids_loader, mock_database)
        
        # Point to non-existent file
        mock_bids_loader.get_subject_scans = Mock(return_value=[
            {'file_path': str(tmp_path / 'nonexistent.nii.gz'), 'suffix': 'T1w', 'size': 0}
        ])
        
        results = qc.run_subject_qc('001')
        
        assert results['status'] == 'fail'
        assert len(results['issues']) > 0
        assert any('not found' in str(issue).lower() for issue in results['issues'])
    
    def test_run_batch_qc(self, mock_bids_loader, mock_database):
        """Test batch QC processing."""
        qc = AutomatedQC(mock_bids_loader, mock_database)
        
        results = qc.run_batch_qc(['001', '002'])
        
        assert '001' in results
        assert '002' in results
        assert mock_database.update_automated_qc.call_count == 2
    
    def test_get_qc_summary(self, mock_bids_loader, mock_database):
        """Test QC summary statistics."""
        mock_database.get_all_subjects = Mock(return_value=[
            {'subject_id': '001', 'automated_qc_status': 'pass'},
            {'subject_id': '002', 'automated_qc_status': 'warning'},
            {'subject_id': '003', 'automated_qc_status': 'fail'},
            {'subject_id': '004', 'automated_qc_status': 'pending'}
        ])
        
        qc = AutomatedQC(mock_bids_loader, mock_database)
        summary = qc.get_qc_summary()
        
        assert summary['total'] == 4
        assert summary['pass'] == 1
        assert summary['warning'] == 1
        assert summary['fail'] == 1
        assert summary['pending'] == 1
        assert summary['pass_pct'] == 25.0
    
    def test_get_subjects_by_status(self, mock_bids_loader, mock_database):
        """Test filtering subjects by QC status."""
        mock_database.get_all_subjects = Mock(return_value=[
            {'subject_id': '001', 'automated_qc_status': 'pass'},
            {'subject_id': '002', 'automated_qc_status': 'pass'},
            {'subject_id': '003', 'automated_qc_status': 'fail'}
        ])
        
        qc = AutomatedQC(mock_bids_loader, mock_database)
        pass_subjects = qc.get_subjects_by_status('pass')
        
        assert len(pass_subjects) == 2
        assert pass_subjects[0]['subject_id'] == '001'
    
    def test_get_flagged_subjects(self, mock_bids_loader, mock_database):
        """Test getting subjects with issues."""
        mock_database.get_all_subjects = Mock(return_value=[
            {'subject_id': '001', 'automated_qc_status': 'pass'},
            {'subject_id': '002', 'automated_qc_status': 'warning'},
            {'subject_id': '003', 'automated_qc_status': 'fail'}
        ])
        
        qc = AutomatedQC(mock_bids_loader, mock_database)
        flagged = qc.get_flagged_subjects()
        
        assert len(flagged) == 2  # warning + fail
        assert any(s['subject_id'] == '002' for s in flagged)
        assert any(s['subject_id'] == '003' for s in flagged)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
