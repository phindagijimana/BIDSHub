"""
Migration script: Single dataset -> Multi-dataset schema

This script migrates existing database from single dataset (v1.0) to multi-dataset (v1.5)
- Adds datasets table
- Adds dataset_id foreign keys to subjects, scans, download_queue
- Preserves existing data by creating a default dataset
"""

import sqlite3
import os
import shutil
from pathlib import Path
from datetime import datetime


def backup_database(db_path):
    """Create backup of database before migration."""
    if not os.path.exists(db_path):
        print(f"[INFO] No existing database at {db_path}")
        return None
    
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"[OK] Backup created: {backup_path}")
    return backup_path


def migrate_database(db_path='data/tracktbi.db'):
    """
    Migrate database to multi-dataset schema.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if successful, False otherwise
    """
    print("=" * 60)
    print("BIDSHub - Multi-Dataset Migration")
    print("=" * 60)
    
    # Create backup
    backup_path = backup_database(db_path)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if already migrated
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='datasets'")
        if cursor.fetchone():
            print("[INFO] Database already migrated to multi-dataset schema")
            return True
        
        print("\n[STEP 1] Creating datasets table...")
        
        # Create datasets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                api_key_encrypted TEXT,
                api_secret_encrypted TEXT,
                dataset_id_external TEXT,
                root_path TEXT,
                status TEXT DEFAULT 'active',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_sync_date TIMESTAMP,
                CHECK (platform IN ('pennsieve', 'openneuro')),
                CHECK (status IN ('active', 'inactive', 'error'))
            )
        """)
        print("[OK] Created datasets table")
        
        # Create default dataset from existing data
        print("\n[STEP 2] Creating default dataset...")
        
        # Try to get metadata about existing dataset
        cursor.execute("SELECT key, value FROM metadata WHERE key='dataset_name' OR key='platform'")
        metadata = {row['key']: row['value'] for row in cursor.fetchall()}
        
        default_name = metadata.get('dataset_name', 'Default Dataset')
        default_platform = metadata.get('platform', 'pennsieve')
        
        cursor.execute("""
            INSERT INTO datasets (name, platform, status, created_date)
            VALUES (?, ?, 'active', ?)
        """, (default_name, default_platform, datetime.now()))
        
        default_dataset_id = cursor.lastrowid
        print(f"[OK] Created default dataset (ID: {default_dataset_id}, Name: {default_name})")
        
        print("\n[STEP 3] Updating subjects table...")
        
        # Check if subjects table has data
        cursor.execute("SELECT COUNT(*) as count FROM subjects")
        subject_count = cursor.fetchone()['count']
        
        # Add dataset_id column to subjects
        cursor.execute("PRAGMA table_info(subjects)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        if 'dataset_id' not in columns:
            # Create new subjects table with dataset_id
            cursor.execute("""
                CREATE TABLE subjects_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER NOT NULL,
                    subject_id TEXT NOT NULL,
                    local_subject_id TEXT NOT NULL,
                    has_2wk BOOLEAN DEFAULT 0,
                    has_6mo BOOLEAN DEFAULT 0,
                    scan_count_2wk INTEGER DEFAULT 0,
                    scan_count_6mo INTEGER DEFAULT 0,
                    qc_status TEXT DEFAULT 'pending',
                    qc_notes TEXT,
                    qc_reviewed_by TEXT,
                    qc_reviewed_date TIMESTAMP,
                    flagged BOOLEAN DEFAULT 0,
                    automated_qc_status TEXT DEFAULT 'pending',
                    automated_qc_date TIMESTAMP,
                    automated_qc_results TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                    UNIQUE(dataset_id, local_subject_id),
                    CHECK (qc_status IN ('pending', 'pass', 'fail', 'needs_review')),
                    CHECK (automated_qc_status IN ('pending', 'pass', 'warning', 'fail'))
                )
            """)
            
            # Build dynamic SELECT based on what columns exist in old table
            old_columns = set(columns)
            optional_columns = {
                'has_2wk': '0',
                'has_6mo': '0',
                'scan_count_2wk': '0',
                'scan_count_6mo': '0',
                'qc_status': "'pending'",
                'qc_notes': 'NULL',
                'qc_reviewed_by': 'NULL',
                'qc_reviewed_date': 'NULL',
                'flagged': '0',
                'automated_qc_status': "'pending'",
                'automated_qc_date': 'NULL',
                'automated_qc_results': 'NULL',
                'last_updated': 'CURRENT_TIMESTAMP'
            }
            
            select_parts = []
            for col, default in optional_columns.items():
                if col in old_columns:
                    select_parts.append(col)
                else:
                    select_parts.append(f"{default} as {col}")
            
            select_clause = ', '.join(select_parts)
            
            # Copy existing data with default dataset_id
            cursor.execute(f"""
                INSERT INTO subjects_new 
                    (dataset_id, subject_id, local_subject_id, has_2wk, has_6mo, 
                     scan_count_2wk, scan_count_6mo, qc_status, qc_notes, 
                     qc_reviewed_by, qc_reviewed_date, flagged, automated_qc_status,
                     automated_qc_date, automated_qc_results, last_updated)
                SELECT 
                    ?, subject_id, subject_id, {select_clause}
                FROM subjects
            """, (default_dataset_id,))
            
            # Drop old table and rename
            cursor.execute("DROP TABLE subjects")
            cursor.execute("ALTER TABLE subjects_new RENAME TO subjects")
            
            print(f"[OK] Migrated {subject_count} subjects to new schema")
        else:
            print("[OK] subjects table already has dataset_id column")
        
        print("\n[STEP 4] Updating scans table...")
        
        # Check scans table
        cursor.execute("SELECT COUNT(*) as count FROM scans")
        scan_count = cursor.fetchone()['count']
        
        cursor.execute("PRAGMA table_info(scans)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        if 'dataset_id' not in columns:
            # Create new scans table with dataset_id
            cursor.execute("""
                CREATE TABLE scans_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER NOT NULL,
                    subject_id TEXT NOT NULL,
                    session TEXT NOT NULL,
                    modality TEXT NOT NULL,
                    suffix TEXT,
                    file_path TEXT NOT NULL,
                    file_size_bytes INTEGER DEFAULT 0,
                    is_downloaded BOOLEAN DEFAULT 0,
                    download_date TIMESTAMP,
                    pennsieve_package_id TEXT,
                    qc_status TEXT DEFAULT 'pending',
                    qc_notes TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                    CHECK (qc_status IN ('pending', 'pass', 'fail', 'needs_review'))
                )
            """)
            
            # Build dynamic SELECT based on what columns exist in old scans table
            old_columns = set(columns)
            scan_optional_columns = {
                'session': "'UNK'",
                'modality': "'UNK'",
                'suffix': "NULL",
                'file_path': "''",  # Include file_path with default
                'file_size_bytes': '0',
                'is_downloaded': '0',
                'download_date': 'NULL',
                'pennsieve_package_id': 'NULL',
                'qc_status': "'pending'",
                'qc_notes': 'NULL',
                'last_updated': 'CURRENT_TIMESTAMP'
            }
            
            scan_select_parts = []
            for col, default in scan_optional_columns.items():
                if col in old_columns:
                    scan_select_parts.append(col)
                else:
                    scan_select_parts.append(f"{default} as {col}")
            
            scan_select_clause = ', '.join(scan_select_parts)
            
            # Copy existing data
            cursor.execute(f"""
                INSERT INTO scans_new
                    (dataset_id, subject_id, session, modality, suffix, file_path,
                     file_size_bytes, is_downloaded, download_date, pennsieve_package_id,
                     qc_status, qc_notes, last_updated)
                SELECT 
                    ?, subject_id, {scan_select_clause}
                FROM scans
            """, (default_dataset_id,))
            
            # Drop old and rename
            cursor.execute("DROP TABLE scans")
            cursor.execute("ALTER TABLE scans_new RENAME TO scans")
            
            print(f"[OK] Migrated {scan_count} scans to new schema")
        else:
            print("[OK] scans table already has dataset_id column")
        
        print("\n[STEP 5] Updating download_queue table...")
        
        cursor.execute("PRAGMA table_info(download_queue)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        if 'dataset_id' not in columns:
            # Get columns from old download_queue table
            cursor.execute("PRAGMA table_info(download_queue)")
            old_queue_columns = {col['name'] for col in cursor.fetchall()}
            
            # Create new download_queue table
            cursor.execute("""
                CREATE TABLE download_queue_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id INTEGER NOT NULL,
                    scan_id INTEGER NOT NULL,
                    subject_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size_bytes INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'queued',
                    priority INTEGER DEFAULT 0,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_date TIMESTAMP,
                    completed_date TIMESTAMP,
                    error_message TEXT,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
                    CHECK (status IN ('queued', 'downloading', 'completed', 'failed', 'paused'))
                )
            """)
            
            # Build dynamic SELECT for download_queue
            queue_optional_columns = {
                'file_path': "''",
                'file_size_bytes': '0',
                'status': "'queued'",
                'priority': '0',
                'added_date': 'CURRENT_TIMESTAMP',
                'started_date': 'NULL',
                'completed_date': 'NULL',
                'error_message': 'NULL'
            }
            
            queue_select_parts = []
            for col, default in queue_optional_columns.items():
                if col in old_queue_columns:
                    queue_select_parts.append(col)
                else:
                    queue_select_parts.append(f"{default} as {col}")
            
            queue_select_clause = ', '.join(queue_select_parts)
            
            # Copy existing data
            cursor.execute(f"""
                INSERT INTO download_queue_new
                    (dataset_id, scan_id, subject_id, file_path, file_size_bytes,
                     status, priority, added_date, started_date, completed_date, error_message)
                SELECT 
                    ?, scan_id, subject_id, {queue_select_clause}
                FROM download_queue
            """, (default_dataset_id,))
            
            # Drop old and rename
            cursor.execute("DROP TABLE download_queue")
            cursor.execute("ALTER TABLE download_queue_new RENAME TO download_queue")
            
            print("[OK] Migrated download_queue to new schema")
        else:
            print("[OK] download_queue table already has dataset_id column")
        
        print("\n[STEP 6] Creating indexes...")
        
        # Create indexes for dataset_id columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subjects_dataset ON subjects(dataset_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_dataset ON scans(dataset_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_dataset ON download_queue(dataset_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subjects_composite ON subjects(dataset_id, local_subject_id)")
        
        print("[OK] Created dataset indexes")
        
        # Update metadata
        print("\n[STEP 7] Updating metadata...")
        
        # Check if metadata table has updated_at column
        cursor.execute("PRAGMA table_info(metadata)")
        metadata_columns = {col['name'] for col in cursor.fetchall()}
        
        if 'updated_at' in metadata_columns:
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value, updated_at) 
                VALUES ('db_version', '1.5.0', ?)
            """, (datetime.now(),))
            
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value, updated_at) 
                VALUES ('multi_dataset_migration_date', ?, ?)
            """, (datetime.now().isoformat(), datetime.now()))
        else:
            # Old schema without updated_at column
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value) 
                VALUES ('db_version', '1.5.0')
            """)
            
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value) 
                VALUES ('multi_dataset_migration_date', ?)
            """, (datetime.now().isoformat(),))
        
        print("[OK] Updated database version to 1.5.0")
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Migration completed successfully!")
        print("=" * 60)
        print(f"- Default dataset created: {default_name}")
        print(f"- Subjects migrated: {subject_count}")
        print(f"- Scans migrated: {scan_count}")
        print(f"- Backup saved at: {backup_path}")
        print("\nYou can now add additional datasets via the Manage Datasets page.")
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n[ERROR] Migration failed: {e}")
        if backup_path:
            print(f"[INFO] Restore from backup: {backup_path}")
        return False
        
    finally:
        if conn:
            conn.close()


def verify_migration(db_path='data/tracktbi.db'):
    """Verify migration was successful."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n" + "=" * 60)
        print("Verifying Migration")
        print("=" * 60)
        
        # Check datasets table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='datasets'")
        if not cursor.fetchone():
            print("[ERROR] datasets table not found")
            return False
        print("[OK] datasets table exists")
        
        # Check dataset_id columns
        tables_to_check = ['subjects', 'scans', 'download_queue']
        for table in tables_to_check:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            if 'dataset_id' not in columns:
                print(f"[ERROR] {table} missing dataset_id column")
                return False
            print(f"[OK] {table} has dataset_id column")
        
        # Check indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%dataset%'")
        indexes = cursor.fetchall()
        print(f"[OK] Found {len(indexes)} dataset-related indexes")
        
        # Check default dataset
        cursor.execute("SELECT COUNT(*) FROM datasets")
        dataset_count = cursor.fetchone()[0]
        print(f"[OK] {dataset_count} dataset(s) in database")
        
        # Check data integrity
        cursor.execute("""
            SELECT COUNT(*) FROM subjects WHERE dataset_id NOT IN (SELECT id FROM datasets)
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            print(f"[WARNING] {orphaned} orphaned subjects found")
        else:
            print("[OK] No orphaned subjects")
        
        print("\n[SUCCESS] Migration verification passed!")
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Verification failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/tracktbi.db'
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        print("[INFO] Run init_db.py first to create a new database")
        sys.exit(1)
    
    # Run migration
    success = migrate_database(db_path)
    
    if success:
        # Verify migration
        verify_migration(db_path)
        print("\n[DONE] Migration complete. Restart the app to use multi-dataset features.")
    else:
        print("\n[FAILED] Migration failed. Check errors above.")
        sys.exit(1)
