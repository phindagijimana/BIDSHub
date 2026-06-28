"""Data-integrity checks and cleanup/repair operations (v3.1.1+)."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class MaintenanceMixin:
    """Detect and repair orphaned/duplicate/inconsistent records."""

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
