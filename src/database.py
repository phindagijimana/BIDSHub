"""
Database operations for BIDSHub.

Provides a clean interface for all database operations including
subjects, scans, download queue, and QC management.

**SQL and parameters:** this module uses the standard ``sqlite3`` API with
placeholders, e.g. ``cursor.execute(query, (value,))`` where ``query`` is a
string containing ``?`` tokens—**never** building SQL with string concatenation
of untrusted input.
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path


class Database:
    """Database manager for BIDSHub."""
    
    def __init__(self, db_path=None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, resolved via
                src.app_paths (repo-relative data/bidshub.db by default, or the
                per-user app-data dir when BIDSHUB_DATA_DIR is set — e.g. the
                desktop app). Explicit paths (tests, scripts) are used as-is.
        """
        if db_path is None:
            from src.app_paths import db_path as _resolve_db_path
            db_path = _resolve_db_path()
        self.db_path = db_path
        
        # Ensure parent directory exists
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
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
                    root_path: str = None,
                    server_url: str = None) -> Optional[int]:
        """
        Add a new dataset to the database.
        
        Args:
            name: Dataset name (must be unique)
            platform: Platform identifier (pennsieve, openneuro, xnat, dandi, fitbir, hcp, loris, enigma)
            api_key: API key (will be stored as-is, encryption recommended)
            api_secret: API secret
            dataset_id_external: External dataset ID (platform-specific)
            root_path: Local root path for dataset
            server_url: Server URL (for XNAT, LORIS)
            
        Returns:
            int: Dataset ID if successful, None otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO datasets 
                (name, platform, api_key_encrypted, api_secret_encrypted, 
                 dataset_id_external, root_path, server_url, status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """, (name, platform, api_key, api_secret, dataset_id_external, 
                 root_path, server_url, datetime.now()))
            
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
                   age: float = None, sex: str = None, diagnosis: str = None,
                   participant_group: str = None, handedness: str = None,
                   site: str = None, acquisition_date: str = None,
                   has_anat: bool = False, has_func: bool = False,
                   has_dwi: bool = False, has_fmap: bool = False,
                   metadata_json: str = None,
                   has_2wk: bool = None, has_6mo: bool = None,
                   scan_count_2wk: int = None, scan_count_6mo: int = None) -> bool:
        """
        Add a new subject to the database (v3.0+).
        
        Args:
            dataset_id: Dataset ID (FK to datasets table)
            subject_id: Full subject identifier
            local_subject_id: Local subject ID within dataset (e.g., "001")
            age: Subject age in years (optional, from metadata)
            sex: Subject sex (M/F/O) (optional, from metadata)
            diagnosis: Primary diagnosis (optional, from metadata)
            participant_group: Group assignment (optional, from metadata)
            handedness: Left/Right/Ambidextrous (optional, from metadata)
            site: Acquisition site (optional, from metadata)
            acquisition_date: Date of acquisition (optional)
            has_anat: Has anatomical scans
            has_func: Has functional scans
            has_dwi: Has diffusion scans
            has_fmap: Has fieldmap scans
            metadata_json: JSON string of additional metadata
            has_2wk: DEPRECATED (ignored, kept for backwards compatibility)
            has_6mo: DEPRECATED (ignored, kept for backwards compatibility)
            scan_count_2wk: DEPRECATED (ignored, kept for backwards compatibility)
            scan_count_6mo: DEPRECATED (ignored, kept for backwards compatibility)
            
        Returns:
            bool: True if successful
            
        Note:
            Session data should be added using add_subject_session() method.
            Deprecated session parameters are ignored but accepted for backwards compatibility.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Default local_subject_id to subject_id if not provided
            if local_subject_id is None:
                local_subject_id = subject_id
            
            # Check for duplicate (v3.1.1+)
            cursor.execute("""
                SELECT id FROM subjects 
                WHERE dataset_id = ? AND subject_id = ?
            """, (dataset_id, subject_id))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing subject - only update last_updated (v3.1.1+)
                # Metadata is stored separately, QC data preserved
                cursor.execute("""
                    UPDATE subjects 
                    SET last_updated = ?
                    WHERE id = ?
                """, (datetime.now(), existing[0]))
            else:
                # Insert new subject (subjects table has no age/sex/etc columns)
                cursor.execute("""
                    INSERT INTO subjects 
                    (subject_id, dataset_id, local_subject_id, 
                     qc_status, qc_notes, qc_reviewed_by, qc_reviewed_date, flagged,
                     automated_qc_status, automated_qc_date, automated_qc_results,
                     last_updated)
                    VALUES (?, ?, ?, 'pending', NULL, NULL, NULL, 0, 
                            'pending', NULL, NULL, ?)
                """, (subject_id, dataset_id, local_subject_id, datetime.now()))
            
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
                # Match either the canonical BIDS label (subject_id) or the
                # local id, scoped to the dataset — callers pass either form.
                cursor.execute("""
                    SELECT * FROM subjects
                    WHERE (subject_id = ? OR local_subject_id = ?) AND dataset_id = ?
                """, (subject_id, subject_id, dataset_id))
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
    
    def get_all_subjects(self, filters: Optional[Dict] = None, 
                        limit: int = None, offset: int = 0) -> List[Dict]:
        """
        Get all subjects with optional filtering and pagination (v3.1.1+).
        
        Args:
            filters: Optional dict with filter criteria
                    'qc_status': Filter by QC status
                    'has_both_sessions': Filter complete subjects
                    'flagged': Filter flagged subjects
                    'dataset_id': Filter by dataset (v3.1.1+)
            limit: Maximum number of subjects to return (None = all)
            offset: Number of subjects to skip (for pagination)
                    
        Returns:
            List of subject dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM subjects WHERE 1=1"
            params = []
            
            # Dataset filter (v3.1.1+)
            if filters and 'dataset_id' in filters:
                query += " AND dataset_id = ?"
                params.append(filters['dataset_id'])
            
            if filters:
                if 'qc_status' in filters and filters['qc_status'] != 'all':
                    query += " AND qc_status = ?"
                    params.append(filters['qc_status'])
                
                if 'has_both_sessions' in filters and filters['has_both_sessions']:
                    # Use subject_sessions table to check for 2+ sessions (v3.0+)
                    query += """ AND subject_id IN (
                        SELECT subject_id FROM subject_sessions 
                        GROUP BY subject_id, dataset_id 
                        HAVING COUNT(*) >= 2
                    )"""
                
                if 'flagged' in filters and filters['flagged']:
                    query += " AND flagged = 1"
            
            query += " ORDER BY subject_id"
            
            # Add pagination (v3.1.1+)
            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"Error getting subjects: {e}")
            return []
            
        finally:
            conn.close()
    
    def get_subjects_count(self, dataset_id: int = None, filters: Optional[Dict] = None) -> int:
        """
        Get total count of subjects (v3.1.1+ for pagination).
        
        Args:
            dataset_id: Optional dataset ID filter
            filters: Optional dict with filter criteria
            
        Returns:
            int: Total subject count
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM subjects WHERE 1=1"
            params = []
            
            # Dataset filter
            if filters and 'dataset_id' in filters:
                query += " AND dataset_id = ?"
                params.append(filters['dataset_id'])
            elif dataset_id:
                query += " AND dataset_id = ?"
                params.append(dataset_id)
            
            # QC status filter
            if filters and 'qc_status' in filters and filters['qc_status'] != 'all':
                query += " AND qc_status = ?"
                params.append(filters['qc_status'])
            
            # Flagged filter
            if filters and 'flagged' in filters and filters['flagged']:
                query += " AND flagged = 1"
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
            
        except sqlite3.Error as e:
            print(f"Error counting subjects: {e}")
            return 0
            
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
    
    def update_scan_qc(self, scan_id: int, qc_status: str,
                      notes: str = None, reviewed_by: str = None,
                      flagged: bool = None) -> bool:
        """
        Update scan-level QC status (v3.1.1+ with validation).
        
        Args:
            scan_id: Scan database ID
            qc_status: New QC status (pending/pass/fail/needs_review)
            notes: QC notes
            reviewed_by: Reviewer identifier
            flagged: Whether to flag scan for special attention
            
        Returns:
            bool: True if successful
        """
        try:
            # Validate QC status (v3.1.1+)
            valid_statuses = ['pending', 'pass', 'fail', 'needs_review']
            if qc_status not in valid_statuses:
                print(f"Invalid QC status: {qc_status}. Must be one of {valid_statuses}")
                return False
            
            # Require notes for fail/needs_review (v3.1.1+)
            if qc_status in ['fail', 'needs_review'] and not notes:
                print(f"QC notes required for status '{qc_status}'")
                return False
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Verify scan exists (v3.1.1+)
            cursor.execute("SELECT id, qc_status FROM scans WHERE id = ?", (scan_id,))
            row = cursor.fetchone()
            
            if not row:
                print(f"Scan {scan_id} not found")
                conn.close()
                return False
            
            old_status = row['qc_status']
            
            # Update scan
            update_fields = ["qc_status = ?", "last_updated = ?"]
            params = [qc_status, datetime.now()]
            
            if notes is not None:
                update_fields.append("qc_notes = ?")
                params.append(notes)
            
            if reviewed_by is not None:
                update_fields.append("reviewed_by = ?")
                update_fields.append("reviewed_date = ?")
                params.extend([reviewed_by, datetime.now()])
            
            if flagged is not None:
                update_fields.append("flagged = ?")
                params.append(1 if flagged else 0)
            
            params.append(scan_id)
            
            cursor.execute(f"""
                UPDATE scans 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """, params)
            
            # Add to QC history
            cursor.execute("""
                INSERT INTO qc_history 
                (scan_id, old_status, new_status, notes, reviewed_by, reviewed_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (scan_id, old_status, qc_status, notes, reviewed_by, datetime.now()))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating QC for scan {scan_id}: {e}")
            return False
            
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_scan_qc(self, scan_id: int) -> Optional[Dict]:
        """
        Get QC information for a specific scan (v3.1+).
        
        Args:
            scan_id: Scan database ID
            
        Returns:
            Dict with QC fields or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, subject_id, session, modality, suffix, file_path,
                       qc_status, qc_notes, reviewed_by, reviewed_date, flagged,
                       synced_to_platform, sync_date
                FROM scans
                WHERE id = ?
            """, (scan_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
            
        except sqlite3.Error as e:
            print(f"Error getting QC for scan {scan_id}: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_subject_scan_qc_summary(self, subject_id: str, dataset_id: int = None) -> Dict:
        """
        Get aggregated QC summary for all scans of a subject (v3.1+).
        
        Args:
            subject_id: Subject identifier
            dataset_id: Optional dataset ID filter
            
        Returns:
            Dict with QC summary: {
                'total_scans': 10,
                'reviewed': 8,
                'pending': 2,
                'pass': 6,
                'fail': 1,
                'needs_review': 1,
                'flagged': 2,
                'pass_rate': 75.0
            }
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            fr = self._scans_fk_subquery()
            query = f"""
                SELECT 
                    COUNT(*) as total_scans,
                    SUM(CASE WHEN s.qc_status != 'pending' THEN 1 ELSE 0 END) as reviewed,
                    SUM(CASE WHEN s.qc_status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN s.qc_status = 'pass' THEN 1 ELSE 0 END) as pass,
                    SUM(CASE WHEN s.qc_status = 'fail' THEN 1 ELSE 0 END) as fail,
                    SUM(CASE WHEN s.qc_status = 'needs_review' THEN 1 ELSE 0 END) as needs_review,
                    SUM(CASE WHEN s.flagged = 1 THEN 1 ELSE 0 END) as flagged
                FROM scans s
                WHERE {fr}
            """
            params = [subject_id]
            
            if dataset_id is not None:
                query += " AND s.dataset_id = ?"
                params.append(dataset_id)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            summary = dict(row) if row else {}
            
            # Calculate pass rate
            reviewed = summary.get('reviewed', 0)
            passed = summary.get('pass', 0)
            summary['pass_rate'] = (passed / reviewed * 100) if reviewed > 0 else 0.0
            
            return summary
            
        except sqlite3.Error as e:
            print(f"Error getting scan QC summary for {subject_id}: {e}")
            return {}
            
        finally:
            conn.close()
    
    def mark_scans_synced(self, scan_ids: List[int], sync_date: datetime = None) -> bool:
        """
        Mark scans as synced to platform (v3.1+).
        
        Args:
            scan_ids: List of scan IDs to mark as synced
            sync_date: Sync timestamp (defaults to now)
            
        Returns:
            bool: True if successful
        """
        if not scan_ids:
            return True
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            sync_timestamp = sync_date or datetime.now()
            
            # Update multiple scans
            placeholders = ','.join('?' * len(scan_ids))
            cursor.execute(f"""
                UPDATE scans
                SET synced_to_platform = 1,
                    sync_date = ?,
                    last_updated = ?
                WHERE id IN ({placeholders})
            """, [sync_timestamp, datetime.now()] + scan_ids)
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error marking scans as synced: {e}")
            return False
            
        finally:
            conn.close()
    
    def get_unsynced_scans(self, dataset_id: int = None) -> List[Dict]:
        """
        Get all scans with QC data that haven't been synced to platform (v3.1+).
        
        Args:
            dataset_id: Optional dataset ID filter
            
        Returns:
            List of scan dicts with QC data
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT id, dataset_id, subject_id, session, modality, suffix, 
                       file_path, qc_status, qc_notes, reviewed_by, reviewed_date, 
                       flagged, synced_to_platform, sync_date
                FROM scans
                WHERE (synced_to_platform = 0 OR synced_to_platform IS NULL)
                  AND qc_status != 'pending'
            """
            params = []
            
            if dataset_id is not None:
                query += " AND dataset_id = ?"
                params.append(dataset_id)
            
            query += " ORDER BY reviewed_date DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"Error getting unsynced scans: {e}")
            return []
            
        finally:
            conn.close()
    
    # ===== Scan Operations =====
    
    @staticmethod
    def _scans_fk_subquery() -> str:
        """scans.subject_id stores subjects.id as text; join via BIDS subject_id string."""
        return "s.subject_id IN (SELECT CAST(id AS TEXT) FROM subjects WHERE subject_id = ?)"
    
    def add_scan(self, subject_id: str, session: str, modality: str,
                file_path: str, suffix: str = None, file_size_bytes: int = 0,
                pennsieve_package_id: str = None, dataset_id: int = None,
                is_downloaded: bool = False) -> Optional[int]:
        """
        Add a scan to the database.
        
        Args:
            subject_id: BIDS subject identifier (e.g. sub-01)
            session: Session name (e.g., 'ses-01', 'ses-02')
            modality: Modality (e.g., 'anat', 'func', 'dwi')
            file_path: Path to scan file
            suffix: Scan suffix (e.g., 'T1w', 'bold')
            file_size_bytes: File size in bytes
            pennsieve_package_id: Pennsieve package ID
            dataset_id: Dataset ID (required; used to resolve subjects.id FK in scans)
            is_downloaded: Whether scan is already downloaded (v1.5+)
            
        Returns:
            int: Scan ID if successful, None otherwise
        """
        if dataset_id is None:
            print("Error adding scan: dataset_id is required")
            return None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM subjects WHERE subject_id = ? AND dataset_id = ?
                """,
                (subject_id, dataset_id),
            )
            row = cursor.fetchone()
            if not row:
                print(f"Error adding scan: no subject {subject_id} in dataset {dataset_id}")
                return None
            sub_pk = row[0]
            fk = str(int(sub_pk))
            
            cursor.execute("""
                INSERT INTO scans 
                (dataset_id, subject_id, session, modality, suffix, file_path, 
                 file_size_bytes, is_downloaded, pennsieve_package_id, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dataset_id, fk, session, modality, suffix, file_path,
                 file_size_bytes, 1 if is_downloaded else 0, pennsieve_package_id, datetime.now()))
            
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
            fr = self._scans_fk_subquery()
            if session:
                cursor.execute(
                    f"""
                    SELECT s.* FROM scans s
                    WHERE {fr} AND s.session = ?
                    ORDER BY s.modality, s.suffix
                    """,
                    (subject_id, session),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT s.* FROM scans s
                    WHERE {fr}
                    ORDER BY s.session, s.modality, s.suffix
                    """,
                    (subject_id,),
                )
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except sqlite3.Error as e:
            print(f"Error getting scans for {subject_id}: {e}")
            return []
            
        finally:
            conn.close()
    
    def get_scans_by_subject(
        self, subject_id, dataset_id: Optional[int] = None
    ) -> List[Dict]:
        """
        List scans for a subject (BIDS `subject_id` or internal `subjects.id` as int).
        
        When ``dataset_id`` is set, only scans in that dataset (mirrors app transfer code).
        """
        bids: Optional[str] = None
        if isinstance(subject_id, int):
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                if dataset_id is not None:
                    cursor.execute(
                        """
                        SELECT subject_id FROM subjects
                        WHERE id = ? AND dataset_id = ?
                        """,
                        (subject_id, dataset_id),
                    )
                else:
                    cursor.execute(
                        "SELECT subject_id FROM subjects WHERE id = ?",
                        (subject_id,),
                    )
                row = cursor.fetchone()
                bids = row[0] if row else None
            except sqlite3.Error as e:
                print(f"Error resolving subject id {subject_id}: {e}")
                return []
            finally:
                conn.close()
            if not bids:
                return []
        else:
            bids = str(subject_id)
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            fr = self._scans_fk_subquery()
            if dataset_id is not None:
                cursor.execute(
                    f"""
                    SELECT s.* FROM scans s
                    WHERE {fr} AND s.dataset_id = ?
                    ORDER BY s.session, s.modality, s.suffix
                    """,
                    (bids, dataset_id),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT s.* FROM scans s
                    WHERE {fr}
                    ORDER BY s.session, s.modality, s.suffix
                    """,
                    (bids,),
                )
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error get_scans_by_subject: {e}")
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
    
    # ===== Metadata Operations =====
    
    def get_metadata(self, key: str) -> Optional[str]:
        """
        Get metadata value by key.
        
        Args:
            key: Metadata key
            
        Returns:
            str: Metadata value or None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            
            return row['value'] if row else None
            
        except sqlite3.Error as e:
            print(f"Error getting metadata {key}: {e}")
            return None
            
        finally:
            conn.close()
    
    def set_metadata(self, key: str, value: str) -> bool:
        """
        Set metadata value (insert or update).
        
        Args:
            key: Metadata key
            value: Metadata value
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO metadata (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (key, value, datetime.now()))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error setting metadata {key}: {e}")
            return False
            
        finally:
            conn.close()
    
    # ===== Generic Query Operations (v3.1.1+) =====
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """
        Execute a generic SQL query.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            fetch: Whether to fetch and return results
            
        Returns:
            List of dicts if fetch=True, None otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch:
                rows = cursor.fetchall()
                conn.close()
                return rows
            else:
                conn.commit()
                conn.close()
                return None
            
        except sqlite3.Error as e:
            print(f"Error executing query: {e}")
            if conn:
                conn.close()
            return None if fetch else False
    
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
            
            # Complete subjects = subjects with 2+ sessions (dynamic)
            cursor.execute("""
                SELECT COUNT(DISTINCT subject_id) 
                FROM (
                    SELECT subject_id, dataset_id, COUNT(*) as session_count
                    FROM subject_sessions
                    GROUP BY subject_id, dataset_id
                    HAVING session_count >= 2
                )
            """)
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
    
    # ===== Subject Sessions Operations (v2.1+) =====
    
    def add_subject_session(self, subject_id: str, dataset_id: int, 
                           session_id: str, scan_count: int = 0,
                           acquisition_date: str = None) -> bool:
        """
        Add or update a subject session record (v3.1.1+ with duplicate prevention).
        
        Args:
            subject_id: Subject ID (e.g., 'sub-01')
            dataset_id: Dataset ID
            session_id: Session ID (e.g., 'ses-01', 'baseline', '2WK')
            scan_count: Number of scans in this session
            acquisition_date: Optional acquisition date (ISO format)
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check for duplicate (v3.1.1+)
            cursor.execute("""
                SELECT id FROM subject_sessions 
                WHERE subject_id = ? AND dataset_id = ? AND session_id = ?
            """, (subject_id, dataset_id, session_id))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing session
                cursor.execute("""
                    UPDATE subject_sessions 
                    SET scan_count = ?,
                        acquisition_date = COALESCE(?, acquisition_date)
                    WHERE id = ?
                """, (scan_count, acquisition_date, existing[0]))
                conn.commit()
                return True
            
            cursor.execute("""
                INSERT INTO subject_sessions 
                (subject_id, dataset_id, session_id, scan_count, acquisition_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(subject_id, dataset_id, session_id) DO UPDATE SET
                    scan_count = excluded.scan_count,
                    acquisition_date = COALESCE(excluded.acquisition_date, acquisition_date)
            """, (subject_id, dataset_id, session_id, scan_count, acquisition_date))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error adding subject session: {e}")
            return False
            
        finally:
            conn.close()
    
    def get_subject_sessions(self, subject_id: str, 
                            dataset_id: Optional[int] = None) -> List[Dict]:
        """
        Get all sessions for a subject.
        
        Args:
            subject_id: Subject ID
            dataset_id: Optional dataset ID filter
            
        Returns:
            List of session dicts with keys: id, session_id, scan_count, acquisition_date
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if dataset_id:
                cursor.execute("""
                    SELECT id, subject_id, dataset_id, session_id, scan_count, 
                           acquisition_date, created_date
                    FROM subject_sessions
                    WHERE subject_id = ? AND dataset_id = ?
                    ORDER BY session_id
                """, (subject_id, dataset_id))
            else:
                cursor.execute("""
                    SELECT id, subject_id, dataset_id, session_id, scan_count, 
                           acquisition_date, created_date
                    FROM subject_sessions
                    WHERE subject_id = ?
                    ORDER BY session_id
                """, (subject_id,))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            print(f"Error getting subject sessions: {e}")
            return []
            
        finally:
            conn.close()
    
    def get_all_sessions_for_dataset(self, dataset_id: int) -> List[str]:
        """
        Get list of unique session IDs in a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            List of unique session IDs (e.g., ['ses-01', 'ses-02'])
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT session_id
                FROM subject_sessions
                WHERE dataset_id = ?
                ORDER BY session_id
            """, (dataset_id,))
            
            return [row['session_id'] for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            print(f"Error getting dataset sessions: {e}")
            return []
            
        finally:
            conn.close()
    
    def update_session_scan_count(self, subject_id: str, dataset_id: int,
                                  session_id: str) -> bool:
        """
        Update scan count for a session based on scans table.
        
        Args:
            subject_id: Subject ID
            dataset_id: Dataset ID
            session_id: Session ID
            
        Returns:
            bool: True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get dataset info to join properly
            cursor.execute("""
                SELECT COUNT(*) 
                FROM scans s
                JOIN subjects sub ON s.subject_id = sub.subject_id
                WHERE sub.subject_id = ? 
                  AND sub.dataset_id = ?
                  AND s.session = ?
            """, (subject_id, dataset_id, session_id))
            
            count = cursor.fetchone()[0]
            
            # Update session record
            cursor.execute("""
                UPDATE subject_sessions
                SET scan_count = ?
                WHERE subject_id = ? AND dataset_id = ? AND session_id = ?
            """, (count, subject_id, dataset_id, session_id))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating session scan count: {e}")
            return False
            
        finally:
            conn.close()
    
    def get_subjects_with_sessions(self, dataset_id: Optional[int] = None,
                                   session_id: Optional[str] = None) -> List[Dict]:
        """
        Get subjects with their session information.
        
        Args:
            dataset_id: Optional filter by dataset
            session_id: Optional filter by specific session
            
        Returns:
            List of subject dicts with 'sessions' key containing session list
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build query - only select columns that exist in subjects table
            query = """
                SELECT DISTINCT 
                    sub.id, sub.dataset_id, sub.subject_id, sub.local_subject_id,
                    sub.qc_status, sub.qc_notes, sub.flagged,
                    sub.automated_qc_status
                FROM subjects sub
            """
            
            filters = []
            params = []
            
            if dataset_id:
                filters.append("sub.dataset_id = ?")
                params.append(dataset_id)
            
            if session_id:
                query += " JOIN subject_sessions ss ON sub.subject_id = ss.subject_id AND sub.dataset_id = ss.dataset_id"
                filters.append("ss.session_id = ?")
                params.append(session_id)
            
            if filters:
                query += " WHERE " + " AND ".join(filters)
            
            query += " ORDER BY sub.subject_id"
            
            cursor.execute(query, tuple(params))
            subjects = [dict(row) for row in cursor.fetchall()]
            
            # Fetch sessions for each subject
            for subject in subjects:
                sessions = self.get_subject_sessions(
                    subject['subject_id'], 
                    subject['dataset_id']
                )
                subject['sessions'] = sessions
            
            return subjects

        except sqlite3.Error as e:
            print(f"Error getting subjects with sessions: {e}")
            return []

        finally:
            conn.close()

    def get_display_stats_for_dataset(self, dataset_id: int) -> Dict[str, Dict]:
        """Per-subject session/scan/modality counts for one dataset (v3.1.2+).

        Returns a dict keyed by BIDS subject label (e.g. 'sub-01') with:
            session_labels: comma-separated session ids ('None' if no sessions)
            session_count:  number of sessions
            scan_count:     number of scans
            modalities:     sorted list of distinct modalities

        Used to enrich the Browse Subjects / QC tables, whose source rows
        (the ``subjects`` table) no longer carry these as columns. Two grouped
        queries rather than N per-subject lookups.
        """
        stats: Dict[str, Dict] = {}
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Sessions (subject_sessions stores the BIDS label in subject_id)
            cursor.execute(
                """
                SELECT subject_id, GROUP_CONCAT(session_id, ', ') AS labels,
                       COUNT(*) AS n
                FROM subject_sessions
                WHERE dataset_id = ?
                GROUP BY subject_id
                """,
                (dataset_id,),
            )
            for row in cursor.fetchall():
                stats[row["subject_id"]] = {
                    "session_labels": row["labels"] or "None",
                    "session_count": row["n"] or 0,
                    "scan_count": 0,
                    "modalities": [],
                }

            # Scans + modalities (scans.subject_id holds subjects.id as text)
            cursor.execute(
                """
                SELECT sub.subject_id AS label,
                       COUNT(*) AS n,
                       GROUP_CONCAT(DISTINCT s.modality) AS mods
                FROM scans s
                JOIN subjects sub ON sub.id = CAST(s.subject_id AS INTEGER)
                WHERE sub.dataset_id = ?
                GROUP BY sub.subject_id
                """,
                (dataset_id,),
            )
            for row in cursor.fetchall():
                entry = stats.setdefault(
                    row["label"],
                    {"session_labels": "None", "session_count": 0,
                     "scan_count": 0, "modalities": []},
                )
                entry["scan_count"] = row["n"] or 0
                mods = [m for m in (row["mods"] or "").split(",") if m]
                entry["modalities"] = sorted(set(mods))

            return stats

        except sqlite3.Error as e:
            print(f"Error getting display stats for dataset {dataset_id}: {e}")
            return stats
        finally:
            conn.close()

    # ===== Data Integrity Operations (v3.1.1+) =====
    
    def check_integrity(self) -> Dict[str, any]:
        """
        Check database integrity and return issues.
        
        Returns:
            dict: Integrity check results with counts of issues found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            issues = {}
            
            # Orphaned subjects (dataset doesn't exist)
            cursor.execute("""
                SELECT COUNT(*) FROM subjects 
                WHERE dataset_id NOT IN (SELECT id FROM datasets)
            """)
            issues['orphaned_subjects'] = cursor.fetchone()[0]
            
            # Orphaned scans: scans.subject_id is FK to subjects.id (legacy rows may use BIDS)
            cursor.execute("""
                SELECT COUNT(*) FROM scans s
                WHERE NOT EXISTS (
                    SELECT 1 FROM subjects sub
                    WHERE sub.id = CAST(s.subject_id AS INTEGER)
                       OR (sub.subject_id = s.subject_id AND sub.dataset_id = s.dataset_id)
                )
            """)
            issues['orphaned_scans'] = cursor.fetchone()[0]
            
            # Orphaned sessions (subject doesn't exist)
            cursor.execute("""
                SELECT COUNT(*) FROM subject_sessions 
                WHERE subject_id NOT IN (SELECT subject_id FROM subjects)
            """)
            issues['orphaned_sessions'] = cursor.fetchone()[0]
            
            # Orphaned queue items (scan doesn't exist)
            cursor.execute("""
                SELECT COUNT(*) FROM download_queue 
                WHERE scan_id NOT IN (SELECT id FROM scans)
            """)
            issues['orphaned_queue_items'] = cursor.fetchone()[0]
            
            # Duplicate subjects
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT subject_id, dataset_id, COUNT(*) as cnt
                    FROM subjects
                    GROUP BY subject_id, dataset_id
                    HAVING cnt > 1
                )
            """)
            issues['duplicate_subjects'] = cursor.fetchone()[0]
            
            # Download state mismatches
            cursor.execute("""
                SELECT file_path FROM scans 
                WHERE is_downloaded = 1
            """)
            downloaded_scans = cursor.fetchall()
            
            missing_count = 0
            for (file_path,) in downloaded_scans:
                if file_path and not Path(file_path).exists():
                    missing_count += 1
            
            issues['download_state_mismatches'] = missing_count
            
            return issues
            
        except sqlite3.Error as e:
            print(f"Integrity check failed: {e}")
            return {}
            
        finally:
            conn.close()
    
    def cleanup_orphaned_records(self, dry_run: bool = True) -> Dict[str, int]:
        """
        Clean up orphaned records in database.
        
        Args:
            dry_run: If True, only report what would be deleted
            
        Returns:
            dict: Count of deleted/would-be-deleted records by type
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            deleted = {}
            
            if not dry_run:
                # Delete orphaned queue items
                cursor.execute("""
                    DELETE FROM download_queue 
                    WHERE scan_id NOT IN (SELECT id FROM scans)
                """)
                deleted['queue_items'] = cursor.rowcount
                
                # Delete orphaned scans (scans.subject_id = subjects.id as text, or legacy BIDS)
                cursor.execute("""
                    DELETE FROM scans
                    WHERE id IN (
                        SELECT s.id FROM scans s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM subjects sub
                            WHERE sub.id = CAST(s.subject_id AS INTEGER)
                               OR (sub.subject_id = s.subject_id AND sub.dataset_id = s.dataset_id)
                        )
                    )
                """)
                deleted['scans'] = cursor.rowcount
                
                # Delete orphaned sessions
                cursor.execute("""
                    DELETE FROM subject_sessions 
                    WHERE subject_id NOT IN (SELECT subject_id FROM subjects)
                """)
                deleted['sessions'] = cursor.rowcount
                
                # Delete orphaned subjects
                cursor.execute("""
                    DELETE FROM subjects 
                    WHERE dataset_id NOT IN (SELECT id FROM datasets)
                """)
                deleted['subjects'] = cursor.rowcount
                
                conn.commit()
            else:
                # Just count what would be deleted
                cursor.execute("""
                    SELECT COUNT(*) FROM download_queue 
                    WHERE scan_id NOT IN (SELECT id FROM scans)
                """)
                deleted['queue_items'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM scans s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM subjects sub
                        WHERE sub.id = CAST(s.subject_id AS INTEGER)
                           OR (sub.subject_id = s.subject_id AND sub.dataset_id = s.dataset_id)
                    )
                """)
                deleted['scans'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM subject_sessions 
                    WHERE subject_id NOT IN (SELECT subject_id FROM subjects)
                """)
                deleted['sessions'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM subjects 
                    WHERE dataset_id NOT IN (SELECT id FROM datasets)
                """)
                deleted['subjects'] = cursor.fetchone()[0]
            
            return deleted
            
        except sqlite3.Error as e:
            print(f"Cleanup failed: {e}")
            return {}
            
        finally:
            conn.close()
    
    def fix_download_states(self, dry_run: bool = True) -> int:
        """
        Fix download state mismatches (scans marked downloaded but file missing).
        
        Args:
            dry_run: If True, only report what would be fixed
            
        Returns:
            int: Number of records fixed/would-be-fixed
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Find scans marked as downloaded but file missing
            cursor.execute("""
                SELECT id, file_path FROM scans 
                WHERE is_downloaded = 1
            """)
            
            downloaded_scans = cursor.fetchall()
            fixed_count = 0
            
            for scan_id, file_path in downloaded_scans:
                if file_path and not Path(file_path).exists():
                    if not dry_run:
                        cursor.execute("""
                            UPDATE scans 
                            SET is_downloaded = 0, download_date = NULL 
                            WHERE id = ?
                        """, (scan_id,))
                    fixed_count += 1
            
            if not dry_run:
                conn.commit()
            
            return fixed_count
            
        except sqlite3.Error as e:
            print(f"Download state fix failed: {e}")
            return 0
            
        finally:
            conn.close()
    
    def remove_duplicate_subjects(self, dry_run: bool = True) -> int:
        """
        Remove duplicate subject entries (keep most recent by ID).
        
        Args:
            dry_run: If True, only report what would be removed
            
        Returns:
            int: Number of duplicates removed/would-be-removed
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Find duplicates
            cursor.execute("""
                SELECT subject_id, dataset_id, GROUP_CONCAT(id) as ids, COUNT(*) as cnt
                FROM subjects
                GROUP BY subject_id, dataset_id
                HAVING cnt > 1
            """)
            
            duplicates = cursor.fetchall()
            removed_count = 0
            
            for subject_id, dataset_id, ids_str, cnt in duplicates:
                ids = [int(x) for x in ids_str.split(',')]
                
                # Keep the last ID (most recent), delete others
                to_delete = ids[:-1]
                
                if not dry_run:
                    placeholders = ','.join('?' * len(to_delete))
                    cursor.execute(f"""
                        DELETE FROM subjects WHERE id IN ({placeholders})
                    """, to_delete)
                
                removed_count += len(to_delete)
            
            if not dry_run:
                conn.commit()
            
            return removed_count
            
        except sqlite3.Error as e:
            print(f"Duplicate removal failed: {e}")
            return 0
            
        finally:
            conn.close()
    
    def verify_qc_consistency(self) -> Dict[str, int]:
        """
        Verify QC data consistency across scans.
        
        Returns:
            dict: QC consistency metrics
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            result = {}
            
            # Scans with QC status set
            cursor.execute("""
                SELECT COUNT(*) FROM scans 
                WHERE qc_status IS NOT NULL AND qc_status != 'pending'
            """)
            result['scans_with_qc'] = cursor.fetchone()[0]
            
            # Scans without QC
            cursor.execute("""
                SELECT COUNT(*) FROM scans 
                WHERE qc_status IS NULL OR qc_status = 'pending'
            """)
            result['scans_without_qc'] = cursor.fetchone()[0]
            
            # QC records without notes
            cursor.execute("""
                SELECT COUNT(*) FROM scans 
                WHERE qc_status IN ('pass', 'fail', 'needs_review')
                AND (qc_notes IS NULL OR qc_notes = '')
            """)
            result['qc_without_notes'] = cursor.fetchone()[0]
            
            # Flagged scans
            cursor.execute("""
                SELECT COUNT(*) FROM scans WHERE flagged = 1
            """)
            result['flagged_scans'] = cursor.fetchone()[0]
            
            return result
            
        except sqlite3.Error as e:
            print(f"QC consistency check failed: {e}")
            return {}
            
        finally:
            conn.close()
    
    def run_integrity_maintenance(
        self, auto_fix: bool = False, dry_run: Optional[bool] = None
    ) -> Dict[str, any]:
        """
        Run comprehensive integrity check and optionally auto-fix issues.
        
        Args:
            auto_fix: If True, run cleanup/fix steps (off when False)
            dry_run: If set, False means apply fixes; True means report only (overrides
                auto_fix: dry_run True -> auto_fix False, dry_run False -> auto_fix True)
        """
        if dry_run is not None:
            auto_fix = not dry_run
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'issues_found': {},
            'fixes_applied': {}
        }
        
        # Check integrity
        issues = self.check_integrity()
        report['issues_found'] = issues
        
        total_issues = sum(issues.values())
        
        if total_issues == 0:
            report['status'] = 'clean'
            report['qc_check'] = self.verify_qc_consistency()
            return report
        
        if auto_fix:
            # Fix duplicates
            if issues.get('duplicate_subjects', 0) > 0:
                fixed = self.remove_duplicate_subjects(dry_run=False)
                report['fixes_applied']['duplicates_removed'] = fixed
            
            # Fix download states
            if issues.get('download_state_mismatches', 0) > 0:
                fixed = self.fix_download_states(dry_run=False)
                report['fixes_applied']['download_states_fixed'] = fixed
            
            # Cleanup orphans
            if any(issues.get(k, 0) > 0 for k in ['orphaned_subjects', 'orphaned_scans', 
                                                    'orphaned_sessions', 'orphaned_queue_items']):
                deleted = self.cleanup_orphaned_records(dry_run=False)
                report['fixes_applied']['orphaned_records_deleted'] = deleted
            
            report['status'] = 'fixed'
        else:
            report['status'] = 'issues_detected'
        
        report['qc_check'] = self.verify_qc_consistency()
        return report