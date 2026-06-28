"""QC history, key/value metadata, generic queries and statistics."""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class MiscMixin:
    """Cross-cutting helpers: QC history, metadata, raw queries and stats."""

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
