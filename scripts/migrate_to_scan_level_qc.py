"""
Database migration: Add scan-level QC fields (v3.0.0 -> v3.1.0)

Extends scans table with complete QC tracking fields:
- reviewed_by (reviewer name/ID)
- reviewed_date (timestamp)
- flagged (boolean for special attention)
- synced_to_platform (track if QC pushed to Pennsieve)
- sync_date (last sync timestamp)

This enables scan-level QC with Pennsieve integration.
"""

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path


def migrate_database(db_path='data/bidshub.db'):
    """
    Migrate database from v3.0.0 to v3.1.0 (scan-level QC fields).
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if successful, False otherwise
    """
    print("="*60)
    print("BIDSHub Database Migration: v3.0.0 -> v3.1.0")
    print("Adding scan-level QC tracking fields")
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
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Check current version
        cursor.execute("SELECT value FROM metadata WHERE key='db_version'")
        current_version = cursor.fetchone()
        if current_version:
            current_version = current_version[0]
            print(f"\n2. Current database version: {current_version}")
        else:
            print("\n2. No version found, assuming legacy database")
            current_version = "unknown"
        
        # Check if scans table has new columns already
        cursor.execute("PRAGMA table_info(scans)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        print(f"\n3. Checking scans table columns...")
        print(f"   Existing columns: {len(existing_columns)}")
        
        # Columns to add
        new_columns = {
            'reviewed_by': 'TEXT',
            'reviewed_date': 'TIMESTAMP',
            'flagged': 'BOOLEAN DEFAULT 0',
            'synced_to_platform': 'BOOLEAN DEFAULT 0',
            'sync_date': 'TIMESTAMP'
        }
        
        columns_added = 0
        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                print(f"\n4. Adding column: {col_name} ({col_type})")
                try:
                    cursor.execute(f"ALTER TABLE scans ADD COLUMN {col_name} {col_type}")
                    columns_added += 1
                    print(f"   [OK] Column '{col_name}' added")
                except sqlite3.Error as e:
                    print(f"   [ERROR] Failed to add column '{col_name}': {e}")
                    raise
            else:
                print(f"\n4. Column '{col_name}' already exists, skipping")
        
        if columns_added == 0:
            print(f"\n[OK] All columns already exist, no migration needed")
        else:
            print(f"\n[OK] Added {columns_added} new column(s) to scans table")
        
        # Create index for flagged scans
        print(f"\n5. Creating index for flagged scans...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scans_flagged 
                ON scans(flagged)
            """)
            print(f"   [OK] Index created")
        except sqlite3.Error as e:
            print(f"   [WARNING] Index creation warning: {e}")
        
        # Create index for qc_status on scans
        print(f"\n6. Creating index for scan qc_status...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scans_qc_status 
                ON scans(qc_status)
            """)
            print(f"   [OK] Index created")
        except sqlite3.Error as e:
            print(f"   [WARNING] Index creation warning: {e}")
        
        # Create index for synced_to_platform
        print(f"\n7. Creating index for sync status...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scans_synced 
                ON scans(synced_to_platform)
            """)
            print(f"   [OK] Index created")
        except sqlite3.Error as e:
            print(f"   [WARNING] Index creation warning: {e}")
        
        # Update database version
        print(f"\n8. Updating database version to 3.1.0...")
        cursor.execute("""
            UPDATE metadata 
            SET value = '3.1.0', updated_at = ? 
            WHERE key = 'db_version'
        """, (datetime.now(),))
        print(f"   [OK] Version updated")
        
        conn.commit()
        
        # Verify migration
        print(f"\n9. Verifying migration...")
        cursor.execute("PRAGMA table_info(scans)")
        final_columns = [col[1] for col in cursor.fetchall()]
        
        all_present = all(col in final_columns for col in new_columns.keys())
        if all_present:
            print(f"   [OK] All QC columns present ({len(final_columns)} total)")
        else:
            missing = [col for col in new_columns.keys() if col not in final_columns]
            print(f"   [ERROR] Missing columns: {missing}")
            return False
        
        # Get stats
        cursor.execute("SELECT COUNT(*) FROM scans")
        scan_count = cursor.fetchone()[0]
        print(f"\n10. Migration complete!")
        print(f"    Total scans in database: {scan_count}")
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
        print("\nNext steps:")
        print("1. Test scan-level QC operations")
        print("2. Implement QC CSV export")
        print("3. Add Pennsieve upload integration")
    else:
        print("\n" + "="*60)
        print("[ERROR] MIGRATION FAILED")
        print("="*60)
        print("\nPlease check error messages above and restore from backup if needed")
        sys.exit(1)
