"""
Add sample datasets (OpenNeuro and DANDI) to BIDSHub for testing.

This script adds 4 pre-configured sample datasets:
- 2 OpenNeuro datasets
- 2 DANDI datasets

These can be used for testing various BIDSHub features including browsing, 
filtering, downloading, and QC.
"""

import sqlite3
import os
from pathlib import Path


def add_sample_datasets(db_path='data/bidshub.db'):
    """
    Add sample datasets from OpenNeuro and DANDI to the database.
    
    Sample Datasets:
    OpenNeuro:
    1. ds005115 - Dense-sampling study (1 subject, 40 sessions)
    2. ds000114 - Test-retest fMRI (10 subjects, motor/language tasks)
    
    DANDI:
    3. 000026 - Human brain cell census for BA 44/45 (MRI structural)
    4. 000058 - MITU01 Dataset (7T MR structural with parameter maps)
    
    Args:
        db_path: Path to the database file (default: data/tracktbi.db)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at {db_path}")
        print("Please run init_db.py first to create the database.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Sample datasets configuration (verified real datasets)
        sample_datasets = [
            # OpenNeuro datasets
            {
                'name': 'OpenNeuro Sample - Minimal MRI (ds005115)',
                'platform': 'openneuro',
                'dataset_id_external': 'ds005115',
                'root_path': None,
                'server_url': 'https://openneuro.org',
                'status': 'active',
                'description': '1 subject, 40 sessions - Deep phenotyping study (28andHe)'
            },
            {
                'name': 'OpenNeuro Sample - Motor/Language fMRI (ds000114)',
                'platform': 'openneuro',
                'dataset_id_external': 'ds000114',
                'root_path': None,
                'server_url': 'https://openneuro.org',
                'status': 'active',
                'description': '10 subjects, test-retest - Motor, language, spatial attention tasks'
            },
            # DANDI datasets
            {
                'name': 'DANDI Sample - Brain Cell Census (000026)',
                'platform': 'dandi',
                'dataset_id_external': '000026',
                'root_path': None,
                'server_url': 'https://dandiarchive.org',
                'status': 'active',
                'description': 'Human brain cell census for BA 44/45 - MRI structural data'
            },
            {
                'name': 'DANDI Sample - 7T MR Structural (000058)',
                'platform': 'dandi',
                'dataset_id_external': '000058',
                'root_path': None,
                'server_url': 'https://dandiarchive.org',
                'status': 'active',
                'description': '7T MR structural images with B0/B1+ parameter maps'
            }
        ]
        
        added_count = 0
        skipped_count = 0
        
        print("=" * 60)
        print("BIDSHub - Adding Sample Datasets (OpenNeuro & DANDI)")
        print("=" * 60)
        
        for dataset in sample_datasets:
            # Check if dataset already exists
            cursor.execute(
                "SELECT id FROM datasets WHERE dataset_id_external = ?",
                (dataset['dataset_id_external'],)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"\n[SKIP] {dataset['name']}")
                print(f"       Dataset ID: {dataset['dataset_id_external']}")
                print(f"       Already exists in database (ID: {existing[0]})")
                skipped_count += 1
                continue
            
            # Insert new dataset
            cursor.execute("""
                INSERT INTO datasets (
                    name, platform, dataset_id_external, root_path, 
                    server_url, status, created_date
                )
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                dataset['name'],
                dataset['platform'],
                dataset['dataset_id_external'],
                dataset['root_path'],
                dataset['server_url'],
                dataset['status']
            ))
            
            dataset_id = cursor.lastrowid
            
            print(f"\n[OK] Added: {dataset['name']}")
            print(f"     Dataset ID: {dataset['dataset_id_external']}")
            print(f"     Database ID: {dataset_id}")
            print(f"     Description: {dataset['description']}")
            # Format URL based on platform
            if dataset['platform'] == 'openneuro':
                url = f"{dataset['server_url']}/datasets/{dataset['dataset_id_external']}"
            elif dataset['platform'] == 'dandi':
                url = f"{dataset['server_url']}/dandiset/{dataset['dataset_id_external']}"
            else:
                url = dataset['server_url']
            print(f"     URL: {url}")
            
            added_count += 1
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print(f"Summary: {added_count} added, {skipped_count} skipped")
        print("=" * 60)
        
        if added_count > 0:
            print("\nNext Steps:")
            print("1. Start BIDSHub: ./explorer")
            print("2. Navigate to 'Manage Datasets' page")
            print("3. Select a sample dataset from the list")
            print("4. Click 'Sync' to index the dataset metadata")
            print("5. Browse subjects and test features")
        
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to add sample datasets: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


def list_sample_datasets(db_path='data/bidshub.db'):
    """
    List all sample datasets in the database.
    
    Args:
        db_path: Path to the database file
    """
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, dataset_id_external, platform, status, created_date, last_sync_date
            FROM datasets
            WHERE platform IN ('openneuro', 'dandi')
            ORDER BY platform, created_date DESC
        """)
        
        datasets = cursor.fetchall()
        
        if not datasets:
            print("No sample datasets found in database.")
            return
        
        print("\n" + "=" * 80)
        print("Sample Datasets in BIDSHub (OpenNeuro & DANDI)")
        print("=" * 80)
        
        for ds in datasets:
            db_id, name, ext_id, platform, status, created, synced = ds
            print(f"\n[{db_id}] {name}")
            print(f"    Platform: {platform}")
            print(f"    Dataset ID: {ext_id}")
            print(f"    Status: {status}")
            print(f"    Created: {created}")
            print(f"    Last Sync: {synced or 'Never'}")
            
            # Format URL based on platform
            if platform == 'openneuro':
                url = f"https://openneuro.org/datasets/{ext_id}"
            elif platform == 'dandi':
                url = f"https://dandiarchive.org/dandiset/{ext_id}"
            else:
                url = 'N/A'
            print(f"    URL: {url}")
        
        print("\n" + "=" * 80)
        
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to list datasets: {e}")
        
    finally:
        if conn:
            conn.close()


def remove_sample_datasets(db_path='data/bidshub.db'):
    """
    Remove sample datasets (OpenNeuro and DANDI) from the database.
    
    Args:
        db_path: Path to the database file
    """
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys to cascade deletes
        cursor.execute("PRAGMA foreign_keys = ON")
        
        sample_ids = ['ds005115', 'ds000114', '000026', '000058']
        
        for dataset_id in sample_ids:
            cursor.execute(
                "DELETE FROM datasets WHERE dataset_id_external = ?",
                (dataset_id,)
            )
            if cursor.rowcount > 0:
                print(f"[OK] Removed dataset: {dataset_id}")
        
        conn.commit()
        print("[OK] Sample datasets removed")
        
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to remove sample datasets: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import sys
    
    db_path = 'data/bidshub.db'
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'add':
            add_sample_datasets(db_path)
        elif command == 'list':
            list_sample_datasets(db_path)
        elif command == 'remove':
            response = input("Remove all sample datasets (OpenNeuro + DANDI)? (y/N): ")
            if response.lower() == 'y':
                remove_sample_datasets(db_path)
            else:
                print("Aborted.")
        else:
            print("Unknown command. Use: add, list, or remove")
    else:
        # Default: add sample datasets
        add_sample_datasets(db_path)
