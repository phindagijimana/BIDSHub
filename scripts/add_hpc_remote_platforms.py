"""
Database migration: Add HPC and Remote Server platforms (v3.1.0 -> v3.1.1)

Adds 'hpc' and 'remote_server' to the platform CHECK constraint.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path


def migrate_database(db_path='data/bidshub.db'):
    """
    Migrate database to support HPC and Remote Server platforms.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if successful, False otherwise
    """
    print("="*60)
    print("BIDSHub Database Migration: v3.1.0 -> v3.1.1")
    print("Adding HPC and Remote Server platforms")
    print("="*60)
    
    if not Path(db_path).exists():
        print(f"[ERROR] Database not found: {db_path}")
        return False
    
    # Backup database
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n1. Creating backup: {backup_path}")
    try:
        shutil.copy2(db_path, backup_path)
        print(f"   [OK] Backup created")
    except Exception as e:
        print(f"   [ERROR] Backup failed: {e}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Check current version
        cursor.execute("SELECT value FROM metadata WHERE key='db_version'")
        current_version = cursor.fetchone()
        if current_version:
            current_version = current_version[0]
            print(f"\n2. Current database version: {current_version}")
        else:
            print("\n2. No version found")
            current_version = "unknown"
        
        # Get current datasets table schema
        print(f"\n3. Reading datasets table schema...")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets'")
        old_schema = cursor.fetchone()[0]
        print(f"   [OK] Current schema retrieved")
        
        # Check if constraint already updated
        if "'hpc'" in old_schema and "'remote_server'" in old_schema:
            print(f"   [OK] Platform constraint already includes HPC and Remote Server")
            print(f"   No migration needed")
            return True
        
        # Read existing data
        print(f"\n4. Reading existing datasets...")
        cursor.execute("SELECT * FROM datasets")
        existing_datasets = cursor.fetchall()
        
        cursor.execute("PRAGMA table_info(datasets)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"   Found {len(existing_datasets)} dataset(s)")
        
        # Drop old table
        print(f"\n5. Recreating datasets table...")
        cursor.execute("DROP TABLE datasets")
        
        # Create new table with updated platform constraint
        cursor.execute("""
            CREATE TABLE datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                api_key_encrypted TEXT,
                api_secret_encrypted TEXT,
                dataset_id_external TEXT,
                root_path TEXT,
                server_url TEXT,
                status TEXT DEFAULT 'active',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_sync_date TIMESTAMP,
                CHECK (platform IN ('local', 'pennsieve', 'openneuro', 'xnat', 'dandi', 'hpc', 'remote_server')),
                CHECK (status IN ('active', 'inactive', 'error'))
            )
        """)
        print(f"   [OK] New table created with HPC and Remote Server platforms")
        
        # Restore data
        if existing_datasets:
            print(f"\n6. Restoring {len(existing_datasets)} dataset(s)...")
            cursor.executemany(f"""
                INSERT INTO datasets ({','.join(columns)})
                VALUES ({','.join(['?'] * len(columns))})
            """, existing_datasets)
            print(f"   [OK] Data restored")
        else:
            print(f"\n6. No existing data to restore")
        
        # Update database version
        print(f"\n7. Updating database version to 3.1.1...")
        cursor.execute("""
            UPDATE metadata 
            SET value = '3.1.1', updated_at = ? 
            WHERE key = 'db_version'
        """, (datetime.now(),))
        print(f"   [OK] Version updated")
        
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        
        # Verify
        print(f"\n8. Verifying migration...")
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets'")
        new_schema = cursor.fetchone()[0]
        
        if "'hpc'" in new_schema and "'remote_server'" in new_schema:
            print(f"   [OK] Platform constraint updated successfully")
        else:
            print(f"   [ERROR] Platform constraint not updated correctly")
            return False
        
        cursor.execute("SELECT COUNT(*) FROM datasets")
        dataset_count = cursor.fetchone()[0]
        print(f"   [OK] Dataset count: {dataset_count}")
        
        print(f"\n9. Migration complete!")
        print(f"    Backup saved to: {backup_path}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n[ERROR] Migration failed: {e}")
        print(f"   Restoring backup from: {backup_path}")
        try:
            shutil.copy2(backup_path, db_path)
            print(f"   [OK] Database restored")
        except:
            print(f"   [ERROR] Restore failed - manual intervention required")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import sys
    
    db_path = 'data/bidshub.db'
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Target database: {db_path}\n")
    
    success = migrate_database(db_path)
    
    if success:
        print("\n" + "="*60)
        print("[OK] MIGRATION SUCCESSFUL")
        print("="*60)
        print("\nNew platforms available:")
        print("  • HPC (High-Performance Computing)")
        print("  • Remote Server (Generic SSH/SFTP)")
        print("\nNext steps:")
        print("1. Add HPC/Remote Server datasets in Manage Datasets")
        print("2. Provide SSH credentials (username + password/key)")
        print("3. Browse and download BIDS data via SSH/SFTP")
    else:
        print("\n" + "="*60)
        print("[ERROR] MIGRATION FAILED")
        print("="*60)
        sys.exit(1)
