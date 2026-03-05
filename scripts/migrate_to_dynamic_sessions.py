"""
Database Migration: Dynamic Sessions Support

Migrates from hardcoded 2WK/6MO sessions to flexible session support.
Enables BIDSHub to work with any session naming (ses-01, baseline, followup, etc.)
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def migrate_database(db_path='data/bidshub.db'):
    """
    Migrate database from TrackTBI-specific schema to generic BIDS schema.
    
    Changes:
    - Creates subject_sessions table for flexible session tracking
    - Migrates existing 2WK/6MO data to new table
    - Preserves all existing data
    
    Args:
        db_path: Path to database file
        
    Returns:
        bool: True if successful
    """
    print(f"BIDSHub Database Migration - Dynamic Sessions")
    print("=" * 60)
    print(f"Database: {db_path}")
    print()
    
    if not Path(db_path).exists():
        print(f"[ERROR] Database not found: {db_path}")
        return False
    
    # Backup database first
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"[OK] Created backup: {backup_path}")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if migration already done
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subject_sessions'")
        if cursor.fetchone():
            print("[INFO] Migration already applied (subject_sessions table exists)")
            print()
            return True
        
        print("[1/4] Creating subject_sessions table...")
        
        # Create new sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subject_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                dataset_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                scan_count INTEGER DEFAULT 0,
                acquisition_date TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                UNIQUE(subject_id, dataset_id, session_id)
            )
        """)
        
        # Create index for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subject_sessions_subject 
            ON subject_sessions(subject_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subject_sessions_dataset 
            ON subject_sessions(dataset_id)
        """)
        
        print("[OK] subject_sessions table created")
        print()
        
        print("[2/4] Migrating existing 2WK/6MO session data...")
        
        # Get all subjects with session data
        cursor.execute("""
            SELECT subject_id, dataset_id, has_2wk, has_6mo, 
                   scan_count_2wk, scan_count_6mo 
            FROM subjects 
            WHERE has_2wk = 1 OR has_6mo = 1
        """)
        
        rows = cursor.fetchall()
        migrated_count = 0
        
        for row in rows:
            subject_id = row['subject_id']
            dataset_id = row['dataset_id']
            has_2wk = row['has_2wk']
            has_6mo = row['has_6mo']
            count_2wk = row['scan_count_2wk']
            count_6mo = row['scan_count_6mo']
            
            # Migrate 2WK session
            if has_2wk:
                cursor.execute("""
                    INSERT OR IGNORE INTO subject_sessions 
                    (subject_id, dataset_id, session_id, scan_count)
                    VALUES (?, ?, '2WK', ?)
                """, (subject_id, dataset_id, count_2wk))
                migrated_count += 1
            
            # Migrate 6MO session
            if has_6mo:
                cursor.execute("""
                    INSERT OR IGNORE INTO subject_sessions 
                    (subject_id, dataset_id, session_id, scan_count)
                    VALUES (?, ?, '6MO', ?)
                """, (subject_id, dataset_id, count_6mo))
                migrated_count += 1
        
        print(f"[OK] Migrated {migrated_count} session records")
        print()
        
        print("[3/4] Updating metadata table...")
        
        # Add migration marker
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('db_version', '2.1.0', ?), 
                   ('migration_dynamic_sessions', 'completed', ?)
        """, (datetime.now(), datetime.now()))
        
        print("[OK] Metadata updated (db_version = 2.1.0)")
        print()
        
        print("[4/4] Committing changes...")
        conn.commit()
        
        print("[OK] Migration completed successfully!")
        print()
        print("=" * 60)
        print("IMPORTANT: The following columns are now deprecated:")
        print("  - subjects.has_2wk")
        print("  - subjects.has_6mo")
        print("  - subjects.scan_count_2wk")
        print("  - subjects.scan_count_6mo")
        print()
        print("Use subject_sessions table instead for all session queries.")
        print("These columns will be removed in a future version.")
        print("=" * 60)
        
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Migration failed: {e}")
        print()
        print("Rolling back...")
        if Path(backup_path).exists():
            shutil.copy2(backup_path, db_path)
            print(f"[OK] Restored from backup: {backup_path}")
        return False
        
    finally:
        if conn:
            conn.close()


def verify_migration(db_path='data/bidshub.db'):
    """Verify migration was successful."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subject_sessions'")
        if not cursor.fetchone():
            print("[ERROR] subject_sessions table not found")
            return False
        
        # Count migrated records
        cursor.execute("SELECT COUNT(*) FROM subject_sessions")
        count = cursor.fetchone()[0]
        
        print(f"[OK] subject_sessions table exists with {count} records")
        
        # Check metadata
        cursor.execute("SELECT value FROM metadata WHERE key='db_version'")
        version = cursor.fetchone()
        
        if version:
            print(f"[OK] Database version: {version[0]}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Verification failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print()
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/bidshub.db'
    
    # Run migration
    success = migrate_database(db_path)
    
    if success:
        print()
        print("Verifying migration...")
        verify_migration(db_path)
        print()
        print("[[OK]] Migration complete!")
    else:
        print()
        print("[[X]] Migration failed!")
        sys.exit(1)
