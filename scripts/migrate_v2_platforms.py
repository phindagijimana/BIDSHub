"""
Database Migration: v1.5 -> v2.0 (Multi-Platform Expansion)

Adds support for 6 new platforms: XNAT, DANDI, FITBIR, ENIGMA, HCP, LORIS
"""

import sqlite3
import sys
from pathlib import Path


def migrate_database(db_path='data/tracktbi.db'):
    """
    Migrate database schema to support additional platforms.
    
    Handles two scenarios:
    A. Old schema (no datasets table) - Create datasets table from scratch
    B. v1.5 schema (has datasets table) - Add server_url and update constraints
    
    Changes:
    1. Create datasets table if missing
    2. Add 'server_url' column (for XNAT, LORIS)
    3. Update platform CHECK constraint to include new platforms
    4. Add dataset_id foreign keys to subjects/scans/queue tables
    5. Update db_version metadata
    
    Args:
        db_path: Path to database file
        
    Returns:
        bool: True if successful
    """
    if not Path(db_path).exists():
        print(f"[ERROR] Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("BIDSHub Database Migration: v1.x -> v2.0")
        print("=" * 60)
        
        # Check if datasets table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='datasets'")
        datasets_exists = cursor.fetchone() is not None
        
        if not datasets_exists:
            print("\n[SCENARIO A] Old schema detected - creating datasets table...")
            
            # Create datasets table for first time
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
                    CHECK (platform IN ('pennsieve', 'openneuro', 'xnat', 'dandi', 'fitbir', 'enigma', 'hcp', 'loris')),
                    CHECK (status IN ('active', 'inactive', 'error'))
                )
            """)
            print("  [OK] datasets table created")
            
            # Add default dataset (backwards compatibility)
            cursor.execute("""
                INSERT INTO datasets (name, platform, status)
                VALUES ('Default Dataset', 'pennsieve', 'active')
            """)
            default_dataset_id = cursor.lastrowid
            print(f"  [OK] Default dataset created (ID: {default_dataset_id})")
            
            # Add dataset_id column to subjects table
            print("\n[1/5] Adding dataset_id to subjects table...")
            cursor.execute("ALTER TABLE subjects ADD COLUMN dataset_id INTEGER DEFAULT 1")
            print("  [OK] Column added")
            
            # Add dataset_id column to scans table
            print("\n[2/5] Adding dataset_id to scans table...")
            cursor.execute("ALTER TABLE scans ADD COLUMN dataset_id INTEGER DEFAULT 1")
            print("  [OK] Column added")
            
            # Add dataset_id column to download_queue table
            print("\n[3/5] Adding dataset_id to download_queue table...")
            cursor.execute("ALTER TABLE download_queue ADD COLUMN dataset_id INTEGER DEFAULT 1")
            print("  [OK] Column added")
            
            # Update subjects to use new structure
            print("\n[4/5] Updating subjects table structure...")
            cursor.execute("""
                UPDATE subjects
                SET dataset_id = 1
                WHERE dataset_id IS NULL
            """)
            print("  [OK] Subjects linked to default dataset")
            
        else:
            print("\n[SCENARIO B] v1.5 schema detected - updating for v2.0...")
            
            # Step 1: Add server_url column if missing
            print("\n[1/3] Adding server_url column to datasets table...")
            try:
                cursor.execute("ALTER TABLE datasets ADD COLUMN server_url TEXT")
                print("  [OK] Column added")
            except sqlite3.OperationalError as e:
                if 'duplicate column name' in str(e).lower():
                    print("  [INFO] Column already exists (skipping)")
                else:
                    raise
            
            # Step 2: Update platform CHECK constraint
            print("\n[2/3] Updating platform CHECK constraint...")
            
            # Create new table with updated constraint
            cursor.execute("""
                CREATE TABLE datasets_new (
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
                    CHECK (platform IN ('pennsieve', 'openneuro', 'xnat', 'dandi', 'fitbir', 'enigma', 'hcp', 'loris')),
                    CHECK (status IN ('active', 'inactive', 'error'))
                )
            """)
            
            # Copy data from old table
            cursor.execute("""
                INSERT INTO datasets_new 
                (id, name, platform, api_key_encrypted, api_secret_encrypted, 
                 dataset_id_external, root_path, server_url, status, created_date, last_sync_date)
                SELECT id, name, platform, api_key_encrypted, api_secret_encrypted,
                       dataset_id_external, root_path, 
                       CASE WHEN EXISTS(SELECT 1 FROM pragma_table_info('datasets') WHERE name='server_url')
                            THEN server_url ELSE NULL END,
                       status, created_date, last_sync_date
                FROM datasets
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE datasets")
            cursor.execute("ALTER TABLE datasets_new RENAME TO datasets")
            print("  [OK] Platform constraint updated")
        
        # Final step: Update db_version
        final_step = "[5/5]" if not datasets_exists else "[3/3]"
        print(f"\n{final_step} Updating database version...")
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at) 
            VALUES ('db_version', '2.0.0', datetime('now'))
        """)
        print("  [OK] Version updated to 2.0.0")
        
        # Record migration date
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at) 
            VALUES ('migration_v2_date', datetime('now'), datetime('now'))
        """)
        print("  [OK] Migration recorded")
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Database migrated to v2.0")
        print("\nSupported platforms:")
        print("  • Pennsieve (existing)")
        print("  • OpenNeuro (existing)")
        print("  • XNAT (new)")
        print("  • DANDI (new)")
        print("  • FITBIR (new)")
        print("  • ENIGMA (new)")
        print("  • HCP (new)")
        print("  • LORIS (new)")
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n[ERROR] Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()


def verify_migration(db_path='data/tracktbi.db'):
    """Verify migration was successful."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\nVerifying migration...")
        
        # Check version
        cursor.execute("SELECT value FROM metadata WHERE key = 'db_version'")
        version = cursor.fetchone()
        print(f"  Database version: {version[0] if version else 'unknown'}")
        
        # Check server_url column exists
        cursor.execute("PRAGMA table_info(datasets)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'server_url' in columns:
            print("  [OK] server_url column present")
        else:
            print("  [X] server_url column missing!")
            return False
        
        # Count existing datasets
        cursor.execute("SELECT COUNT(*) FROM datasets")
        count = cursor.fetchone()[0]
        print(f"  Datasets preserved: {count}")
        
        print("\n[OK] Migration verified successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Verification failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    db_path = 'data/tracktbi.db'
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Migrating database: {db_path}\n")
    
    success = migrate_database(db_path)
    
    if success:
        verify_migration(db_path)
    else:
        print("\n[ERROR] Migration failed!")
        sys.exit(1)
