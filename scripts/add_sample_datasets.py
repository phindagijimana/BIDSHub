"""
Add sample OpenNeuro datasets to BIDSHub for testing.

This script adds 2 pre-configured OpenNeuro datasets that can be used for testing
various BIDSHub features including browsing, filtering, downloading, and QC.
"""

import sqlite3
import os
from pathlib import Path


def add_sample_datasets(db_path='data/tracktbi.db'):
    """
    Add sample OpenNeuro datasets to the database.
    
    Sample Datasets:
    1. ds005115 - Minimal MRI dataset (1 subject) for basic testing
    2. ds000228 - Test-retest fMRI dataset (small, well-structured)
    
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
        
        # Sample datasets configuration
        sample_datasets = [
            {
                'name': 'OpenNeuro Sample - Minimal MRI (ds005115)',
                'platform': 'openneuro',
                'dataset_id_external': 'ds005115',
                'root_path': None,
                'server_url': 'https://openneuro.org',
                'status': 'active',
                'description': 'Very small dataset (1 subject) - ideal for quick testing'
            },
            {
                'name': 'OpenNeuro Sample - Test-Retest fMRI (ds000228)',
                'platform': 'openneuro',
                'dataset_id_external': 'ds000228',
                'root_path': None,
                'server_url': 'https://openneuro.org',
                'status': 'active',
                'description': 'Small test-retest dataset - good for workflow testing'
            }
        ]
        
        added_count = 0
        skipped_count = 0
        
        print("=" * 60)
        print("BIDSHub - Adding Sample OpenNeuro Datasets")
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
            print(f"     URL: {dataset['server_url']}/datasets/{dataset['dataset_id_external']}")
            
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


def list_openneuro_datasets(db_path='data/tracktbi.db'):
    """
    List all OpenNeuro datasets in the database.
    
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
            SELECT id, name, dataset_id_external, status, created_date, last_sync_date
            FROM datasets
            WHERE platform = 'openneuro'
            ORDER BY created_date DESC
        """)
        
        datasets = cursor.fetchall()
        
        if not datasets:
            print("No OpenNeuro datasets found in database.")
            return
        
        print("\n" + "=" * 80)
        print("OpenNeuro Datasets in BIDSHub")
        print("=" * 80)
        
        for ds in datasets:
            db_id, name, ext_id, status, created, synced = ds
            print(f"\n[{db_id}] {name}")
            print(f"    Dataset ID: {ext_id}")
            print(f"    Status: {status}")
            print(f"    Created: {created}")
            print(f"    Last Sync: {synced or 'Never'}")
            print(f"    URL: https://openneuro.org/datasets/{ext_id}")
        
        print("\n" + "=" * 80)
        
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to list datasets: {e}")
        
    finally:
        if conn:
            conn.close()


def remove_sample_datasets(db_path='data/tracktbi.db'):
    """
    Remove sample OpenNeuro datasets from the database.
    
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
        
        sample_ids = ['ds005115', 'ds000228']
        
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
    
    db_path = 'data/tracktbi.db'
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'add':
            add_sample_datasets(db_path)
        elif command == 'list':
            list_openneuro_datasets(db_path)
        elif command == 'remove':
            response = input("Remove sample OpenNeuro datasets? (y/N): ")
            if response.lower() == 'y':
                remove_sample_datasets(db_path)
            else:
                print("Aborted.")
        else:
            print("Unknown command. Use: add, list, or remove")
    else:
        # Default: add sample datasets
        add_sample_datasets(db_path)
