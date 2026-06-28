"""Dataset CRUD operations (v1.5+)."""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional


class DatasetMixin:
    """Create, read, update and delete dataset records."""

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
