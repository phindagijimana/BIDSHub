"""
Tests for Database Integrity Features (v3.1.1+)

Tests duplicate prevention, orphaned record cleanup, and integrity checks.
"""

import pytest
import sys
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database


class TestDuplicatePrevention:
    """Test duplicate subject/session prevention."""
    
    def test_add_subject_updates_existing(self, test_db):
        """Test that re-adding subject updates instead of duplicating."""
        db = test_db
        
        # Add subject first time
        db.add_subject(
            subject_id='sub-001',
            dataset_id=1,
            local_subject_id='sub-001'
        )
        
        # Get initial record
        subjects = db.get_all_subjects()
        initial_count = len(subjects)
        
        # Re-add same subject
        db.add_subject(
            subject_id='sub-001',
            dataset_id=1,
            local_subject_id='sub-001'
        )
        
        # Count should remain same
        subjects = db.get_all_subjects()
        assert len(subjects) == initial_count, "Should not create duplicate"
    
    def test_add_session_updates_existing(self, test_db):
        """Test session update instead of duplicate."""
        db = test_db
        
        db.add_subject('sub-001', 1, 'sub-001')
        
        # Add session
        db.add_subject_session('sub-001', 1, 'ses-01', scan_count=5)
        
        # Re-add with different scan count
        db.add_subject_session('sub-001', 1, 'ses-01', scan_count=8)
        
        sessions = db.get_subject_sessions('sub-001', 1)
        ses_01 = [s for s in sessions if s['session_id'] == 'ses-01']
        
        assert len(ses_01) == 1, "Should not duplicate session"
        assert ses_01[0]['scan_count'] == 8, "Should update scan count"


class TestIntegrityChecks:
    """Test database integrity checking."""
    
    def test_check_integrity_empty_db(self, test_db):
        """Test integrity check on empty database."""
        issues = test_db.check_integrity()
        
        assert isinstance(issues, dict)
        assert all(count == 0 for count in issues.values())
    
    def test_check_integrity_valid_data(self, test_db):
        """Test integrity check with valid data."""
        db = test_db
        
        # Add valid data structure
        db.add_subject('sub-001', 1, 'sub-001')
        db.add_subject_session('sub-001', 1, 'ses-01', scan_count=2)
        
        issues = db.check_integrity()
        
        # Should have no issues
        assert issues.get('orphaned_subjects', 0) == 0
        assert issues.get('orphaned_sessions', 0) == 0
    
    def test_detect_orphaned_sessions(self, test_db):
        """Test detection of orphaned sessions."""
        db = test_db
        
        # Add subject and session
        db.add_subject('sub-001', 1, 'sub-001')
        db.add_subject_session('sub-001', 1, 'ses-01', scan_count=2)
        
        # Manually delete subject to create orphan
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.execute("DELETE FROM subjects WHERE subject_id = 'sub-001'")
        conn.commit()
        conn.close()
        
        # Check integrity
        issues = db.check_integrity()
        
        assert issues.get('orphaned_sessions', 0) > 0, "Should detect orphaned session"
    
    def test_detect_duplicate_subjects(self, test_db):
        """Test detection of duplicate subjects."""
        db = test_db
        
        # Manually create duplicates (bypassing add_subject)
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        
        # Insert same subject twice
        for _ in range(2):
            conn.execute("""
                INSERT INTO subjects (subject_id, dataset_id, local_subject_id)
                VALUES ('sub-001', 1, 'sub-001')
            """)
        conn.commit()
        conn.close()
        
        issues = db.check_integrity()
        
        assert issues.get('duplicate_subjects', 0) > 0, "Should detect duplicates"


class TestOrphanedRecordCleanup:
    """Test cleanup of orphaned records."""
    
    def test_cleanup_orphaned_sessions_dry_run(self, test_db):
        """Test dry-run mode for session cleanup."""
        db = test_db
        
        # Create orphaned session scenario
        db.add_subject('sub-001', 1, 'sub-001')
        db.add_subject_session('sub-001', 1, 'ses-01', scan_count=2)
        
        # Delete subject to orphan session
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.execute("DELETE FROM subjects WHERE subject_id = 'sub-001'")
        conn.commit()
        conn.close()
        
        # Dry run cleanup
        result = db.cleanup_orphaned_records(dry_run=True)
        
        assert result.get('would_delete_sessions', 0) > 0, "Should report orphaned sessions"
        
        # Verify nothing was actually deleted
        issues = db.check_integrity()
        assert issues.get('orphaned_sessions', 0) > 0, "Sessions should still exist in dry-run"
    
    def test_cleanup_orphaned_sessions_actual(self, test_db):
        """Test actual cleanup of orphaned sessions."""
        db = test_db
        
        # Create orphaned session
        db.add_subject('sub-001', 1, 'sub-001')
        db.add_subject_session('sub-001', 1, 'ses-01', scan_count=2)
        
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.execute("DELETE FROM subjects WHERE subject_id = 'sub-001'")
        conn.commit()
        conn.close()
        
        # Actual cleanup
        result = db.cleanup_orphaned_records(dry_run=False)
        
        assert result.get('deleted_sessions', 0) > 0, "Should delete orphaned sessions"
        
        # Verify cleanup worked
        issues = db.check_integrity()
        assert issues.get('orphaned_sessions', 0) == 0, "Orphaned sessions should be removed"


class TestDownloadStateConsistency:
    """Test download state verification and fixes."""
    
    def test_fix_download_states_dry_run(self, test_db):
        """Test dry-run mode for download state fixes."""
        db = test_db
        
        # Add subject and scan
        db.add_subject('sub-001', 1, 'sub-001')
        db.add_subject_session('sub-001', 1, 'ses-01', scan_count=1)
        
        # Add scan marked as downloaded but file doesn't exist
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.execute("""
            INSERT INTO scans (subject_id, dataset_id, session, modality, suffix, 
                              file_path, is_downloaded)
            VALUES ('sub-001', 1, 'ses-01', 'anat', 'T1w', '/nonexistent/file.nii.gz', 1)
        """)
        conn.commit()
        conn.close()
        
        # Dry run fix
        result = db.fix_download_states(dry_run=True)
        
        assert result.get('would_fix', 0) > 0, "Should detect inconsistent state"
    
    def test_fix_download_states_actual(self, test_db):
        """Test actual fix of download states."""
        db = test_db
        
        db.add_subject('sub-001', 1, 'sub-001')
        
        # Add scan with bad state
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.execute("""
            INSERT INTO scans (subject_id, dataset_id, session, modality, suffix,
                              file_path, is_downloaded)
            VALUES ('sub-001', 1, 'ses-01', 'anat', 'T1w', '/nonexistent/file.nii.gz', 1)
        """)
        conn.commit()
        conn.close()
        
        # Fix states
        result = db.fix_download_states(dry_run=False)
        
        assert result.get('fixed', 0) > 0, "Should fix state"
        
        # Verify scan is now marked as not downloaded
        scans = db.get_subject_scans('sub-001')
        assert all(scan['is_downloaded'] == 0 for scan in scans), "Should reset download flag"


class TestQCConsistency:
    """Test QC data consistency checks."""
    
    def test_update_scan_qc_validation(self, test_db):
        """Test QC update validation."""
        db = test_db
        
        # Invalid QC status should fail
        result = db.update_scan_qc(
            scan_id=999,
            qc_status='invalid_status',
            notes='Test'
        )
        
        assert result is False, "Invalid QC status should be rejected"
    
    def test_qc_notes_required_for_fail(self, test_db):
        """Test that notes are required for fail status."""
        db = test_db
        
        db.add_subject('sub-001', 1, 'sub-001')
        
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scans (subject_id, dataset_id, session, modality, suffix, file_path)
            VALUES ('sub-001', 1, 'ses-01', 'anat', 'T1w', '/path/file.nii.gz')
        """)
        scan_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Try to mark as fail without notes
        result = db.update_scan_qc(scan_id, 'fail', notes=None)
        
        assert result is False, "Fail status should require notes"
        
        # With notes should work
        result = db.update_scan_qc(scan_id, 'fail', notes='Poor quality')
        assert result is True, "Should succeed with notes"
    
    def test_verify_qc_consistency(self, test_db):
        """Test QC consistency verification."""
        db = test_db
        
        db.add_subject('sub-001', 1, 'sub-001')
        
        # Add scan with QC
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scans (subject_id, dataset_id, session, modality, suffix,
                              file_path, qc_status, qc_notes)
            VALUES ('sub-001', 1, 'ses-01', 'anat', 'T1w', '/path/file.nii.gz', 'fail', NULL)
        """)
        conn.commit()
        conn.close()
        
        # Check consistency
        issues = db.verify_qc_consistency()
        
        # Should detect QC record without notes for fail status
        assert issues.get('qc_without_notes', 0) > 0, "Should detect missing notes"


class TestMaintenanceWorkflow:
    """Test full maintenance workflow."""
    
    def test_run_integrity_maintenance(self, test_db):
        """Test complete maintenance operation."""
        db = test_db
        
        # Create some test data with issues
        db.add_subject('sub-001', 1, 'sub-001')
        db.add_subject('sub-002', 1, 'sub-002')
        
        # Run maintenance
        result = db.run_integrity_maintenance(dry_run=True)
        
        assert 'integrity_check' in result
        assert 'cleanup_result' in result
        assert 'fix_states_result' in result
        assert 'qc_check' in result
    
    def test_maintenance_with_actual_fixes(self, test_db):
        """Test maintenance with actual fixes applied."""
        db = test_db
        
        # Add data
        db.add_subject('sub-001', 1, 'sub-001')
        
        # Run actual maintenance
        result = db.run_integrity_maintenance(dry_run=False)
        
        # Should complete without errors
        assert result is not None
        
        # Check integrity after maintenance
        issues = db.check_integrity()
        # Most issues should be resolved
        assert sum(issues.values()) == 0, "Maintenance should resolve most issues"


class TestRemoveDuplicateSubjects:
    """Test duplicate subject removal."""
    
    def test_remove_duplicate_subjects_dry_run(self, test_db):
        """Test dry-run duplicate removal."""
        db = test_db
        
        # Manually create duplicates
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        for _ in range(2):
            conn.execute("""
                INSERT INTO subjects (subject_id, dataset_id, local_subject_id, last_updated)
                VALUES ('sub-001', 1, 'sub-001', datetime('now'))
            """)
        conn.commit()
        conn.close()
        
        # Dry run
        result = db.remove_duplicate_subjects(dry_run=True)
        
        assert result.get('would_remove', 0) > 0, "Should detect duplicates"
        
        # Verify nothing removed
        subjects = db.get_all_subjects()
        duplicates = [s for s in subjects if s['subject_id'] == 'sub-001']
        assert len(duplicates) == 2, "Dry-run should not remove"
    
    def test_remove_duplicate_subjects_actual(self, test_db):
        """Test actual duplicate removal."""
        db = test_db
        
        # Create duplicates
        import sqlite3
        import time
        conn = sqlite3.connect(db.db_path)
        
        # First duplicate (older)
        conn.execute("""
            INSERT INTO subjects (subject_id, dataset_id, local_subject_id, last_updated)
            VALUES ('sub-001', 1, 'sub-001', datetime('2023-01-01'))
        """)
        
        # Second duplicate (newer - should be kept)
        conn.execute("""
            INSERT INTO subjects (subject_id, dataset_id, local_subject_id, last_updated)
            VALUES ('sub-001', 1, 'sub-001', datetime('2024-01-01'))
        """)
        conn.commit()
        conn.close()
        
        # Remove duplicates
        result = db.remove_duplicate_subjects(dry_run=False)
        
        assert result.get('removed', 0) > 0, "Should remove older duplicate"
        
        # Verify only one remains
        subjects = db.get_all_subjects()
        matching = [s for s in subjects if s['subject_id'] == 'sub-001']
        assert len(matching) == 1, "Should have only one subject"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
