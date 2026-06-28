"""Scan CRUD, scan-level QC and platform-sync operations."""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class ScanMixin:
    """Manage scan records, their QC state and platform sync flags."""

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
