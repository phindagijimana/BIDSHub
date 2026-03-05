"""
Schema fix: Remove invalid foreign key constraint on scans.subject_id

The scans table has an invalid foreign key:
  FOREIGN KEY (subject_id) REFERENCES subjects(id)

This tries to link TEXT subject_id to INTEGER subjects.id, causing constraint failures.

Solution: Recreate scans table without this foreign key constraint.
The dataset_id foreign key is sufficient for data integrity.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path


def fix_scans_foreign_key(db_path='data/bidshub.db'):
    """
    Fix invalid foreign key constraint on scans table.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if successful, False otherwise
    """
    print("="*60)
    print("BIDSHub Schema Fix: Scans Foreign Key Constraint")
    print("="*60)
    
    if not Path(db_path).exists():
        print(f"[ERROR] Database not found: {db_path}")
        return False
    
    # Backup database
    backup_path = f"{db_path}.backup_fk_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
        
        # Disable foreign keys for migration
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Get existing data
        print("\n2. Reading existing scans data...")
        cursor.execute("SELECT COUNT(*) FROM scans")
        scan_count = cursor.fetchone()[0]
        print(f"   Found {scan_count} existing scans")
        
        cursor.execute("SELECT * FROM scans")
        existing_scans = cursor.fetchall()
        
        # Get column names
        cursor.execute("PRAGMA table_info(scans)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"   Columns: {len(columns)}")
        
        # Drop old table
        print("\n3. Dropping old scans table...")
        cursor.execute("DROP TABLE scans")
        print("   [OK] Old table dropped")
        
        # Create new scans table with corrected foreign keys
        print("\n4. Creating new scans table...")
        cursor.execute("""
            CREATE TABLE scans (
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
                reviewed_by TEXT,
                reviewed_date TIMESTAMP,
                flagged BOOLEAN DEFAULT 0,
                synced_to_platform BOOLEAN DEFAULT 0,
                sync_date TIMESTAMP,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                CHECK (qc_status IN ('pending', 'pass', 'fail', 'needs_review'))
            )
        """)
        print("   [OK] New table created (without invalid FK)")
        
        # Restore data if any
        if existing_scans:
            print(f"\n5. Restoring {len(existing_scans)} scans...")
            cursor.executemany(f"""
                INSERT INTO scans ({','.join(columns)})
                VALUES ({','.join(['?'] * len(columns))})
            """, existing_scans)
            print(f"   [OK] Data restored")
        else:
            print("\n5. No existing data to restore")
        
        # Recreate indexes
        print("\n6. Creating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_scans_subject ON scans(subject_id)",
            "CREATE INDEX IF NOT EXISTS idx_scans_session ON scans(session)",
            "CREATE INDEX IF NOT EXISTS idx_scans_modality ON scans(modality)",
            "CREATE INDEX IF NOT EXISTS idx_scans_downloaded ON scans(is_downloaded)",
            "CREATE INDEX IF NOT EXISTS idx_scans_dataset ON scans(dataset_id)",
            "CREATE INDEX IF NOT EXISTS idx_scans_flagged ON scans(flagged)",
            "CREATE INDEX IF NOT EXISTS idx_scans_qc_status ON scans(qc_status)",
            "CREATE INDEX IF NOT EXISTS idx_scans_synced ON scans(synced_to_platform)"
        ]
        
        for idx_sql in indexes:
            cursor.execute(idx_sql)
        
        print(f"   [OK] Created {len(indexes)} indexes")
        
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        
        print("\n7. Verifying schema...")
        cursor.execute("PRAGMA foreign_key_check(scans)")
        fk_errors = cursor.fetchall()
        
        if fk_errors:
            print(f"   [WARNING] Foreign key issues found: {len(fk_errors)}")
            for err in fk_errors[:5]:
                print(f"     {err}")
        else:
            print("   [OK] No foreign key errors")
        
        print(f"\n8. Schema fix complete!")
        print(f"    Scans in database: {scan_count}")
        print(f"    Backup saved to: {backup_path}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n[ERROR] Schema fix failed: {e}")
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
    
    success = fix_scans_foreign_key(db_path)
    
    if success:
        print("\n" + "="*60)
        print("[OK] SCHEMA FIX SUCCESSFUL")
        print("="*60)
        print("\nThe invalid foreign key has been removed.")
        print("Scans table now only has dataset_id foreign key.")
    else:
        print("\n" + "="*60)
        print("[ERROR] SCHEMA FIX FAILED")
        print("="*60)
        sys.exit(1)
