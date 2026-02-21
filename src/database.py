"""
Database operations for Data Explorer.

Provides a clean interface for all database operations including
subjects, scans, download queue, and QC management.
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class Database:
    """Database manager for Data Explorer."""
    
    def __init__(self, db_path='data/tracktbi.db'):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure database file exists and is initialized."""
        if not Path(self.db_path).exists():
            from scripts.init_db import init_database
            init_database(self.db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    # ===== Dataset Operations (v1.5+) =====
    
    def add_dataset(self, name: str, platform: str, 
                    api_key: str = None, api_secret: str = None,
                    dataset_id_external: str = None, 
                    root_path: str = None) -> Optional[int]:
        """
        Add a new dataset to the database.
        
        Args:
            name: Dataset name (must be unique)
            platform: 'pennsieve' or 'openneuro'
            api_key: API key (will be stored as-is, encryption recommended)
            api_secret: API secret
            dataset_id_external: External dataset ID (Pennsieve name or OpenNeuro ID)
            root_path: Local root path for dataset
            
        Returns:
            int: Dataset ID if successful, None otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO datasets 
                (name, platform, api_key_encrypted, api_secret_encrypted, 
                 dataset_id_external, root_path, status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
            """, (name, platform, api_key, api_secret, dataset_id_external, 
                 root_path, datetime.now()))
            
            dataset_id = cursor.lastrowid
            conn.commit()
            return dataset_id
            
        except sqlite3.Error as e:
            print(f"Error adding dataset {name}: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_dataset(self, dataset_id: int) -> Optional[Dict]:
        """
        Get dataset by ID.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dict with dataset data or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,))
            row = cursor.fetchone()
            
            return dict(row) if row else None
            
        except sqlite3.Error as e:
            print(f"Error getting dataset {dataset_id}: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_all_datasets(self, status: str = None) -> List[Dict]:
        """
        Get all datasets, optionally filtered by status.
        
        Args:
            status: Filter by status ('active', 'inactive', 'error'), None for all
            
        Returns:
            List of dataset dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if status:
                cursor.execute("SELECT * FROM datasets WHERE status = ? ORDER BY created_date DESC", (status,))
            else:
                cursor.execute("SELECT * FROM datasets ORDER BY created_date DESC")
            
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            print(f"Error getting datasets: {e}")
            return []
            
        finally:
            conn.close()
    
    def update_dataset(self, dataset_id: int, **kwargs) -> bool:
        """
        Update dataset fields.
        
        Args:
            dataset_id: Dataset ID
            **kwargs: Fields to update (name, platform, status, root_path, etc.)
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build update query from kwargs
            allowed_fields = ['name', 'platform', 'api_key_encrypted', 'api_secret_encrypted',
                            'dataset_id_external', 'root_path', 'status', 'last_sync_date']
            
            updates = []
            values = []
            
            for key, value in kwargs.items():
                if key in allowed_fields:
                    updates.append(f"{key} = ?")
                    values.append(value)
            
            if not updates:
                return False
            
            query = f"UPDATE datasets SET {', '.join(updates)} WHERE id = ?"
            values.append(dataset_id)
            
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            print(f"Error updating dataset {dataset_id}: {e}")
            return False
            
        finally:
            conn.close()
    
    def delete_dataset(self, dataset_id: int) -> bool:
        """
        Delete dataset and all associated data (CASCADE).
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
            conn.commit()
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            print(f"Error deleting dataset {dataset_id}: {e}")
            return False
            
        finally:
            conn.close()
    
    # ===== Subject Operations =====
    
    def add_subject(self, dataset_id: int, subject_id: str, 
                   local_subject_id: str = None,
                   has_2wk: bool = False, 
                   has_6mo: bool = False, scan_count_2wk: int = 0,
                   scan_count_6mo: int = 0) -> bool:
        """
        Add a new subject to the database.
        
        Args:
            dataset_id: Dataset ID (FK to datasets table)
            subject_id: Full subject identifier (for backwards compatibility)
            local_subject_id: Local subject ID within dataset (e.g., "001")
            has_2wk: Whether subject has 2WK session
            has_6mo: Whether subject has 6MO session
            scan_count_2wk: Number of scans in 2WK session
            scan_count_6mo: Number of scans in 6MO session
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Default local_subject_id to subject_id if not provided
            if local_subject_id is None:
                local_subject_id = subject_id
            
            # Use INSERT OR IGNORE followed by UPDATE to handle duplicates
            # (v1.5+ uses composite unique key on dataset_id, local_subject_id)
            cursor.execute("""
                INSERT INTO subjects 
                (dataset_id, subject_id, local_subject_id, has_2wk, has_6mo, 
                 scan_count_2wk, scan_count_6mo, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset_id, local_subject_id) DO UPDATE SET
                    subject_id = excluded.subject_id,
                    has_2wk = excluded.has_2wk,
                    has_6mo = excluded.has_6mo,
                    scan_count_2wk = excluded.scan_count_2wk,
                    scan_count_6mo = excluded.scan_count_6mo,
                    last_updated = excluded.last_updated
            """, (dataset_id, subject_id, local_subject_id, has_2wk, has_6mo, 
                 scan_count_2wk, scan_count_6mo, datetime.now()))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error adding subject {subject_id}: {e}")
            return False
            
        finally:
            conn.close()
    
    def get_subject(self, subject_id: str, dataset_id: int = None) -> Optional[Dict]:
        """
        Get subject by ID.
        
        Args:
            subject_id: Subject identifier (local_subject_id)
            dataset_id: Optional dataset ID to filter by
            
        Returns:
            Dict with subject data or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if dataset_id:
                cursor.execute("""
                    SELECT * FROM subjects 
                    WHERE local_subject_id = ? AND dataset_id = ?
                """, (subject_id, dataset_id))
            else:
                # Backwards compatibility - try to find by subject_id or local_subject_id
                cursor.execute("""
                    SELECT * FROM subjects 
                    WHERE subject_id = ? OR local_subject_id = ?
                    LIMIT 1
                """, (subject_id, subject_id))
            
            row = cursor.fetchone()
            
            return dict(row) if row else None
            
        except sqlite3.Error as e:
            print(f"Error getting subject {subject_id}: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_subjects_by_dataset(self, dataset_id: int) -> List[Dict]:
        """
        Get all subjects for a specific dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            List of subject dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM subjects 
                WHERE dataset_id = ?
                ORDER BY local_subject_id
            """, (dataset_id,))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            print(f"Error getting subjects for dataset {dataset_id}: {e}")
            return []
            
        finally:
            conn.close()
    
    def get_all_subjects(self, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Get all subjects with optional filtering.
        
        Args:
            filters: Optional dict with filter criteria
                    'qc_status': Filter by QC status
                    'has_both_sessions': Filter complete subjects
                    'flagged': Filter flagged subjects
                    
        Returns:
            List of subject dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM subjects WHERE 1=1"
            params = []
            
            if filters:
                if 'qc_status' in filters and filters['qc_status'] != 'all':
                    query += " AND qc_status = ?"
                    params.append(filters['qc_status'])
                
                if 'has_both_sessions' in filters and filters['has_both_sessions']:
                    query += " AND has_2wk = 1 AND has_6mo = 1"
                
                if 'flagged' in filters and filters['flagged']:
                    query += " AND flagged = 1"
            
            query += " ORDER BY subject_id"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"Error getting subjects: {e}")
            return []
            
        finally:
            conn.close()
    
    def update_subject_qc(self, subject_id: str, qc_status: str, 
                         notes: str = None, reviewed_by: str = None,
                         flagged: bool = None) -> bool:
        """
        Update subject QC status.
        
        Args:
            subject_id: Subject identifier
            qc_status: New QC status (pending/pass/fail/needs_review)
            notes: QC notes
            reviewed_by: Reviewer identifier
            flagged: Whether to flag subject
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get old status for history
            cursor.execute("SELECT qc_status FROM subjects WHERE subject_id = ?", 
                         (subject_id,))
            row = cursor.fetchone()
            old_status = row['qc_status'] if row else None
            
            # Update subject
            update_fields = ["qc_status = ?", "last_updated = ?"]
            params = [qc_status, datetime.now()]
            
            if notes is not None:
                update_fields.append("qc_notes = ?")
                params.append(notes)
            
            if reviewed_by is not None:
                update_fields.append("qc_reviewed_by = ?")
                update_fields.append("qc_reviewed_date = ?")
                params.extend([reviewed_by, datetime.now()])
            
            if flagged is not None:
                update_fields.append("flagged = ?")
                params.append(flagged)
            
            params.append(subject_id)
            
            cursor.execute(f"""
                UPDATE subjects 
                SET {', '.join(update_fields)}
                WHERE subject_id = ?
            """, params)
            
            # Add to QC history
            cursor.execute("""
                INSERT INTO qc_history 
                (subject_id, old_status, new_status, notes, reviewed_by, reviewed_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subject_id, old_status, qc_status, notes, reviewed_by, datetime.now()))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating QC for subject {subject_id}: {e}")
            return False
            
        finally:
            conn.close()
    
    def update_automated_qc(self, subject_id: str, status: str, 
                           results: str = None) -> bool:
        """
        Update automated QC status for a subject.
        
        Args:
            subject_id: Subject identifier
            status: QC status ('pass', 'warning', 'fail')
            results: JSON string with detailed QC results
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE subjects
                SET automated_qc_status = ?,
                    automated_qc_date = ?,
                    automated_qc_results = ?,
                    last_updated = ?
                WHERE subject_id = ?
            """, (status, datetime.now(), results, datetime.now(), subject_id))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating automated QC for {subject_id}: {e}")
            return False
            
        finally:
            conn.close()
    
    # ===== Scan Operations =====
    
    def add_scan(self, subject_id: str, session: str, modality: str,
                file_path: str, suffix: str = None, file_size_bytes: int = 0,
                pennsieve_package_id: str = None) -> Optional[int]:
        """
        Add a scan to the database.
        
        Args:
            subject_id: Subject identifier
            session: Session name (e.g., '2WK', '6MO')
            modality: Modality (e.g., 'anat', 'func', 'dwi')
            file_path: Path to scan file
            suffix: Scan suffix (e.g., 'T1w', 'bold')
            file_size_bytes: File size in bytes
            pennsieve_package_id: Pennsieve package ID
            
        Returns:
            int: Scan ID if successful, None otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO scans 
                (subject_id, session, modality, suffix, file_path, 
                 file_size_bytes, pennsieve_package_id, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (subject_id, session, modality, suffix, file_path,
                 file_size_bytes, pennsieve_package_id, datetime.now()))
            
            scan_id = cursor.lastrowid
            conn.commit()
            return scan_id
            
        except sqlite3.Error as e:
            print(f"Error adding scan: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_subject_scans(self, subject_id: str, session: str = None) -> List[Dict]:
        """
        Get all scans for a subject.
        
        Args:
            subject_id: Subject identifier
            session: Optional session filter
            
        Returns:
            List of scan dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if session:
                cursor.execute("""
                    SELECT * FROM scans 
                    WHERE subject_id = ? AND session = ?
                    ORDER BY modality, suffix
                """, (subject_id, session))
            else:
                cursor.execute("""
                    SELECT * FROM scans 
                    WHERE subject_id = ?
                    ORDER BY session, modality, suffix
                """, (subject_id,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"Error getting scans for {subject_id}: {e}")
            return []
            
        finally:
            conn.close()
    
    def update_scan_status(self, scan_id: int, is_downloaded: bool,
                          download_date: datetime = None) -> bool:
        """
        Update scan download status.
        
        Args:
            scan_id: Scan ID
            is_downloaded: Whether scan is downloaded
            download_date: Download completion date
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE scans 
                SET is_downloaded = ?, download_date = ?, last_updated = ?
                WHERE id = ?
            """, (is_downloaded, download_date or datetime.now(), 
                 datetime.now(), scan_id))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating scan {scan_id}: {e}")
            return False
            
        finally:
            conn.close()
    
    # ===== Download Queue Operations =====
    
    def add_to_download_queue(self, scan_id: int, subject_id: str,
                             file_path: str, file_size_bytes: int = 0,
                             priority: int = 0) -> Optional[int]:
        """
        Add scan to download queue.
        
        Args:
            scan_id: Scan ID
            subject_id: Subject identifier
            file_path: File path
            file_size_bytes: File size
            priority: Download priority (higher = first)
            
        Returns:
            int: Queue ID if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO download_queue 
                (scan_id, subject_id, file_path, file_size_bytes, priority)
                VALUES (?, ?, ?, ?, ?)
            """, (scan_id, subject_id, file_path, file_size_bytes, priority))
            
            queue_id = cursor.lastrowid
            conn.commit()
            return queue_id
            
        except sqlite3.Error as e:
            print(f"Error adding to download queue: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_download_queue(self, status: str = None) -> List[Dict]:
        """
        Get download queue.
        
        Args:
            status: Optional status filter (queued/downloading/completed/failed)
            
        Returns:
            List of queue item dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if status:
                cursor.execute("""
                    SELECT * FROM download_queue 
                    WHERE status = ?
                    ORDER BY priority DESC, added_date ASC
                """, (status,))
            else:
                cursor.execute("""
                    SELECT * FROM download_queue 
                    ORDER BY priority DESC, added_date ASC
                """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"Error getting download queue: {e}")
            return []
            
        finally:
            conn.close()
    
    def update_queue_status(self, queue_id: int, status: str,
                           error_message: str = None) -> bool:
        """
        Update download queue item status.
        
        Args:
            queue_id: Queue item ID
            status: New status
            error_message: Error message if failed
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            update_data = [status]
            query = "UPDATE download_queue SET status = ?"
            
            if status == 'downloading':
                query += ", started_date = ?"
                update_data.append(datetime.now())
            elif status == 'completed':
                query += ", completed_date = ?"
                update_data.append(datetime.now())
            
            if error_message:
                query += ", error_message = ?"
                update_data.append(error_message)
            
            query += " WHERE id = ?"
            update_data.append(queue_id)
            
            cursor.execute(query, update_data)
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating queue item {queue_id}: {e}")
            return False
            
        finally:
            conn.close()
    
    # ===== QC History Operations =====
    
    def get_qc_history(self, subject_id: str = None, limit: int = 50) -> List[Dict]:
        """
        Get QC history.
        
        Args:
            subject_id: Optional subject filter
            limit: Maximum number of records
            
        Returns:
            List of QC history records
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if subject_id:
                cursor.execute("""
                    SELECT * FROM qc_history 
                    WHERE subject_id = ?
                    ORDER BY reviewed_date DESC
                    LIMIT ?
                """, (subject_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM qc_history 
                    ORDER BY reviewed_date DESC
                    LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"Error getting QC history: {e}")
            return []
            
        finally:
            conn.close()
    
    # ===== Statistics Operations =====
    
    def get_stats(self) -> Dict:
        """
        Get database statistics.
        
        Returns:
            Dict with various statistics
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Subject counts
            cursor.execute("SELECT COUNT(*) FROM subjects")
            stats['total_subjects'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM subjects WHERE has_2wk = 1 AND has_6mo = 1")
            stats['complete_subjects'] = cursor.fetchone()[0]
            
            # Scan counts
            cursor.execute("SELECT COUNT(*) FROM scans")
            stats['total_scans'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM scans WHERE is_downloaded = 1")
            stats['downloaded_scans'] = cursor.fetchone()[0]
            
            # QC counts
            cursor.execute("SELECT qc_status, COUNT(*) FROM subjects GROUP BY qc_status")
            qc_counts = dict(cursor.fetchall())
            stats['qc_pending'] = qc_counts.get('pending', 0)
            stats['qc_pass'] = qc_counts.get('pass', 0)
            stats['qc_fail'] = qc_counts.get('fail', 0)
            stats['qc_review'] = qc_counts.get('needs_review', 0)
            
            # Queue stats
            cursor.execute("SELECT COUNT(*) FROM download_queue WHERE status = 'queued'")
            stats['queued_downloads'] = cursor.fetchone()[0]
            
            return stats
            
        except sqlite3.Error as e:
            print(f"Error getting stats: {e}")
            return {}
            
        finally:
            conn.close()
