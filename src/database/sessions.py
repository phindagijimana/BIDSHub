"""Subject-session operations and per-dataset display statistics (v2.1+)."""

import sqlite3
from typing import Dict, List, Optional


class SessionMixin:
    """Track per-subject sessions and derive display statistics."""

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
