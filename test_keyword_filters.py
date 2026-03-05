#!/usr/bin/env python3
"""
Test keyword and modality filtering features.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database import Database
from src.metadata_filter import MetadataFilter

def test_keyword_filtering():
    """Test keyword search functionality."""
    print("=" * 60)
    print("Testing Keyword Filtering")
    print("=" * 60)
    
    db = Database()
    
    # Get all datasets
    datasets = db.get_all_datasets(status='active')
    
    if not datasets:
        print("[ERROR] No datasets found")
        return False
    
    print(f"\n[OK] Found {len(datasets)} dataset(s)")
    for ds in datasets:
        print(f"  - {ds['name']} (ID: {ds['id']})")
    
    # Initialize MetadataFilter with database
    metadata_filter = MetadataFilter(datasets=datasets, database=db)
    
    # Test 1: Keyword search for "epilepsy"
    print("\n" + "-" * 60)
    print("Test 1: Searching for 'epilepsy'")
    print("-" * 60)
    
    epilepsy_matches = metadata_filter.filter_by_keywords(['epilepsy'])
    print(f"Found {len(epilepsy_matches)} matches")
    
    if epilepsy_matches:
        for match in epilepsy_matches[:5]:
            print(f"  - {match['subject_id']} from {match['dataset_name']}")
            print(f"    Reason: {match['match_reason']}")
    
    # Test 2: Keyword search for "TBI"
    print("\n" + "-" * 60)
    print("Test 2: Searching for 'TBI'")
    print("-" * 60)
    
    tbi_matches = metadata_filter.filter_by_keywords(['TBI', 'traumatic brain injury'])
    print(f"Found {len(tbi_matches)} matches")
    
    if tbi_matches:
        for match in tbi_matches[:5]:
            print(f"  - {match['subject_id']} from {match['dataset_name']}")
            print(f"    Reason: {match['match_reason']}")
    
    return True

def test_modality_filtering():
    """Test modality filtering functionality."""
    print("\n" + "=" * 60)
    print("Testing Modality Filtering")
    print("=" * 60)
    
    db = Database()
    
    # Get all datasets
    datasets = db.get_all_datasets(status='active')
    
    if not datasets:
        print("[ERROR] No datasets found")
        return False
    
    # Initialize MetadataFilter with database
    metadata_filter = MetadataFilter(datasets=datasets, database=db)
    
    # Test 1: Filter by T1w
    print("\n" + "-" * 60)
    print("Test 1: Filtering for T1w")
    print("-" * 60)
    
    t1_matches = metadata_filter.filter_by_modalities(['T1w'])
    print(f"Found {len(t1_matches)} subjects with T1w")
    
    if t1_matches:
        for match in t1_matches[:3]:
            print(f"  - {match['subject_id']} from {match['dataset_name']}")
            print(f"    Modalities: {', '.join(match['available_modalities'])}")
    
    # Test 2: Filter by DWI
    print("\n" + "-" * 60)
    print("Test 2: Filtering for DWI")
    print("-" * 60)
    
    dwi_matches = metadata_filter.filter_by_modalities(['DWI', 'dwi'])
    print(f"Found {len(dwi_matches)} subjects with DWI")
    
    if dwi_matches:
        for match in dwi_matches[:3]:
            print(f"  - {match['subject_id']} from {match['dataset_name']}")
            print(f"    Modalities: {', '.join(match['available_modalities'])}")
    
    # Test 3: Filter by multiple modalities
    print("\n" + "-" * 60)
    print("Test 3: Filtering for T1w + T2w")
    print("-" * 60)
    
    multi_matches = metadata_filter.filter_by_modalities(['T1w', 'T2w'])
    print(f"Found {len(multi_matches)} subjects with T1w or T2w")
    
    if multi_matches:
        for match in multi_matches[:3]:
            print(f"  - {match['subject_id']} from {match['dataset_name']}")
            print(f"    Modalities: {', '.join(match['available_modalities'])}")
    
    return True

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Keyword & Modality Filter Test Suite")
    print("=" * 60)
    
    try:
        keyword_ok = test_keyword_filtering()
        modality_ok = test_modality_filtering()
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Keyword Filtering: {'[OK] PASS' if keyword_ok else '[ERROR] FAIL'}")
        print(f"Modality Filtering: {'[OK] PASS' if modality_ok else '[ERROR] FAIL'}")
        print()
        
        return keyword_ok and modality_ok
    
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
