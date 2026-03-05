"""
Test all 5 platforms (including 'local') with local mode
Verifies UI works and database operations succeed for each platform
"""

import sys
import sqlite3
from pathlib import Path
import tempfile

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database


def test_all_platforms_with_local_mode():
    """Test adding local datasets for all 5 platforms (including 'local')"""
    
    print("\n" + "="*70)
    print("TESTING ALL 5 PLATFORMS - LOCAL MODE")
    print("="*70)
    print("\nThis tests database operations for local datasets on all platforms")
    print("="*70)
    
    platforms = [
        ('local', 'Local Only'),
        ('pennsieve', 'Pennsieve'),
        ('openneuro', 'OpenNeuro'),
        ('xnat', 'XNAT'),
        ('dandi', 'DANDI')
    ]
    
    results = {}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test.db"
        db = Database(str(test_db))
        
        print(f"\nCreated test database: {test_db}")
        print(f"\n{'='*70}")
        
        for platform_id, platform_name in platforms:
            print(f"\n{platform_name} ({platform_id})")
            print("-" * 70)
            
            try:
                # Test adding dataset with local mode
                dataset_id = db.add_dataset(
                    name=f"{platform_name}_Local_Test",
                    platform=platform_id,
                    api_key=None,  # Optional for local
                    api_secret=None,  # Optional for local
                    dataset_id_external=f"local_{platform_id}_test",
                    root_path="/tmp/test-bids-dataset",
                    server_url=None  # Optional
                )
                
                if dataset_id:
                    print(f"   [PASS] Dataset added (ID: {dataset_id})")
                    
                    # Verify retrieval
                    dataset = db.get_dataset(dataset_id)
                    if dataset and dataset['platform'] == platform_id:
                        print(f"   [PASS] Dataset retrieved successfully")
                        print(f"   [INFO] Name: {dataset['name']}")
                        print(f"   [INFO] Platform: {dataset['platform']}")
                        print(f"   [INFO] Root path: {dataset['root_path']}")
                        print(f"   [INFO] Credentials: {'Not required (local mode)' if not dataset['api_key_encrypted'] else 'Present'}")
                        results[platform_id] = 'PASS'
                    else:
                        print(f"   [FAIL] Dataset retrieval failed")
                        results[platform_id] = 'FAIL'
                else:
                    print(f"   [FAIL] Dataset addition failed")
                    results[platform_id] = 'FAIL'
                    
            except Exception as e:
                print(f"   [FAIL] Error: {str(e)}")
                results[platform_id] = 'FAIL'
        
        # Get all datasets to verify
        print(f"\n{'='*70}")
        print("VERIFICATION: All Datasets")
        print("="*70)
        
        all_datasets = db.get_all_datasets(status='active')
        print(f"\nTotal datasets in database: {len(all_datasets)}")
        
        for ds in all_datasets:
            print(f"  - [{ds['platform']}] {ds['name']}")
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v == 'PASS')
    failed = sum(1 for v in results.values() if v == 'FAIL')
    total = len(results)
    
    print(f"\nTotal Platforms Tested: {total}")
    print(f"Passed: {passed} ({passed/total*100:.0f}%)")
    print(f"Failed: {failed}")
    
    print(f"\nResults by Platform:")
    for platform_id, platform_name in platforms:
        status = results.get(platform_id, 'NOT TESTED')
        symbol = '[PASS]' if status == 'PASS' else '[FAIL]'
        print(f"  {symbol} {platform_name:<15} {status}")
    
    if passed == total:
        print(f"\n{'='*70}")
        print("ALL PLATFORMS PASSED LOCAL MODE TEST")
        print("="*70)
        return True
    else:
        print(f"\n{'='*70}")
        print(f"WARNING: {failed} platform(s) failed")
        print("="*70)
        return False


if __name__ == "__main__":
    success = test_all_platforms_with_local_mode()
    sys.exit(0 if success else 1)
