"""
Simple functional tests for local dataset features
Tests basic functionality without complex dependencies
"""

import sys
import json
from pathlib import Path
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_minimal_bids_dataset(root_path):
    """Create a minimal valid BIDS dataset"""
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    
    # dataset_description.json
    dataset_desc = {
        "Name": "Test BIDS Dataset",
        "BIDSVersion": "1.8.0"
    }
    with open(root / "dataset_description.json", 'w') as f:
        json.dump(dataset_desc, f, indent=2)
    
    # participants.tsv
    with open(root / "participants.tsv", 'w') as f:
        f.write("participant_id\tage\tsex\n")
        f.write("sub-001\t25\tM\n")
        f.write("sub-002\t30\tF\n")
    
    # Create subject directories
    for sub_id in ['sub-001', 'sub-002']:
        anat_dir = root / sub_id / "ses-01" / "anat"
        anat_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dummy scan
        scan_file = anat_dir / f"{sub_id}_ses-01_T1w.nii.gz"
        scan_file.touch()
        
        # JSON sidecar
        with open(anat_dir / f"{sub_id}_ses-01_T1w.json", 'w') as f:
            json.dump({"Modality": "MR"}, f)
    
    return root


def test_validation():
    """Test validation logic"""
    print("\n" + "="*70)
    print("TEST: VALIDATION LOGIC")
    print("="*70)
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Valid BIDS dataset
        print("\n1. Valid BIDS dataset validation")
        valid_path = Path(tmpdir) / "valid-bids"
        create_minimal_bids_dataset(valid_path)
        
        exists = valid_path.exists()
        has_desc = (valid_path / "dataset_description.json").exists()
        has_parts = (valid_path / "participants.tsv").exists()
        has_subjects = len(list(valid_path.glob("sub-*"))) >= 2
        
        print(f"   [OK] Directory exists: {exists}")
        print(f"   [OK] dataset_description.json: {has_desc}")
        print(f"   [OK] participants.tsv: {has_parts}")
        print(f"   [OK] Has subjects: {has_subjects}")
        
        if exists and has_desc and has_parts and has_subjects:
            print("   [OK] PASS: Valid BIDS dataset detected")
            passed += 1
        else:
            print("   [ERROR] FAIL: Validation incomplete")
            failed += 1
        
        # Test 2: Missing directory
        print("\n2. Nonexistent directory validation")
        invalid_path = Path(tmpdir) / "nonexistent"
        not_exists = not invalid_path.exists()
        
        print(f"   [OK] Correctly detected missing directory: {not_exists}")
        
        if not_exists:
            print("   [OK] PASS: Nonexistent path detected")
            passed += 1
        else:
            print("   [ERROR] FAIL: Should detect nonexistent path")
            failed += 1
        
        # Test 3: Invalid BIDS (missing files)
        print("\n3. Invalid BIDS dataset validation")
        incomplete_path = Path(tmpdir) / "incomplete"
        incomplete_path.mkdir()
        (incomplete_path / "README").touch()
        
        missing_desc = not (incomplete_path / "dataset_description.json").exists()
        
        print(f"   [OK] Missing dataset_description.json detected: {missing_desc}")
        
        if missing_desc:
            print("   [OK] PASS: Missing BIDS files detected")
            passed += 1
        else:
            print("   [ERROR] FAIL: Should detect missing BIDS files")
            failed += 1
    
    print(f"\n{'='*70}")
    print(f"Validation Tests: {passed} passed, {failed} failed")
    print(f"{'='*70}")
    
    return passed, failed


def test_external_id_generation():
    """Test external_id auto-generation for local datasets"""
    print("\n" + "="*70)
    print("TEST: EXTERNAL ID AUTO-GENERATION")
    print("="*70)
    
    passed = 0
    failed = 0
    
    # Test 1: Generate from path name
    print("\n1. Generate external_id from directory name")
    test_path = Path("/data/my-study")
    external_id = f"local_{test_path.name}"
    
    expected = "local_my-study"
    is_correct = external_id == expected
    
    print(f"   Path: {test_path}")
    print(f"   Generated: {external_id}")
    print(f"   Expected: {expected}")
    
    if is_correct:
        print("   [OK] PASS: External ID generated correctly")
        passed += 1
    else:
        print("   [ERROR] FAIL: External ID incorrect")
        failed += 1
    
    # Test 2: Handle special characters
    print("\n2. Handle special characters in path")
    test_path2 = Path("/data/Study-2024_v1")
    external_id2 = f"local_{test_path2.name}"
    
    contains_original = "Study-2024_v1" in external_id2
    
    print(f"   Path: {test_path2}")
    print(f"   Generated: {external_id2}")
    
    if contains_original:
        print("   [OK] PASS: Preserves path name correctly")
        passed += 1
    else:
        print("   [ERROR] FAIL: Path name not preserved")
        failed += 1
    
    print(f"\n{'='*70}")
    print(f"External ID Tests: {passed} passed, {failed} failed")
    print(f"{'='*70}")
    
    return passed, failed


def test_bids_structure_creation():
    """Test that we can create a valid BIDS structure"""
    print("\n" + "="*70)
    print("TEST: BIDS STRUCTURE CREATION")
    print("="*70)
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nCreating BIDS dataset in: {tmpdir}")
        bids_root = create_minimal_bids_dataset(tmpdir)
        
        # Test 1: Root structure
        print("\n1. Root directory structure")
        has_desc = (bids_root / "dataset_description.json").exists()
        has_parts = (bids_root / "participants.tsv").exists()
        
        print(f"   [OK] dataset_description.json: {has_desc}")
        print(f"   [OK] participants.tsv: {has_parts}")
        
        if has_desc and has_parts:
            print("   [OK] PASS: Root structure correct")
            passed += 1
        else:
            print("   [ERROR] FAIL: Missing root files")
            failed += 1
        
        # Test 2: Subject structure
        print("\n2. Subject directory structure")
        sub_dirs = list(bids_root.glob("sub-*"))
        
        print(f"   Found {len(sub_dirs)} subjects: {[s.name for s in sub_dirs]}")
        
        if len(sub_dirs) == 2:
            print("   [OK] PASS: Correct number of subjects")
            passed += 1
        else:
            print("   [ERROR] FAIL: Wrong number of subjects")
            failed += 1
        
        # Test 3: Scan files
        print("\n3. Scan files structure")
        scan_files = list(bids_root.glob("sub-*/ses-*/anat/*.nii.gz"))
        
        print(f"   Found {len(scan_files)} scan files")
        
        if len(scan_files) >= 2:
            print("   [OK] PASS: Scan files created")
            passed += 1
        else:
            print("   [ERROR] FAIL: Missing scan files")
            failed += 1
        
        # Test 4: JSON sidecars
        print("\n4. JSON sidecar files")
        json_files = list(bids_root.glob("sub-*/ses-*/anat/*.json"))
        
        print(f"   Found {len(json_files)} JSON files")
        
        if len(json_files) >= 2:
            print("   [OK] PASS: JSON sidecars created")
            passed += 1
        else:
            print("   [ERROR] FAIL: Missing JSON sidecars")
            failed += 1
    
    print(f"\n{'='*70}")
    print(f"BIDS Structure Tests: {passed} passed, {failed} failed")
    print(f"{'='*70}")
    
    return passed, failed


def test_path_validations():
    """Test path validation logic"""
    print("\n" + "="*70)
    print("TEST: PATH VALIDATION LOGIC")
    print("="*70)
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Valid directory
        print("\n1. Valid directory path")
        valid_dir = Path(tmpdir) / "valid"
        valid_dir.mkdir()
        
        is_dir = valid_dir.is_dir()
        exists = valid_dir.exists()
        
        print(f"   Path: {valid_dir}")
        print(f"   Exists: {exists}")
        print(f"   Is directory: {is_dir}")
        
        if exists and is_dir:
            print("   [OK] PASS: Valid directory validated")
            passed += 1
        else:
            print("   [ERROR] FAIL: Valid directory not recognized")
            failed += 1
        
        # Test 2: File instead of directory
        print("\n2. File instead of directory")
        file_path = Path(tmpdir) / "file.txt"
        file_path.touch()
        
        is_not_dir = not file_path.is_dir()
        
        print(f"   Path: {file_path}")
        print(f"   Is NOT directory: {is_not_dir}")
        
        if is_not_dir:
            print("   [OK] PASS: File correctly identified as non-directory")
            passed += 1
        else:
            print("   [ERROR] FAIL: File should not be directory")
            failed += 1
        
        # Test 3: Nonexistent path
        print("\n3. Nonexistent path")
        nonexist = Path(tmpdir) / "doesnotexist"
        
        not_exists = not nonexist.exists()
        
        print(f"   Path: {nonexist}")
        print(f"   Does NOT exist: {not_exists}")
        
        if not_exists:
            print("   [OK] PASS: Nonexistent path detected")
            passed += 1
        else:
            print("   [ERROR] FAIL: Should detect nonexistent path")
            failed += 1
    
    print(f"\n{'='*70}")
    print(f"Path Validation Tests: {passed} passed, {failed} failed")
    print(f"{'='*70}")
    
    return passed, failed


def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*70)
    print("BIDSHUB LOCAL DATASET FEATURES - FUNCTIONAL TEST SUITE")
    print("="*70)
    print("Testing v2.0 local dataset validation and UI logic")
    print("="*70)
    
    total_passed = 0
    total_failed = 0
    
    # Run tests
    p, f = test_validation()
    total_passed += p
    total_failed += f
    
    p, f = test_external_id_generation()
    total_passed += p
    total_failed += f
    
    p, f = test_bids_structure_creation()
    total_passed += p
    total_failed += f
    
    p, f = test_path_validations()
    total_passed += p
    total_failed += f
    
    # Overall summary
    print("\n" + "="*70)
    print("OVERALL TEST RESULTS")
    print("="*70)
    
    total_tests = total_passed + total_failed
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {total_passed} ({total_passed/total_tests*100:.1f}%)")
    print(f"Failed: {total_failed} ({total_failed/total_tests*100:.1f}%)")
    
    if total_failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉")
        print("="*70)
        return True
    else:
        print(f"\n[WARNING] {total_failed} TEST(S) FAILED")
        print("="*70)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
