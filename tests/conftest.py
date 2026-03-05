"""
Shared pytest fixtures and configuration for BIDSHub tests.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
import sys
import sqlite3
import os

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def test_db():
    """Create a temporary database for testing."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    
    # Create database
    db = Database(db_path)
    
    # Add test dataset (use actual database columns from init_db.py)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO datasets (name, platform, dataset_id_external, root_path, status)
        VALUES ('test_dataset', 'local', 'test_local', '/test/path', 'active')
    """)
    conn.commit()
    conn.close()
    
    yield db
    
    # Cleanup
    try:
        os.remove(db_path)
        os.rmdir(temp_dir)
    except:
        pass


@pytest.fixture
def sample_bids_structure(temp_dir):
    """
    Create a sample BIDS directory structure for testing.
    
    Structure:
        temp_dir/
        +── participants.tsv
        +── dataset_description.json
        +── sub-001/
            +── ses-2WK/
            |   +── anat/
            |       +── sub-001_ses-2WK_T1w.nii.gz
            |       +── sub-001_ses-2WK_T1w.json
            +── ses-6MO/
                +── anat/
                    +── sub-001_ses-6MO_T1w.nii.gz
                    +── sub-001_ses-6MO_T1w.json
    """
    # Create participants.tsv
    participants_data = """participant_id\tage\tsex\tdiagnosis
sub-001\t28\tM\tTBI
sub-002\t34\tF\tControl
"""
    (temp_dir / "participants.tsv").write_text(participants_data)
    
    # Create dataset_description.json
    dataset_desc = """{
    "Name": "Test Dataset",
    "BIDSVersion": "1.6.0",
    "Authors": ["Test Author"]
}"""
    (temp_dir / "dataset_description.json").write_text(dataset_desc)
    
    # Create subject directories
    for subject_id in ['001', '002']:
        for session in ['2WK', '6MO']:
            session_dir = temp_dir / f'sub-{subject_id}' / f'ses-{session}' / 'anat'
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Create scan file
            scan_file = session_dir / f'sub-{subject_id}_ses-{session}_T1w.nii.gz'
            scan_file.write_bytes(b'x' * 5 * 1024 * 1024)  # 5 MB
            
            # Create JSON sidecar
            json_file = session_dir / f'sub-{subject_id}_ses-{session}_T1w.json'
            json_file.write_text('{"EchoTime": 0.0025}')
    
    return temp_dir


@pytest.fixture
def sample_participants_tsv(temp_dir):
    """Create a sample participants.tsv file."""
    data = """participant_id\tage\tsex\tdiagnosis\tsite
sub-001\t28\tM\tmoderate-TBI\tUCSF
sub-002\t34\tF\tsevere-TBI\tYale
sub-003\t45\tM\tmild-TBI\tUCSF
"""
    
    participants_file = temp_dir / "participants.tsv"
    participants_file.write_text(data)
    
    return temp_dir


@pytest.fixture
def mock_pennsieve_env():
    """Mock environment variables for Pennsieve testing."""
    return {
        'PENNSIEVE_API_KEY': 'test_key_12345',
        'PENNSIEVE_API_SECRET': 'test_secret_67890'
    }


@pytest.fixture
def mock_openneuro_dataset_id():
    """Sample OpenNeuro dataset ID for testing."""
    return 'ds000246'


# Marker for slow tests
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (> 1s)"
    )
    config.addinivalue_line(
        "markers", "database: mark test as requiring database"
    )
    config.addinivalue_line(
        "markers", "api: mark test as interacting with external API"
    )
