"""Subject CRUD and subject-level QC operations."""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class SubjectMixin:
    """Manage subject records and their QC state."""

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

            # Resolve the subject's primary key. qc_history.subject_id is an
            # INTEGER FK to subjects.id, NOT the BIDS label — inserting the label
            # there fails the foreign-key constraint and aborts the whole update.
            cursor.execute(
                "SELECT id, qc_status FROM subjects WHERE subject_id = ? LIMIT 1",
                (subject_id,),
            )
            row = cursor.fetchone()
            if not row:
                print(f"Error updating QC: subject {subject_id} not found")
                return False
            sub_pk = row['id']
            old_status = row['qc_status']

            # Update subject (scoped to the resolved row)
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

            params.append(sub_pk)

            cursor.execute(f"""
                UPDATE subjects
                SET {', '.join(update_fields)}
                WHERE id = ?
            """, params)

            # Add to QC history (subject_id is the integer FK to subjects.id)
            cursor.execute("""
                INSERT INTO qc_history
                (subject_id, old_status, new_status, notes, reviewed_by, reviewed_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sub_pk, old_status, qc_status, notes, reviewed_by, datetime.now()))

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
