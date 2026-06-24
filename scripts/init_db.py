"""
Database initialization script for BIDSHub.

Creates all required tables with proper schema, indexes, and constraints.
"""

import sqlite3
import os
from pathlib import Path


def init_database(db_path='data/bidshub.db'):
    """
    Initialize the SQLite database with all required tables.
    
    Args:
        db_path: Path to the database file (default: data/bidshub.db)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Ensure data directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create datasets table (v2.0+)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
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
                CHECK (platform IN ('local', 'pennsieve', 'openneuro', 'xnat', 'dandi')),
                CHECK (status IN ('active', 'inactive', 'error'))
            )
        """)
        
        # Create subjects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER NOT NULL,
                subject_id TEXT NOT NULL,
                local_subject_id TEXT NOT NULL,
                has_2wk BOOLEAN DEFAULT 0,
                has_6mo BOOLEAN DEFAULT 0,
                scan_count_2wk INTEGER DEFAULT 0,
                scan_count_6mo INTEGER DEFAULT 0,
                
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
        
        # Create scans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
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
                reviewed_by TEXT,
                reviewed_date TIMESTAMP,
                flagged BOOLEAN DEFAULT 0,
                synced_to_platform BOOLEAN DEFAULT 0,
                sync_date TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                CHECK (qc_status IN ('pending', 'pass', 'fail', 'needs_review'))
            )
        """)
        
        # Create download_queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_queue (
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
        
        # subject_sessions (v3+ dynamic sessions; was migration-only, required for integrity checks)
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
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subject_sessions_subject
            ON subject_sessions(subject_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subject_sessions_dataset
            ON subject_sessions(dataset_id)
        """)
        
        # Create qc_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qc_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER,
                scan_id INTEGER,
                old_status TEXT,
                new_status TEXT,
                notes TEXT,
                reviewed_by TEXT,
                reviewed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
            )
        """)
        
        # Create metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_qc_status 
            ON subjects(qc_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_flagged 
            ON subjects(flagged)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_automated_qc_status 
            ON subjects(automated_qc_status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scans_subject 
            ON scans(subject_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scans_session 
            ON scans(session)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scans_modality 
            ON scans(modality)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scans_downloaded 
            ON scans(is_downloaded)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_status 
            ON download_queue(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_scan 
            ON download_queue(scan_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_qc_history_subject 
            ON qc_history(subject_id)
        """)
        
        # Create indexes for dataset_id columns (v1.5+)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_dataset 
            ON subjects(dataset_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scans_dataset 
            ON scans(dataset_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_dataset 
            ON download_queue(dataset_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subjects_composite 
            ON subjects(dataset_id, local_subject_id)
        """)
        
        # Insert initial metadata
        cursor.execute("""
            INSERT OR IGNORE INTO metadata (key, value) 
            VALUES ('db_version', '2.0.0')
        """)
        
        cursor.execute("""
            INSERT OR IGNORE INTO metadata (key, value) 
            VALUES ('created_at', datetime('now'))
        """)
        
        conn.commit()
        print(f"[OK] Database initialized successfully at: {db_path}")
        print(f"[OK] Created tables: datasets, subjects, scans, download_queue, subject_sessions, qc_history, metadata")
        
        # Get index count
        index_count = cursor.execute('SELECT COUNT(*) FROM sqlite_master WHERE type="index"').fetchone()[0]
        print(f"[OK] Created {index_count} indexes")
        
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Database initialization failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


def verify_database(db_path='data/bidshub.db'):
    """
    Verify the database schema is correct.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check all tables exist
        required_tables = ['datasets', 'subjects', 'scans', 'download_queue', 'qc_history', 'metadata']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        for table in required_tables:
            if table not in existing_tables:
                print(f"[ERROR] Missing table: {table}")
                return False
        
        print(f"[OK] All {len(required_tables)} tables present")
        
        # Check metadata
        cursor.execute("SELECT key, value FROM metadata")
        metadata = dict(cursor.fetchall())
        print(f"[OK] Database version: {metadata.get('db_version', 'unknown')}")
        print(f"[OK] Created at: {metadata.get('created_at', 'unknown')}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] Database verification failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print("BIDSHub - Database Initialization")
    print("=" * 50)
    
    # Initialize database (canonical runtime path; matches Database() default)
    db_path = 'data/bidshub.db'
    
    if os.path.exists(db_path):
        if os.environ.get("BIDSHUB_NONINTERACTIVE", ""):
            print(f"[OK] Database already exists at {db_path} (non-interactive, keeping file)")
            exit(0)
        response = input(f"Database already exists at {db_path}. Recreate? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            exit(0)
        os.remove(db_path)
        print(f"[OK] Removed existing database")
    
    success = init_database(db_path)
    
    if success:
        print("\nVerifying database...")
        verify_database(db_path)
        print("\n[OK] Database ready for use!")
    else:
        print("\n[ERROR] Database initialization failed!")
        exit(1)
