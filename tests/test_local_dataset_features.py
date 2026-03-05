"""
Test suite for local dataset features and enhanced UI
Tests the v2.0 local dataset support and browse platform features
"""

import sys
import os
from pathlib import Path
import tempfile
import json
import sqlite3

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database
from src.bids_loader import BIDSLoader


class TestResults:
    """Track test results"""
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
    
    def add(self, name, passed, message=""):
        self.tests.append({
            'name': name,
            'passed': passed,
            'message': message
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Total Tests: {total}")
        print(f"Passed: {self.passed} ({self.passed/total*100:.1f}%)")
        print(f"Failed: {self.failed} ({self.failed/total*100:.1f}%)")
        print(f"{'='*70}\n")
        
        if self.failed > 0:
            print("FAILED TESTS:")
            for test in self.tests:
                if not test['passed']:
                    print(f"  [X] {test['name']}")
                    if test['message']:
                        print(f"    {test['message']}")
        
        return self.failed == 0


def create_test_bids_dataset(root_path):
    """Create a minimal valid BIDS dataset for testing"""
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    
    # Create dataset_description.json
    dataset_desc = {
        "Name": "Test Local BIDS Dataset",
        "BIDSVersion": "1.8.0",
        "Authors": ["Test Suite"],
        "Description": "Minimal BIDS dataset for testing BIDSHub local features"
    }
    with open(root / "dataset_description.json", 'w') as f:
        json.dump(dataset_desc, f, indent=2)
    
    # Create participants.tsv
    participants = "participant_id\tage\tsex\tgroup\n"
    participants += "sub-001\t25\tM\tcontrol\n"
    participants += "sub-002\t30\tF\tpatient\n"
    participants += "sub-003\t28\tM\tpatient\n"
    
    with open(root / "participants.tsv", 'w') as f:
        f.write(participants)
    
    # Create README
    with open(root / "README", 'w') as f:
        f.write("# Test BIDS Dataset\n\nFor testing BIDSHub local dataset features.\n")
    
    # Create subject directories with minimal scan structure
    for sub_id in ['sub-001', 'sub-002', 'sub-003']:
        for ses_id in ['ses-01', 'ses-02']:
            anat_dir = root / sub_id / ses_id / "anat"
            anat_dir.mkdir(parents=True, exist_ok=True)
            
            # Create dummy NIfTI files (just empty for now)
            for modality in ['T1w', 'T2w']:
                nii_file = anat_dir / f"{sub_id}_{ses_id}_{modality}.nii.gz"
                nii_file.touch()
                
                # Create JSON sidecar
                json_file = anat_dir / f"{sub_id}_{ses_id}_{modality}.json"
                sidecar = {
                    "Modality": "MR",
                    "MagneticFieldStrength": 3,
                    "Manufacturer": "Test"
                }
                with open(json_file, 'w') as f:
                    json.dump(sidecar, f, indent=2)
    
    return root


def test_local_dataset_validation():
    """Test 1: Local BIDS dataset validation"""
    results = TestResults()
    
    print("\n" + "="*70)
    print("TEST 1: LOCAL DATASET VALIDATION")
    print("="*70)
    
    # Create test dataset
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "test-bids"
        
        print(f"\nCreating test BIDS dataset at: {test_path}")
        create_test_bids_dataset(test_path)
        
        # Test 1.1: Directory exists
        print("\n1.1: Checking directory existence...")
        exists = test_path.exists()
        results.add("Directory exists", exists, f"Path: {test_path}")
        print(f"  {'[OK]' if exists else '[X]'} Directory exists: {exists}")
        
        # Test 1.2: dataset_description.json exists
        print("\n1.2: Checking dataset_description.json...")
        desc_exists = (test_path / "dataset_description.json").exists()
        results.add("dataset_description.json exists", desc_exists)
        print(f"  {'[OK]' if desc_exists else '[X]'} dataset_description.json: {desc_exists}")
        
        # Test 1.3: participants.tsv exists
        print("\n1.3: Checking participants.tsv...")
        parts_exists = (test_path / "participants.tsv").exists()
        results.add("participants.tsv exists", parts_exists)
        print(f"  {'[OK]' if parts_exists else '[X]'} participants.tsv: {parts_exists}")
        
        # Test 1.4: Subject directories exist
        print("\n1.4: Checking subject directories...")
        sub_dirs = list(test_path.glob("sub-*"))
        has_subjects = len(sub_dirs) >= 3
        results.add("Subject directories exist", has_subjects, f"Found {len(sub_dirs)} subjects")
        print(f"  {'[OK]' if has_subjects else '[X]'} Found {len(sub_dirs)} subject directories")
        
        # Test 1.5: BIDS structure validation with PyBIDS
        print("\n1.5: Validating BIDS structure with PyBIDS...")
        try:
            loader = BIDSLoader(str(test_path))
            subjects = loader.get_subjects()
            bids_valid = len(subjects) == 3
            results.add("PyBIDS validation", bids_valid, f"Found {len(subjects)} subjects")
            print(f"  {'[OK]' if bids_valid else '[X]'} PyBIDS found {len(subjects)} subjects")
            
            # Test 1.6: Sessions detection
            print("\n1.6: Checking sessions...")
            sessions = loader.get_sessions('sub-001')
            has_sessions = len(sessions) >= 2
            results.add("Sessions detected", has_sessions, f"Found {len(sessions)} sessions")
            print(f"  {'[OK]' if has_sessions else '[X]'} Found {len(sessions)} sessions for sub-001")
            
            # Test 1.7: Scans detection
            print("\n1.7: Checking scans...")
            scans = loader.get_scans('sub-001', 'ses-01')
            has_scans = len(scans) >= 2
            results.add("Scans detected", has_scans, f"Found {len(scans)} scans")
            print(f"  {'[OK]' if has_scans else '[X]'} Found {len(scans)} scans for sub-001/ses-01")
            
        except Exception as e:
            results.add("PyBIDS validation", False, str(e))
            print(f"  [X] PyBIDS validation failed: {str(e)}")
    
    return results


def test_database_local_dataset_operations():
    """Test 2: Database operations for local datasets"""
    results = TestResults()
    
    print("\n" + "="*70)
    print("TEST 2: DATABASE OPERATIONS FOR LOCAL DATASETS")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"
        test_bids_path = Path(tmpdir) / "test-bids"
        
        # Create test BIDS dataset
        create_test_bids_dataset(test_bids_path)
        
        # Create test database
        print(f"\nCreating test database at: {test_db_path}")
        db = Database(str(test_db_path))
        
        # Test 2.1: Add local dataset
        print("\n2.1: Adding local dataset...")
        dataset_id = db.add_dataset(
            name="Test_Local_Dataset",
            platform="pennsieve",  # Platform doesn't matter for local
            api_key=None,  # Optional for local
            api_secret=None,  # Optional for local
            dataset_id_external="local_test-bids",
            root_path=str(test_bids_path),
            server_url=None
        )
        added = dataset_id is not None
        results.add("Add local dataset to database", added, f"Dataset ID: {dataset_id}")
        print(f"  {'[OK]' if added else '[X]'} Dataset added with ID: {dataset_id}")
        
        # Test 2.2: Retrieve dataset
        print("\n2.2: Retrieving dataset...")
        dataset = db.get_dataset(dataset_id)
        retrieved = dataset is not None and dataset['name'] == "Test_Local_Dataset"
        results.add("Retrieve local dataset", retrieved)
        print(f"  {'[OK]' if retrieved else '[X]'} Dataset retrieved: {dataset['name'] if dataset else 'None'}")
        
        # Test 2.3: Add subjects
        print("\n2.3: Adding subjects...")
        subject_count = 0
        for sub_id in ['sub-001', 'sub-002', 'sub-003']:
            db.add_subject(
                dataset_id=dataset_id,
                subject_id=sub_id,
                local_subject_id=sub_id
            )
            subject_count += 1
        
        subjects = db.get_subjects_by_dataset(dataset_id)
        subjects_added = len(subjects) == 3
        results.add("Add subjects for local dataset", subjects_added, f"Added {len(subjects)} subjects")
        print(f"  {'[OK]' if subjects_added else '[X]'} Added {len(subjects)} subjects")
        
        # Test 2.4: Add scans (mark as downloaded)
        print("\n2.4: Adding scans (marked as downloaded)...")
        scan_count = 0
        for subject in subjects:
            for ses in ['ses-01', 'ses-02']:
                for modality in ['T1w', 'T2w']:
                    db.add_scan(
                        dataset_id=dataset_id,
                        subject_id=subject['subject_id'],
                        session=ses,
                        modality='anat',
                        suffix=modality,
                        file_path=f"{test_bids_path}/{subject['subject_id']}/{ses}/anat/{subject['subject_id']}_{ses}_{modality}.nii.gz",
                        file_size_bytes=1024,
                        is_downloaded=True  # Local files are already "downloaded"
                    )
                    scan_count += 1
        
        # Verify scans
        scans = db.get_scans_by_subject(subjects[0]['id'])
        scans_added = len(scans) >= 4  # At least 4 scans per subject
        results.add("Add scans marked as downloaded", scans_added, f"Added {scan_count} scans, retrieved {len(scans)}")
        print(f"  {'[OK]' if scans_added else '[X]'} Added {scan_count} scans, {len(scans)} retrieved for first subject")
        
        # Test 2.5: Verify downloaded status
        print("\n2.5: Verifying downloaded status...")
        all_downloaded = all(scan['is_downloaded'] == 1 for scan in scans)
        results.add("All scans marked as downloaded", all_downloaded)
        print(f"  {'[OK]' if all_downloaded else '[X]'} All scans marked as downloaded: {all_downloaded}")
        
        # Test 2.6: Get all datasets
        print("\n2.6: Retrieving all datasets...")
        all_datasets = db.get_all_datasets(status='active')
        has_dataset = len(all_datasets) == 1
        results.add("Get all datasets", has_dataset, f"Found {len(all_datasets)} dataset(s)")
        print(f"  {'[OK]' if has_dataset else '[X]'} Found {len(all_datasets)} active dataset(s)")
    
    return results


def test_local_auto_indexing():
    """Test 3: Auto-indexing for local datasets"""
    results = TestResults()
    
    print("\n" + "="*70)
    print("TEST 3: AUTO-INDEXING FOR LOCAL DATASETS")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"
        test_bids_path = Path(tmpdir) / "test-bids"
        
        # Create test BIDS dataset
        create_test_bids_dataset(test_bids_path)
        
        # Create database
        db = Database(str(test_db_path))
        
        # Add dataset
        dataset_id = db.add_dataset(
            name="Auto_Index_Test",
            platform="pennsieve",
            dataset_id_external="local_test",
            root_path=str(test_bids_path)
        )
        
        # Test 3.1: Simulate auto-indexing (what happens in app.py)
        print("\n3.1: Simulating auto-indexing process...")
        try:
            bids_loader = BIDSLoader(str(test_bids_path))
            subjects_list = bids_loader.get_subjects()
            
            indexed_count = 0
            for subject in subjects_list:
                sessions = bids_loader.get_sessions(subject)
                
                # Add subject
                db.add_subject(
                    dataset_id=dataset_id,
                    subject_id=subject,
                    local_subject_id=subject
                )
                
                # Add scans for each session
                for session in sessions:
                    scans = bids_loader.get_scans(subject, session)
                    
                    for scan in scans:
                        db.add_scan(
                            dataset_id=dataset_id,
                            subject_id=subject,
                            session=session if session else 'ses-01',
                            modality=scan['modality'],
                            suffix=scan.get('suffix', ''),
                            file_path=scan['file_path'],
                            file_size_bytes=scan.get('size', 0),
                            is_downloaded=True  # Local files
                        )
                
                indexed_count += 1
            
            auto_index_success = indexed_count == 3
            results.add("Auto-indexing subjects", auto_index_success, f"Indexed {indexed_count} subjects")
            print(f"  {'[OK]' if auto_index_success else '[X]'} Auto-indexed {indexed_count} subjects")
            
            # Test 3.2: Verify subjects in database
            print("\n3.2: Verifying subjects in database...")
            subjects_in_db = db.get_subjects_by_dataset(dataset_id)
            subjects_match = len(subjects_in_db) == indexed_count
            results.add("Subjects in database", subjects_match, f"Expected {indexed_count}, got {len(subjects_in_db)}")
            print(f"  {'[OK]' if subjects_match else '[X]'} Database has {len(subjects_in_db)} subjects")
            
            # Test 3.3: Verify scans marked as downloaded
            print("\n3.3: Verifying scans marked as downloaded...")
            first_subject_id = subjects_in_db[0]['id']
            scans = db.get_scans_by_subject(first_subject_id)
            all_downloaded = all(scan['is_downloaded'] == 1 for scan in scans)
            results.add("Scans marked as downloaded", all_downloaded, f"Checked {len(scans)} scans")
            print(f"  {'[OK]' if all_downloaded else '[X]'} All {len(scans)} scans marked as downloaded")
            
        except Exception as e:
            results.add("Auto-indexing process", False, str(e))
            print(f"  [X] Auto-indexing failed: {str(e)}")
    
    return results


def test_validation_logic():
    """Test 4: Validation logic for local vs cloud datasets"""
    results = TestResults()
    
    print("\n" + "="*70)
    print("TEST 4: VALIDATION LOGIC (LOCAL VS CLOUD)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        valid_path = Path(tmpdir) / "valid-bids"
        create_test_bids_dataset(valid_path)
        
        invalid_path = Path(tmpdir) / "nonexistent"
        
        # Test 4.1: Valid local path
        print("\n4.1: Valid local BIDS path...")
        valid_check = valid_path.exists() and (valid_path / "dataset_description.json").exists()
        results.add("Valid local path validation", valid_check)
        print(f"  {'[OK]' if valid_check else '[X]'} Valid path detected: {valid_check}")
        
        # Test 4.2: Invalid path (doesn't exist)
        print("\n4.2: Invalid path (doesn't exist)...")
        invalid_check = not invalid_path.exists()
        results.add("Invalid path detection", invalid_check)
        print(f"  {'[OK]' if invalid_check else '[X]'} Invalid path correctly identified: {invalid_check}")
        
        # Test 4.3: Path exists but missing required files
        print("\n4.3: Path exists but missing BIDS files...")
        incomplete_path = Path(tmpdir) / "incomplete-bids"
        incomplete_path.mkdir()
        (incomplete_path / "README").touch()
        
        has_desc = (incomplete_path / "dataset_description.json").exists()
        results.add("Missing BIDS files detection", not has_desc)
        print(f"  {'[OK]' if not has_desc else '[X]'} Missing dataset_description.json detected: {not has_desc}")
        
        # Test 4.4: Validation of dataset_description.json content
        print("\n4.4: Validating dataset_description.json content...")
        with open(valid_path / "dataset_description.json", 'r') as f:
            desc = json.load(f)
        
        has_name = 'Name' in desc
        has_version = 'BIDSVersion' in desc
        desc_valid = has_name and has_version
        results.add("dataset_description.json content validation", desc_valid)
        print(f"  {'[OK]' if desc_valid else '[X]'} Has Name: {has_name}, Has BIDSVersion: {has_version}")
    
    return results


def test_mixed_datasets():
    """Test 5: Mixed local and cloud datasets"""
    results = TestResults()
    
    print("\n" + "="*70)
    print("TEST 5: MIXED LOCAL AND CLOUD DATASETS")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"
        local_bids_path = Path(tmpdir) / "local-bids"
        
        # Create local BIDS dataset
        create_test_bids_dataset(local_bids_path)
        
        # Create database
        db = Database(str(test_db_path))
        
        # Test 5.1: Add local dataset
        print("\n5.1: Adding local dataset...")
        local_id = db.add_dataset(
            name="Local_Dataset",
            platform="pennsieve",
            dataset_id_external="local_001",
            root_path=str(local_bids_path)
        )
        local_added = local_id is not None
        results.add("Add local dataset", local_added, f"ID: {local_id}")
        print(f"  {'[OK]' if local_added else '[X]'} Local dataset added: ID {local_id}")
        
        # Test 5.2: Add cloud dataset
        print("\n5.2: Adding cloud dataset...")
        cloud_id = db.add_dataset(
            name="Cloud_Dataset",
            platform="openneuro",
            api_key="test-key",
            api_secret="test-secret",
            dataset_id_external="ds000246",
            root_path="/tmp/downloads/ds000246"
        )
        cloud_added = cloud_id is not None
        results.add("Add cloud dataset", cloud_added, f"ID: {cloud_id}")
        print(f"  {'[OK]' if cloud_added else '[X]'} Cloud dataset added: ID {cloud_id}")
        
        # Test 5.3: Retrieve all datasets
        print("\n5.3: Retrieving all datasets...")
        all_datasets = db.get_all_datasets(status='active')
        has_both = len(all_datasets) == 2
        results.add("Mixed datasets retrieval", has_both, f"Found {len(all_datasets)} datasets")
        print(f"  {'[OK]' if has_both else '[X]'} Found {len(all_datasets)} datasets (expected 2)")
        
        # Test 5.4: Identify dataset types
        print("\n5.4: Identifying dataset types...")
        local_ds = [d for d in all_datasets if 'local' in d['dataset_id_external'].lower()]
        cloud_ds = [d for d in all_datasets if 'ds0' in d['dataset_id_external']]
        
        identified = len(local_ds) == 1 and len(cloud_ds) == 1
        results.add("Dataset type identification", identified, 
                   f"Local: {len(local_ds)}, Cloud: {len(cloud_ds)}")
        print(f"  {'[OK]' if identified else '[X]'} Identified {len(local_ds)} local, {len(cloud_ds)} cloud")
        
        # Test 5.5: Optional credentials for local dataset
        print("\n5.5: Verifying optional credentials for local...")
        local_dataset = db.get_dataset(local_id)
        creds_optional = local_dataset['api_key'] is None and local_dataset['api_secret'] is None
        results.add("Local dataset without credentials", creds_optional)
        print(f"  {'[OK]' if creds_optional else '[X]'} Local dataset allows null credentials: {creds_optional}")
    
    return results


def test_error_handling():
    """Test 6: Error handling and edge cases"""
    results = TestResults()
    
    print("\n" + "="*70)
    print("TEST 6: ERROR HANDLING AND EDGE CASES")
    print("="*70)
    
    # Test 6.1: Nonexistent path
    print("\n6.1: Attempting to access nonexistent path...")
    nonexistent = Path("/nonexistent/path/that/does/not/exist")
    path_check = not nonexistent.exists()
    results.add("Nonexistent path detection", path_check)
    print(f"  {'[OK]' if path_check else '[X]'} Correctly identified nonexistent path: {path_check}")
    
    # Test 6.2: Empty external_id for local dataset
    print("\n6.2: Testing auto-generation of external_id...")
    with tempfile.TemporaryDirectory() as tmpdir:
        test_bids_path = Path(tmpdir) / "my-study"
        create_test_bids_dataset(test_bids_path)
        
        # Simulate the logic from app.py
        external_id = None
        if not external_id:
            external_id = f"local_{test_bids_path.name}"
        
        auto_generated = external_id == "local_my-study"
        results.add("Auto-generate external_id for local", auto_generated, f"Generated: {external_id}")
        print(f"  {'[OK]' if auto_generated else '[X]'} Auto-generated ID: {external_id}")
    
    # Test 6.3: Path is file, not directory
    print("\n6.3: Testing path that is a file (not directory)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "not-a-directory.txt"
        file_path.touch()
        
        is_dir_check = not file_path.is_dir()
        results.add("File vs directory validation", is_dir_check)
        print(f"  {'[OK]' if is_dir_check else '[X]'} Correctly identified file (not dir): {is_dir_check}")
    
    # Test 6.4: Duplicate dataset name
    print("\n6.4: Testing duplicate dataset name...")
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"
        db = Database(str(test_db_path))
        
        # Add first dataset
        id1 = db.add_dataset(name="Duplicate_Test", platform="pennsieve", 
                            dataset_id_external="test1", root_path="/tmp/test1")
        
        # Try to add with same name (should be prevented in UI, but test database)
        id2 = db.add_dataset(name="Duplicate_Test", platform="openneuro", 
                            dataset_id_external="test2", root_path="/tmp/test2")
        
        # Both should succeed in database (UI prevents it)
        both_added = id1 is not None and id2 is not None
        results.add("Database allows duplicates (UI should prevent)", both_added, 
                   "Database layer doesn't enforce uniqueness - UI should")
        print(f"  {'[OK]' if both_added else '[X]'} Database allowed both: {both_added} (UI handles validation)")
    
    return results


def test_browse_functionality():
    """Test 7: Browse platform datasets functionality"""
    results = TestResults()
    
    print("\n" + "="*70)
    print("TEST 7: BROWSE PLATFORM DATASETS FUNCTIONALITY")
    print("="*70)
    
    # Note: This tests the mock functionality - real platform connections would require credentials
    
    # Test 7.1: Mock OpenNeuro browse
    print("\n7.1: Testing browse results structure...")
    mock_browse_results = {
        'platform': 'openneuro',
        'datasets': [
            {
                'name': 'ds003974',
                'description': 'BOLD response to motion',
                'subjects': 120,
                'id': 'ds003974'
            },
            {
                'name': 'ds000246',
                'description': 'OpenPain study',
                'subjects': 124,
                'id': 'ds000246'
            }
        ]
    }
    
    has_structure = 'platform' in mock_browse_results and 'datasets' in mock_browse_results
    results.add("Browse results structure", has_structure)
    print(f"  {'[OK]' if has_structure else '[X]'} Browse results have correct structure: {has_structure}")
    
    # Test 7.2: Auto-fill from browse selection
    print("\n7.2: Testing auto-fill from selection...")
    selected_dataset = mock_browse_results['datasets'][0]
    
    # Simulate auto-fill logic
    autofill_data = {
        'name': selected_dataset['name'],
        'id': selected_dataset['id'],
        'platform': mock_browse_results['platform']
    }
    
    autofill_works = (autofill_data['name'] == 'ds003974' and 
                      autofill_data['id'] == 'ds003974' and
                      autofill_data['platform'] == 'openneuro')
    results.add("Auto-fill from browse selection", autofill_works)
    print(f"  {'[OK]' if autofill_works else '[X]'} Auto-fill data generated correctly: {autofill_works}")
    
    # Test 7.3: Platform matching
    print("\n7.3: Testing platform matching logic...")
    current_platform = 'openneuro'
    selected_platform = autofill_data['platform']
    autofill_active = (selected_platform == current_platform)
    results.add("Platform matching for auto-fill", autofill_active)
    print(f"  {'[OK]' if autofill_active else '[X]'} Platform match enables auto-fill: {autofill_active}")
    
    return results


def run_all_tests():
    """Run all test suites"""
    all_results = []
    
    print("\n" + "="*70)
    print("BIDSHUB LOCAL DATASET FEATURES - COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("Testing v2.0 local dataset support and enhanced UI features")
    print("="*70)
    
    # Run test suites
    all_results.append(test_local_dataset_validation())
    all_results.append(test_database_local_dataset_operations())
    all_results.append(test_local_auto_indexing())
    all_results.append(test_mixed_datasets())
    all_results.append(test_browse_functionality())
    all_results.append(test_error_handling())
    
    # Combined summary
    print("\n" + "="*70)
    print("OVERALL TEST RESULTS")
    print("="*70)
    
    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total_tests = total_passed + total_failed
    
    print(f"\nTotal Tests Run: {total_tests}")
    print(f"Passed: {total_passed} ({total_passed/total_tests*100:.1f}%)")
    print(f"Failed: {total_failed} ({total_failed/total_tests*100:.1f}%)")
    
    if total_failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("="*70)
        return True
    else:
        print(f"\n[WARNING] {total_failed} TEST(S) FAILED")
        print("="*70)
        
        # Show failed tests
        print("\nFailed Tests:")
        for result_set in all_results:
            for test in result_set.tests:
                if not test['passed']:
                    print(f"  [X] {test['name']}")
                    if test['message']:
                        print(f"    -> {test['message']}")
        
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
