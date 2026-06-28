"""Download queue operations."""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class DownloadQueueMixin:
    """Enqueue scans for download and track their queue status."""

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
