"""
OpenNeuro Integration for Data Explorer.

Provides interface to download public BIDS datasets from OpenNeuro.
OpenNeuro is a free and open platform for sharing neuroimaging data.
"""

import openneuro as on
from pathlib import Path
from typing import Optional, Dict, List, Callable
import shutil


class OpenNeuroAgent:
    """Interface to OpenNeuro for downloading public BIDS datasets."""
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize OpenNeuro agent.
        
        Args:
            api_token: Optional API token for private datasets
        """
        self.api_token = api_token
        self._verify_installation()
    
    def _verify_installation(self):
        """Verify openneuro-py is installed."""
        try:
            import openneuro
        except ImportError:
            raise RuntimeError(
                "OpenNeuro library not found. Install with: pip install openneuro-py"
            )
    
    def download_dataset(self,
                        dataset_id: str,
                        target_dir: str,
                        include_patterns: Optional[List[str]] = None,
                        exclude_patterns: Optional[List[str]] = None,
                        progress_callback: Callable[[str], None] = None) -> bool:
        """
        Download entire dataset or specific files from OpenNeuro.
        
        Args:
            dataset_id: OpenNeuro dataset ID (e.g., 'ds000246')
            target_dir: Local directory for download
            include_patterns: Optional list of patterns to include (e.g., ['sub-001/**'])
            exclude_patterns: Optional list of patterns to exclude (e.g., ['**/sourcedata/**'])
            progress_callback: Optional callback(message) for updates
            
        Returns:
            bool: True if download successful
        """
        try:
            if progress_callback:
                progress_callback(f"Starting download: {dataset_id}")
                if include_patterns:
                    progress_callback(f"Including: {', '.join(include_patterns)}")
                if exclude_patterns:
                    progress_callback(f"Excluding: {', '.join(exclude_patterns)}")
            
            # Build download arguments
            kwargs = {
                'dataset': dataset_id,
                'target_dir': target_dir
            }
            
            if include_patterns:
                kwargs['include'] = include_patterns
            
            if exclude_patterns:
                kwargs['exclude'] = exclude_patterns
            
            # Download (openneuro-py handles progress internally)
            if progress_callback:
                progress_callback("Downloading files...")
            
            on.download(**kwargs)
            
            if progress_callback:
                progress_callback("✓ Download complete")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"✗ Download failed: {e}")
            print(f"OpenNeuro download error: {e}")
            return False
    
    def download_subject(self,
                        dataset_id: str,
                        subject_id: str,
                        target_dir: str,
                        sessions: Optional[List[str]] = None,
                        progress_callback: Callable[[str], None] = None) -> bool:
        """
        Download a specific subject from OpenNeuro dataset.
        
        Args:
            dataset_id: OpenNeuro dataset ID
            subject_id: Subject ID (with or without 'sub-' prefix)
            target_dir: Local directory for download
            sessions: Optional list of sessions (e.g., ['ses-01', 'ses-02'])
            progress_callback: Optional callback for updates
            
        Returns:
            bool: True if download successful
        """
        # Ensure subject_id has 'sub-' prefix
        if not subject_id.startswith('sub-'):
            subject_id = f'sub-{subject_id}'
        
        # Build include pattern
        if sessions:
            # Download specific sessions
            include_patterns = []
            for session in sessions:
                if not session.startswith('ses-'):
                    session = f'ses-{session}'
                include_patterns.append(f'{subject_id}/{session}/**')
        else:
            # Download all sessions for subject
            include_patterns = [f'{subject_id}/**']
        
        return self.download_dataset(
            dataset_id=dataset_id,
            target_dir=target_dir,
            include_patterns=include_patterns,
            progress_callback=progress_callback
        )
    
    def download_subjects_batch(self,
                               dataset_id: str,
                               subject_ids: List[str],
                               target_dir: str,
                               sessions: Optional[List[str]] = None,
                               progress_callback: Callable[[int, int, str], None] = None) -> Dict:
        """
        Download multiple subjects with progress tracking.
        
        Args:
            dataset_id: OpenNeuro dataset ID
            subject_ids: List of subject IDs
            target_dir: Local directory for download
            sessions: Optional list of sessions to download
            progress_callback: Optional callback(current, total, subject_id)
            
        Returns:
            dict: {'successful': int, 'failed': int, 'errors': list}
        """
        results = {'successful': 0, 'failed': 0, 'errors': []}
        total = len(subject_ids)
        
        for i, subject_id in enumerate(subject_ids):
            if progress_callback:
                progress_callback(i + 1, total, subject_id)
            
            def subject_progress(msg):
                if progress_callback:
                    progress_callback(i + 1, total, f"{subject_id}: {msg}")
            
            success = self.download_subject(
                dataset_id=dataset_id,
                subject_id=subject_id,
                target_dir=target_dir,
                sessions=sessions,
                progress_callback=subject_progress
            )
            
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(subject_id)
        
        return results
    
    def download_by_modality(self,
                            dataset_id: str,
                            target_dir: str,
                            modalities: List[str],
                            progress_callback: Callable[[str], None] = None) -> bool:
        """
        Download only specific modalities (e.g., anat, func, dwi).
        
        Args:
            dataset_id: OpenNeuro dataset ID
            target_dir: Local directory for download
            modalities: List of modalities (e.g., ['anat', 'func'])
            progress_callback: Optional callback for updates
            
        Returns:
            bool: True if download successful
        """
        # Build include patterns for modalities
        include_patterns = []
        for modality in modalities:
            include_patterns.append(f'**/{modality}/**')
        
        return self.download_dataset(
            dataset_id=dataset_id,
            target_dir=target_dir,
            include_patterns=include_patterns,
            progress_callback=progress_callback
        )
    
    def get_available_space(self, path: str = '.') -> int:
        """
        Check available disk space.
        
        Args:
            path: Path to check
            
        Returns:
            int: Available space in bytes
        """
        try:
            usage = shutil.disk_usage(path)
            return usage.free
        except Exception:
            return 0
    
    def get_remote_dataset_structure(self, dataset_id: str) -> Dict:
        """
        Get dataset structure from OpenNeuro without downloading.
        Uses OpenNeuro GraphQL API to browse metadata.
        
        Args:
            dataset_id: OpenNeuro dataset ID (e.g., 'ds000246')
            
        Returns:
            dict: {
                'subjects': [list of subject IDs],
                'sessions': {subject_id: [sessions]},
                'metadata': {participants.tsv data}
            }
        """
        try:
            import requests
            
            # OpenNeuro GraphQL API
            graphql_url = 'https://openneuro.org/crn/graphql'
            
            # Query to get dataset file tree
            query = """
            query($datasetId: ID!) {
                dataset(id: $datasetId) {
                    id
                    draft {
                        files {
                            filename
                            size
                        }
                    }
                }
            }
            """
            
            response = requests.post(
                graphql_url,
                json={'query': query, 'variables': {'datasetId': dataset_id}},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Failed to query OpenNeuro: {response.status_code}")
                return {'subjects': [], 'sessions': {}, 'metadata': None}
            
            data = response.json()
            
            if 'errors' in data:
                print(f"GraphQL errors: {data['errors']}")
                return {'subjects': [], 'sessions': {}, 'metadata': None}
            
            # Parse file tree for BIDS structure
            structure = {
                'subjects': set(),
                'sessions': {},
                'metadata': None
            }
            
            files = data.get('data', {}).get('dataset', {}).get('draft', {}).get('files', [])
            
            for file_info in files:
                filename = file_info.get('filename', '')
                
                # Look for subject directories
                if filename.startswith('sub-'):
                    parts = filename.split('/')
                    
                    if len(parts) > 0 and parts[0].startswith('sub-'):
                        subject_id = parts[0].replace('sub-', '')
                        structure['subjects'].add(subject_id)
                        
                        # Look for sessions
                        if len(parts) > 1 and parts[1].startswith('ses-'):
                            session = parts[1].replace('ses-', '')
                            if subject_id not in structure['sessions']:
                                structure['sessions'][subject_id] = set()
                            structure['sessions'][subject_id].add(session)
            
            # Convert sets to lists
            structure['subjects'] = sorted(list(structure['subjects']))
            structure['sessions'] = {k: sorted(list(v)) for k, v in structure['sessions'].items()}
            
            return structure
            
        except Exception as e:
            print(f"Error getting OpenNeuro structure: {e}")
            return {'subjects': [], 'sessions': {}, 'metadata': None}
    
    def download_participants_tsv(self, dataset_id: str, target_dir: str) -> bool:
        """
        Download only participants.tsv to get metadata.
        
        Args:
            dataset_id: OpenNeuro dataset ID
            target_dir: Local directory for download
            
        Returns:
            bool: True if successful
        """
        return self.download_dataset(
            dataset_id=dataset_id,
            target_dir=target_dir,
            include_patterns=['participants.tsv', 'participants.json']
        )
    
    def validate_dataset_id(self, dataset_id: str) -> bool:
        """
        Check if dataset ID is valid format.
        
        Args:
            dataset_id: Dataset ID to validate
            
        Returns:
            bool: True if valid format (dsXXXXXX)
        """
        import re
        pattern = r'^ds\d{6}$'
        return bool(re.match(pattern, dataset_id))


# Helper function for checking connectivity
def check_openneuro_connection() -> bool:
    """
    Check if OpenNeuro is accessible.
    
    Returns:
        bool: True if can connect to OpenNeuro
    """
    try:
        import requests
        response = requests.get('https://openneuro.org/api', timeout=5)
        return response.status_code == 200
    except Exception:
        return False
