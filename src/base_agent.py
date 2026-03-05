"""
Base Platform Agent for BIDSHub.

Provides common interface and utilities for all platform integrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


class BasePlatformAgent(ABC):
    """
    Abstract base class for all platform agents.
    
    All platform-specific agents (Pennsieve, OpenNeuro, XNAT, DANDI, etc.)
    should inherit from this class and implement the required methods.
    """
    
    def __init__(self, credentials: Optional[Dict[str, str]] = None):
        """
        Initialize platform agent.
        
        Args:
            credentials: Dictionary of platform-specific credentials
        """
        self.credentials = credentials or {}
        self.platform_name = self._get_platform_name()
    
    def _get_platform_name(self) -> str:
        """Extract platform name from class name."""
        class_name = self.__class__.__name__
        if class_name.endswith('Agent'):
            return class_name[:-5].lower()
        return class_name.lower()
    
    @abstractmethod
    def verify_connection(self) -> bool:
        """
        Verify credentials and connection to platform.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_datasets(self) -> List[Dict]:
        """
        List available datasets on the platform.
        
        Returns:
            List of dataset dictionaries with keys:
                - id: Platform-specific dataset identifier
                - name: Human-readable dataset name
                - description: Optional description
                - subject_count: Number of subjects (if available)
        """
        pass
    
    @abstractmethod
    def get_dataset_structure(self, dataset_id: str) -> Dict:
        """
        Get complete structure for a dataset (subjects/sessions/scans).
        
        Args:
            dataset_id: Platform-specific dataset identifier
            
        Returns:
            Dictionary with structure:
                {
                    'subjects': [
                        {
                            'subject_id': 'sub-001',
                            'sessions': [
                                {
                                    'session_id': 'ses-01',
                                    'scans': [
                                        {
                                            'file_path': 'sub-001/ses-01/anat/sub-001_ses-01_T1w.nii.gz',
                                            'modality': 'anat',
                                            'suffix': 'T1w',
                                            'size_bytes': 12345678
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                    'total_subjects': 10,
                    'total_scans': 50
                }
        """
        pass
    
    @abstractmethod
    def download_file(self, 
                     file_id: str,
                     target_path: str,
                     progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """
        Download a specific file from the platform.
        
        Args:
            file_id: Platform-specific file identifier (path, package ID, etc.)
            target_path: Local path where file should be saved
            progress_callback: Optional callback(progress_pct, message)
            
        Returns:
            bool: True if download successful
        """
        pass
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """
        Get metadata for a specific file.
        
        Args:
            file_id: Platform-specific file identifier
            
        Returns:
            Dictionary with file metadata:
                {
                    'size_bytes': 12345678,
                    'modified_date': '2024-01-01',
                    'checksum': 'abc123',
                    'format': 'nii.gz'
                }
        """
        return None
    
    def supports_upload(self) -> bool:
        """
        Check if platform supports uploading data.
        
        Returns:
            bool: True if uploads supported (e.g., Pennsieve, XNAT)
        """
        return False
    
    def get_bids_compliance(self) -> str:
        """
        Get BIDS compliance level for this platform.
        
        Returns:
            str: 'full', 'partial', or 'none'
                - 'full': Platform enforces BIDS (OpenNeuro)
                - 'partial': Some datasets are BIDS (DANDI, HCP)
                - 'none': Custom format only (XNAT DICOM)
        """
        return 'partial'
    
    def list_subjects(self, dataset_id: str) -> List[str]:
        """
        Get list of subject IDs for a dataset (convenience method).
        
        Args:
            dataset_id: Dataset identifier
            
        Returns:
            List of subject IDs
        """
        structure = self.get_dataset_structure(dataset_id)
        return [s['subject_id'] for s in structure.get('subjects', [])]
    
    def search_datasets(self, query: str) -> List[Dict]:
        """
        Search for datasets matching query.
        
        Args:
            query: Search term (name, description, tags)
            
        Returns:
            List of matching datasets
        """
        all_datasets = self.get_datasets()
        query_lower = query.lower()
        
        return [
            d for d in all_datasets
            if query_lower in d.get('name', '').lower()
            or query_lower in d.get('description', '').lower()
        ]
    
    def get_platform_info(self) -> Dict:
        """
        Get information about this platform.
        
        Returns:
            Dictionary with platform details:
                {
                    'name': 'XNAT',
                    'type': 'institutional',
                    'bids_support': 'partial',
                    'upload_support': True,
                    'requires_approval': False
                }
        """
        return {
            'name': self.platform_name.upper(),
            'type': 'unknown',
            'bids_support': self.get_bids_compliance(),
            'upload_support': self.supports_upload(),
            'requires_approval': False
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} platform='{self.platform_name}'>"
