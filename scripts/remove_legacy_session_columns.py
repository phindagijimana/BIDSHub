#!/usr/bin/env python3
"""
Migration Script: Remove Legacy Session Columns
Version: 3.0.0
Date: March 4, 2026

Removes deprecated columns from subjects table:
- has_2wk
- has_6mo
- scan_count_2wk
- scan_count_6mo

These columns have been replaced by the subject_sessions table (v2.1.0).
This is a breaking change and should only be run after verifying all code
has been updated to use subject_sessions table.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def migrate_database(db_path='data/bidshub.db'):
    """Remove legacy session columns from subjects table."""
    
    print("\nBIDSHub Database Migration - Remove Legacy Columns")
    print("=" * 60)
    print(f"Database: {db_path}\n")
    
    # Check database exists
    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}")
        return False
    
    # Create backup
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    import shutil
    try:
        shutil.copy2(db_path, backup_path)
        print(f"[OK] Created backup: {backup_path}\n")
    except Exception as e:
        print(f"[ERROR] Could not create backup: {e}")
        return False
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Step 1: Check if deprecated columns exist
        print("[1/4] Checking for deprecated columns...")
        cursor.execute("PRAGMA table_info(subjects)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        deprecated_cols = ['has_2wk', 'has_6mo', 'scan_count_2wk', 'scan_count_6mo']
        cols_to_remove = [col for col in deprecated_cols if col in columns]
        
        if not cols_to_remove:
            print("[OK] No deprecated columns found - migration already complete!")
            conn.close()
            return True
        
        print(f"[OK] Found {len(cols_to_remove)} deprecated columns: {cols_to_remove}\n")
        
        # Step 2: Create new subjects table without deprecated columns
        print("[2/4] Creating new subjects table without deprecated columns...")
        
        cursor.execute("""
            CREATE TABLE subjects_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER NOT NULL,
                subject_id TEXT NOT NULL,
                local_subject_id TEXT NOT NULL,
                
                -- Manual QC (human review)
                qc_status TEXT DEFAULT 'pending',
                qc_notes TEXT,
                qc_reviewed_by TEXT,
                qc_reviewed_date TIMESTAMP,
                flagged BOOLEAN DEFAULT 0,
                
                -- Automated QC (computer checks)
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
        print("[OK] New subjects table created\n")
        
        # Step 3: Copy data to new table
        print("[3/4] Copying data to new table...")
        
        cursor.execute("""
            INSERT INTO subjects_new 
                (id, dataset_id, subject_id, local_subject_id, 
                 qc_status, qc_notes, qc_reviewed_by, qc_reviewed_date, flagged,
                 automated_qc_status, automated_qc_date, automated_qc_results, last_updated)
            SELECT 
                id, dataset_id, subject_id, local_subject_id,
                qc_status, qc_notes, qc_reviewed_by, qc_reviewed_date, flagged,
                automated_qc_status, automated_qc_date, automated_qc_results, last_updated
            FROM subjects
        """)
        
        rows_copied = cursor.rowcount
        print(f"[OK] Copied {rows_copied} subjects\n")
        
        # Step 4: Replace old table with new one
        print("[4/4] Replacing old table...")
        
        # Drop old table
        cursor.execute("DROP TABLE subjects")
        
        # Rename new table
        cursor.execute("ALTER TABLE subjects_new RENAME TO subjects")
        
        # Recreate indexes
        cursor.execute("""
            CREATE INDEX idx_subjects_qc_status ON subjects(qc_status)
        """)
        cursor.execute("""
            CREATE INDEX idx_subjects_flagged ON subjects(flagged)
        """)
        cursor.execute("""
            CREATE INDEX idx_subjects_automated_qc_status ON subjects(automated_qc_status)
        """)
        cursor.execute("""
            CREATE INDEX idx_subjects_dataset ON subjects(dataset_id)
        """)
        cursor.execute("""
            CREATE INDEX idx_subjects_composite ON subjects(dataset_id, local_subject_id)
        """)
        
        print("[OK] Table replaced and indexes recreated\n")
        
        # Update database version
        cursor.execute("""
            UPDATE metadata SET value = '3.0.0' WHERE key = 'db_version'
        """)
        
        conn.commit()
        
        print("=" * 60)
        print("[[OK]] Migration completed successfully!")
        print(f"\nRemoved columns: {', '.join(cols_to_remove)}")
        print("Database version: 3.0.0")
        print(f"Backup saved: {backup_path}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        print(f"Database unchanged. Backup at: {backup_path}")
        return False
        
    finally:
        conn.close()


if __name__ == "__main__":
    print("\nWARNING: This is a breaking change!")
    print("This migration removes columns that were deprecated in v2.1.0")
    print("Ensure all code has been updated to use subject_sessions table.\n")
    
    response = input("Continue with migration? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        success = migrate_database()
        sys.exit(0 if success else 1)
    else:
        print("Migration cancelled.")
        sys.exit(0)
