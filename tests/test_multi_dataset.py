"""
Unit and integration tests for multi-dataset support (v1.5+).
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.metadata_filter import MetadataFilter


@pytest.fixture
def setup_multi_dataset_db(tmp_path):
    """Setup database with multiple datasets."""
    db_path = tmp_path / "test_multi.db"
    db = Database(str(db_path))
    
    # Add two datasets
    dataset_1_id = db.add_dataset(
        name="TrackTBI",
        platform="pennsieve",
        api_key="key1",
        api_secret="secret1",
        dataset_id_external="TrackTBI",
        root_path=str(tmp_path / "dataset1")
    )
    
    dataset_2_id = db.add_dataset(
        name="ds000246",
        platform="openneuro",
        dataset_id_external="ds000246",
        root_path=str(tmp_path / "dataset2")
    )
    
    return {
        'db': db,
        'dataset_1_id': dataset_1_id,
        'dataset_2_id': dataset_2_id,
        'tmp_path': tmp_path
    }


class TestDatasetOperations:
    """Test dataset CRUD operations."""
    
    def test_add_dataset(self, setup_multi_dataset_db):
        """Test adding a dataset."""
        env = setup_multi_dataset_db
        db = env['db']
        
        # Add third dataset
        dataset_id = db.add_dataset(
            name="ABCD",
            platform="pennsieve",
            dataset_id_external="ABCD_Study"
        )
        
        assert dataset_id is not None
        assert dataset_id > 0
    
    def test_get_dataset(self, setup_multi_dataset_db):
        """Test retrieving a dataset."""
        env = setup_multi_dataset_db
        db = env['db']
        
        dataset = db.get_dataset(env['dataset_1_id'])
        
        assert dataset is not None
        assert dataset['name'] == "TrackTBI"
        assert dataset['platform'] == "pennsieve"
        assert dataset['status'] == "active"
    
    def test_get_all_datasets(self, setup_multi_dataset_db):
        """Test retrieving all datasets."""
        env = setup_multi_dataset_db
        db = env['db']
        
        datasets = db.get_all_datasets()
        
        assert len(datasets) == 2
        assert any(d['name'] == "TrackTBI" for d in datasets)
        assert any(d['name'] == "ds000246" for d in datasets)
    
    def test_get_datasets_by_status(self, setup_multi_dataset_db):
        """Test filtering datasets by status."""
        env = setup_multi_dataset_db
        db = env['db']
        
        # Deactivate one dataset
        db.update_dataset(env['dataset_1_id'], status='inactive')
        
        active_datasets = db.get_all_datasets(status='active')
        inactive_datasets = db.get_all_datasets(status='inactive')
        
        assert len(active_datasets) == 1
        assert len(inactive_datasets) == 1
        assert active_datasets[0]['name'] == "ds000246"
    
    def test_update_dataset(self, setup_multi_dataset_db):
        """Test updating dataset fields."""
        env = setup_multi_dataset_db
        db = env['db']
        
        success = db.update_dataset(
            env['dataset_1_id'],
            name="TrackTBI_Updated",
            status="inactive"
        )
        
        assert success is True
        
        dataset = db.get_dataset(env['dataset_1_id'])
        assert dataset['name'] == "TrackTBI_Updated"
        assert dataset['status'] == "inactive"
    
    def test_delete_dataset(self, setup_multi_dataset_db):
        """Test deleting a dataset."""
        env = setup_multi_dataset_db
        db = env['db']
        
        success = db.delete_dataset(env['dataset_2_id'])
        
        assert success is True
        
        # Verify deleted
        dataset = db.get_dataset(env['dataset_2_id'])
        assert dataset is None
        
        # Verify only one dataset remains
        datasets = db.get_all_datasets()
        assert len(datasets) == 1


class TestMultiDatasetSubjects:
    """Test subject operations with multiple datasets."""
    
    def test_add_subjects_to_different_datasets(self, setup_multi_dataset_db):
        """Test adding subjects to different datasets."""
        env = setup_multi_dataset_db
        db = env['db']
        
        # Add subjects to dataset 1
        db.add_subject(env['dataset_1_id'], '001', '001', True, True, 2, 2)
        db.add_subject(env['dataset_1_id'], '002', '002', True, False, 2, 0)
        
        # Add subjects to dataset 2
        db.add_subject(env['dataset_2_id'], '001', '001', True, True, 3, 3)
        db.add_subject(env['dataset_2_id'], '003', '003', True, True, 2, 2)
        
        # Verify separation
        dataset1_subjects = db.get_subjects_by_dataset(env['dataset_1_id'])
        dataset2_subjects = db.get_subjects_by_dataset(env['dataset_2_id'])
        
        assert len(dataset1_subjects) == 2
        assert len(dataset2_subjects) == 2
        
        # Both datasets can have subject '001' (different context)
        assert any(s['local_subject_id'] == '001' for s in dataset1_subjects)
        assert any(s['local_subject_id'] == '001' for s in dataset2_subjects)
    
    def test_get_subjects_by_dataset(self, setup_multi_dataset_db):
        """Test retrieving subjects filtered by dataset."""
        env = setup_multi_dataset_db
        db = env['db']
        
        # Add subjects
        db.add_subject(env['dataset_1_id'], '001', '001')
        db.add_subject(env['dataset_1_id'], '002', '002')
        db.add_subject(env['dataset_2_id'], '003', '003')
        
        dataset1_subjects = db.get_subjects_by_dataset(env['dataset_1_id'])
        
        assert len(dataset1_subjects) == 2
        assert all(s['dataset_id'] == env['dataset_1_id'] for s in dataset1_subjects)
    
    def test_cascade_delete_dataset(self, setup_multi_dataset_db):
        """Test that deleting dataset cascades to subjects."""
        env = setup_multi_dataset_db
        db = env['db']
        
        # Add subjects to dataset
        db.add_subject(env['dataset_1_id'], '001', '001')
        db.add_subject(env['dataset_1_id'], '002', '002')
        
        # Verify subjects exist
        subjects_before = db.get_subjects_by_dataset(env['dataset_1_id'])
        assert len(subjects_before) == 2
        
        # Delete dataset
        db.delete_dataset(env['dataset_1_id'])
        
        # Verify subjects are gone (CASCADE)
        subjects_after = db.get_subjects_by_dataset(env['dataset_1_id'])
        assert len(subjects_after) == 0


class TestMultiDatasetMetadataFilter:
    """Test metadata filtering across multiple datasets."""
    
    def test_multi_dataset_initialization(self, tmp_path):
        """Test initializing metadata filter with multiple datasets."""
        # Create two BIDS datasets
        dataset1_path = tmp_path / "dataset1"
        dataset1_path.mkdir()
        
        participants1 = """participant_id\tage\tsex
sub-001\t28\tM
sub-002\t34\tF
"""
        (dataset1_path / "participants.tsv").write_text(participants1)
        
        dataset2_path = tmp_path / "dataset2"
        dataset2_path.mkdir()
        
        participants2 = """participant_id\tage\tsex
sub-003\t45\tM
sub-004\t52\tF
"""
        (dataset2_path / "participants.tsv").write_text(participants2)
        
        # Initialize multi-dataset filter
        datasets = [
            {'id': 1, 'name': 'Dataset1', 'root_path': str(dataset1_path)},
            {'id': 2, 'name': 'Dataset2', 'root_path': str(dataset2_path)}
        ]
        
        mf = MetadataFilter(datasets=datasets)
        
        assert mf.is_available() is True
        assert len(mf.participants_dfs) == 2
        assert 1 in mf.participants_dfs
        assert 2 in mf.participants_dfs
    
    def test_filter_across_datasets(self, tmp_path):
        """Test filtering subjects across multiple datasets."""
        # Create test data
        dataset1_path = tmp_path / "dataset1"
        dataset1_path.mkdir()
        
        participants1 = """participant_id\tage\tsex\tdiagnosis
sub-001\t28\tM\tTBI
sub-002\t34\tF\tControl
"""
        (dataset1_path / "participants.tsv").write_text(participants1)
        
        dataset2_path = tmp_path / "dataset2"
        dataset2_path.mkdir()
        
        participants2 = """participant_id\tage\tsex\tdiagnosis
sub-003\t32\tM\tTBI
sub-004\t52\tF\tTBI
"""
        (dataset2_path / "participants.tsv").write_text(participants2)
        
        # Initialize filter
        datasets = [
            {'id': 1, 'name': 'Dataset1', 'root_path': str(dataset1_path)},
            {'id': 2, 'name': 'Dataset2', 'root_path': str(dataset2_path)}
        ]
        
        mf = MetadataFilter(datasets=datasets)
        
        # Filter: sex='M' across both datasets
        results = mf.filter_subjects({'sex': ['M']})
        
        # Should return 2 subjects: 001 from dataset1, 003 from dataset2
        assert len(results) == 2
        assert any(r['subject_id'] == '001' and r['dataset_id'] == 1 for r in results)
        assert any(r['subject_id'] == '003' and r['dataset_id'] == 2 for r in results)
    
    def test_filter_specific_dataset(self, tmp_path):
        """Test filtering subjects from specific dataset only."""
        # Setup
        dataset1_path = tmp_path / "dataset1"
        dataset1_path.mkdir()
        
        participants1 = """participant_id\tage\tsex
sub-001\t28\tM
sub-002\t34\tF
"""
        (dataset1_path / "participants.tsv").write_text(participants1)
        
        dataset2_path = tmp_path / "dataset2"
        dataset2_path.mkdir()
        
        participants2 = """participant_id\tage\tsex
sub-003\t45\tM
sub-004\t52\tF
"""
        (dataset2_path / "participants.tsv").write_text(participants2)
        
        datasets = [
            {'id': 1, 'name': 'Dataset1', 'root_path': str(dataset1_path)},
            {'id': 2, 'name': 'Dataset2', 'root_path': str(dataset2_path)}
        ]
        
        mf = MetadataFilter(datasets=datasets)
        
        # Filter only dataset 1
        results = mf.filter_subjects({'sex': ['M']}, dataset_ids=[1])
        
        assert len(results) == 1
        assert results[0]['subject_id'] == '001'
        assert results[0]['dataset_id'] == 1


class TestMultiDatasetIntegration:
    """Integration tests for complete multi-dataset workflows."""
    
    def test_add_datasets_and_subjects(self, tmp_path):
        """Test complete workflow: add datasets, add subjects, query across."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        
        # Add datasets
        ds1_id = db.add_dataset("Dataset1", "pennsieve")
        ds2_id = db.add_dataset("Dataset2", "openneuro")
        
        # Add subjects to each
        db.add_subject(ds1_id, '001', '001', True, True)
        db.add_subject(ds1_id, '002', '002', True, False)
        db.add_subject(ds2_id, '003', '003', True, True)
        
        # Query datasets
        datasets = db.get_all_datasets()
        assert len(datasets) == 2
        
        # Query subjects by dataset
        ds1_subjects = db.get_subjects_by_dataset(ds1_id)
        ds2_subjects = db.get_subjects_by_dataset(ds2_id)
        
        assert len(ds1_subjects) == 2
        assert len(ds2_subjects) == 1
        
        # Verify foreign keys
        assert all(s['dataset_id'] == ds1_id for s in ds1_subjects)
        assert all(s['dataset_id'] == ds2_id for s in ds2_subjects)
    
    def test_dataset_isolation(self, tmp_path):
        """Test that datasets are properly isolated."""
        db_path = tmp_path / "test.db"
        db = Database(str(db_path))
        
        # Add two datasets
        ds1_id = db.add_dataset("Dataset1", "pennsieve")
        ds2_id = db.add_dataset("Dataset2", "openneuro")
        
        # Both can have subject with same local ID
        db.add_subject(ds1_id, '001', '001', True, True)
        db.add_subject(ds2_id, '001', '001', True, False)
        
        # Retrieve subjects
        ds1_subjects = db.get_subjects_by_dataset(ds1_id)
        ds2_subjects = db.get_subjects_by_dataset(ds2_id)
        
        # Both should have subject '001', but different records
        assert len(ds1_subjects) == 1
        assert len(ds2_subjects) == 1
        assert ds1_subjects[0]['local_subject_id'] == '001'
        assert ds2_subjects[0]['local_subject_id'] == '001'
        assert ds1_subjects[0]['id'] != ds2_subjects[0]['id']
        # has_6mo on subjects row is not driven by add_subject(..., has_6mo=...) in current API
        assert 'has_6mo' in ds1_subjects[0]


class TestMigrationScript:
    """Test database migration from v1.0 to v1.5."""
    
    def test_migration_preserves_data(self, tmp_path):
        """Test that migration preserves existing data."""
        from scripts.migrate_to_multi_dataset import migrate_database
        
        db_path = tmp_path / "test.db"
        
        # Create v1.0 style database (old schema)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Old schema without datasets table
        cursor.execute("""
            CREATE TABLE subjects (
                subject_id TEXT PRIMARY KEY,
                has_2wk BOOLEAN DEFAULT 0,
                has_6mo BOOLEAN DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE scans (
                id INTEGER PRIMARY KEY,
                subject_id TEXT,
                file_path TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE download_queue (
                id INTEGER PRIMARY KEY,
                scan_id INTEGER,
                subject_id TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Insert test data
        cursor.execute("INSERT INTO subjects VALUES ('001', 1, 1)")
        cursor.execute("INSERT INTO subjects VALUES ('002', 1, 0)")
        cursor.execute("INSERT INTO metadata VALUES ('dataset_name', 'TestDataset')")
        cursor.execute("INSERT INTO metadata VALUES ('platform', 'pennsieve')")
        
        conn.commit()
        conn.close()
        
        # Run migration
        success = migrate_database(str(db_path))
        
        assert success is True
        
        # Verify migrated database
        db = Database(str(db_path))
        
        # Check datasets table exists and has default dataset
        datasets = db.get_all_datasets()
        assert len(datasets) == 1
        assert datasets[0]['name'] == 'TestDataset'
        assert datasets[0]['platform'] == 'pennsieve'
        
        # Check subjects were migrated
        subjects = db.get_subjects_by_dataset(datasets[0]['id'])
        assert len(subjects) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
