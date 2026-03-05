"""
Migration script to add metadata columns to subjects table.

Adds fields for storing participant demographics and characteristics.
"""

import sqlite3
import sys
from pathlib import Path


def migrate_add_subject_metadata(db_path='data/tracktbi.db'):
    """
    Add metadata columns to subjects table.
    
    Args:
        db_path: Path to database file
        
    Returns:
        bool: True if successful
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if migration already applied
        cursor.execute("PRAGMA table_info(subjects)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'age' in columns:
            print("[INFO] Migration already applied")
            return True
        
        print("[INFO] Adding metadata columns to subjects table...")
        
        # Add metadata columns
        metadata_columns = [
            ("age", "REAL"),
            ("sex", "TEXT"),
            ("diagnosis", "TEXT"),
            ("participant_group", "TEXT"),
            ("handedness", "TEXT"),
            ("site", "TEXT"),
            ("acquisition_date", "TEXT"),
            ("has_anat", "BOOLEAN DEFAULT 0"),
            ("has_func", "BOOLEAN DEFAULT 0"),
            ("has_dwi", "BOOLEAN DEFAULT 0"),
            ("has_fmap", "BOOLEAN DEFAULT 0"),
            ("metadata_json", "TEXT"),
        ]
        
        for col_name, col_type in metadata_columns:
            try:
                cursor.execute(f"ALTER TABLE subjects ADD COLUMN {col_name} {col_type}")
                print(f"[OK] Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"[SKIP] Column {col_name} already exists")
                else:
                    raise
        
        # Create indexes for common filter fields
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_age ON subjects(age)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_sex ON subjects(sex)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_diagnosis ON subjects(diagnosis)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_group ON subjects(participant_group)
        """)
        
        conn.commit()
        print("[OK] Migration completed successfully")
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Migration failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/tracktbi.db'
    
    if not Path(db_path).exists():
        print(f"[ERROR] Database not found: {db_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("BIDSHub - Add Subject Metadata Migration")
    print("=" * 60)
    
    success = migrate_add_subject_metadata(db_path)
    sys.exit(0 if success else 1)
