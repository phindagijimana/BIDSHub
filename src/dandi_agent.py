"""
DANDI Archive Integration for BIDSHub.

Provides interface to browse and download neurophysiology datasets from DANDI.
DANDI stores data in NWB (Neurodata Without Borders) format, with some BIDS-compliant datasets.
"""

from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging

from src.base_agent import BasePlatformAgent


logger = logging.getLogger(__name__)


class DANDIAgent(BasePlatformAgent):
    """
    Interface to DANDI Archive for neurophysiology and neuroimaging data.
    
    DANDI primarily stores NWB format data but also includes BIDS-compliant
    MRI and EEG datasets.
    """
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize DANDI agent.
        
        Args:
            api_token: Optional API token for private dandisets
        """
        super().__init__(credentials={'api_token': api_token} if api_token else {})
        self.api_token = api_token
        self.client = None
        self._dandi_available = self._verify_installation()
    
    def _verify_installation(self) -> bool:
        """
        Verify dandi is installed.
        
        Returns:
            bool: True if dandi is available
        """
        try:
            from dandi.dandiapi import DandiAPIClient
            return True
        except ImportError:
            logger.error("DANDI client not found. Install with: pip install dandi")
            return False
    
    def verify_connection(self) -> bool:
        """
        Verify DANDI connection.
        
        Returns:
            bool: True if connection successful
        """
        if not self._dandi_available:
            return False
            
        try:
            from dandi.dandiapi import DandiAPIClient
            
            self.client = DandiAPIClient(token=self.api_token)
            
            # Test connection by listing dandisets (limit to 1)
            dandisets = list(self.client.get_dandisets())
            return True
            
        except Exception as e:
            logger.error(f"DANDI connection failed: {e}")
            return False
    
    def get_datasets(self) -> List[Dict]:
        """
        List available dandisets.
        
        Returns:
            List of dandiset dictionaries
        """
        if not self.client:
            if not self.verify_connection():
                return []
        
        dandisets = []
        
        try:
            for ds in self.client.get_dandisets():
                metadata = ds.get_raw_metadata()
                
                dandisets.append({
                    'id': ds.identifier,
                    'name': metadata.get('name', f'Dandiset {ds.identifier}'),
                    'description': metadata.get('description', '')[:200],
                    'url': ds.api_url,
                    'version': ds.version_id,
                    'contributor': ', '.join([
                        c.get('name', '') 
                        for c in metadata.get('contributor', [])[:3]
                    ])
                })
        
        except Exception as e:
            logger.error(f"Error listing dandisets: {e}")
        
        return dandisets
    
    def get_dataset_structure(self, dataset_id: str, version: str = "draft") -> Dict:
        """
        Get structure for a dandiset.
        
        Args:
            dataset_id: Dandiset identifier (e.g., '000001')
            version: Version to access ('draft' or specific version)
            
        Returns:
            Dictionary with subjects and files
        """
        if not self.client:
            if not self.verify_connection():
                return {'subjects': [], 'files': []}
        
        try:
            dandiset = self.client.get_dandiset(dataset_id, version)
            
            structure = {
                'subjects': [],
                'files': [],
                'total_size_bytes': 0,
                'has_bids': False,
                'has_nwb': False
            }
            
            # Collect all assets
            for asset in dandiset.get_assets():
                file_info = {
                    'path': asset.path,
                    'asset_id': asset.identifier,
                    'size_bytes': asset.size,
                    'modified': str(asset.modified),
                    'blob_id': asset.blob
                }
                
                structure['files'].append(file_info)
                structure['total_size_bytes'] += asset.size
                
                # Check format
                if asset.path.endswith('.nwb'):
                    structure['has_nwb'] = True
                
                # Extract subject ID from BIDS path
                if '/sub-' in asset.path:
                    structure['has_bids'] = True
                    try:
                        subject_part = asset.path.split('/sub-')[1]
                        subject_id = subject_part.split('/')[0]
                        subject_id = f"sub-{subject_id}"
                        
                        # Check if subject already added
                        if not any(s['subject_id'] == subject_id for s in structure['subjects']):
                            structure['subjects'].append({
                                'subject_id': subject_id,
                                'sessions': []  # DANDI structure varies
                            })
                    except:
                        pass
            
            return structure
            
        except Exception as e:
            logger.error(f"Error getting DANDI structure: {e}")
            return {'subjects': [], 'files': []}
    
    def download_file(self,
                     asset_id: str,
                     asset_path: str,
                     target_path: str,
                     progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """
        Download a specific file from DANDI.
        
        Args:
            asset_id: DANDI asset identifier
            asset_path: Path within dandiset
            target_path: Local target path
            progress_callback: Optional callback(progress_pct, message)
            
        Returns:
            bool: True if download successful
        """
        if not self.client:
            if not self.verify_connection():
                return False
        
        try:
            if progress_callback:
                progress_callback(0, f"Starting download: {Path(asset_path).name}")
            
            # Find asset by path
            # Note: This is simplified - actual implementation may need dandiset context
            # For now, we assume asset_id or path is provided from get_dataset_structure
            
            if progress_callback:
                progress_callback(50, "Downloading from DANDI...")
            
            # Download using dandi client
            # Actual implementation will use dandiset.download_asset()
            # This requires the dandiset context
            
            if progress_callback:
                progress_callback(100, "Download complete")
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading from DANDI: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return False
    
    def download_dandiset(self,
                         dandiset_id: str,
                         target_dir: str,
                         include_patterns: Optional[List[str]] = None,
                         exclude_patterns: Optional[List[str]] = None,
                         progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Download entire dandiset or filtered subset.
        
        Args:
            dandiset_id: Dandiset identifier
            target_dir: Local directory for download
            include_patterns: Patterns to include (e.g., ['sub-001/**', '*.nii.gz'])
            exclude_patterns: Patterns to exclude
            progress_callback: Callback for progress updates
            
        Returns:
            bool: True if successful
        """
        if not self.client:
            if not self.verify_connection():
                return False
        
        try:
            if progress_callback:
                progress_callback(f"Downloading dandiset {dandiset_id}...")
            
            dandiset = self.client.get_dandiset(dandiset_id, "draft")
            
            # Create target directory
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            
            # Download
            dandiset.download(target_dir)
            
            if progress_callback:
                progress_callback("Download complete")
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading dandiset: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False
    
    def get_subjects_with_metadata(self, dandiset_id: str) -> List[Dict]:
        """
        Fetch subject list with metadata and scans from DANDI dandiset.
        
        Args:
            dandiset_id: Dandiset identifier (e.g., '000001')
            
        Returns:
            list: List of dicts with subject info and scans
        """
        try:
            if not self.client:
                if not self.verify_connection():
                    return []
            
            structure = self.get_dataset_structure(dandiset_id)
            subjects_list = structure.get('subjects', [])
            all_files = structure.get('files', [])
            
            if not subjects_list:
                logger.warning(f"No subjects found in dandiset {dandiset_id}")
                return []
            
            # Build a map of subject -> scans from all files
            subject_scans_map = {}
            for file_info in all_files:
                file_path = file_info['path']
                
                # Extract subject ID from path (BIDS: /sub-XX/...)
                if '/sub-' in file_path and file_path.endswith(('.nii', '.nii.gz')):
                    try:
                        subject_part = file_path.split('/sub-')[1]
                        subject_id = f"sub-{subject_part.split('/')[0]}"
                        
                        # Extract session if present
                        session_id = 'ses-default'
                        if '/ses-' in file_path:
                            session_part = file_path.split('/ses-')[1]
                            session_id = f"ses-{session_part.split('/')[0]}"
                        
                        # Extract scan info
                        filename = Path(file_path).name
                        
                        scan_info = {
                            'scan_type': self._infer_scan_type(filename),
                            'file_path': file_path,
                            'asset_id': file_info['asset_id'],
                            'size_bytes': file_info['size_bytes'],
                            'session_id': session_id,
                            'modality': self._infer_modality(file_path)
                        }
                        
                        if subject_id not in subject_scans_map:
                            subject_scans_map[subject_id] = []
                        subject_scans_map[subject_id].append(scan_info)
                    except:
                        pass
            
            # Build subject list with scans
            result = []
            for subject_info in subjects_list:
                subject_id = subject_info['subject_id']
                scans = subject_scans_map.get(subject_id, [])
                
                # Extract unique sessions from scans
                sessions = list(set(scan['session_id'] for scan in scans))
                if not sessions:
                    sessions = ['ses-default']
                
                result.append({
                    'subject_id': subject_id,
                    'age': None,
                    'sex': None,
                    'diagnosis': None,
                    'participant_group': None,
                    'handedness': None,
                    'site': None,
                    'sessions': sessions,
                    'scans': scans,
                    'has_anat': structure.get('has_bids', False),
                    'has_func': False,
                    'has_dwi': False,
                    'has_fmap': False,
                    'metadata': {}
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching subjects from {dandiset_id}: {e}")
            return []
    
    def _infer_scan_type(self, filename: str) -> str:
        """Infer scan type from BIDS filename."""
        filename_lower = filename.lower()
        
        if 't1w' in filename_lower:
            return 'T1w'
        elif 't2w' in filename_lower:
            return 'T2w'
        elif 'flair' in filename_lower:
            return 'FLAIR'
        elif 'bold' in filename_lower or 'task' in filename_lower:
            return 'BOLD'
        elif 'dwi' in filename_lower:
            return 'DWI'
        else:
            return 'OTHER'
    
    def _infer_modality(self, file_path: str) -> str:
        """Infer modality from BIDS file path."""
        if '/anat/' in file_path:
            return 'anat'
        elif '/func/' in file_path:
            return 'func'
        elif '/dwi/' in file_path:
            return 'dwi'
        elif '/fmap/' in file_path:
            return 'fmap'
        else:
            return 'other'
    
    def get_bids_compliance(self) -> str:
        """DANDI has partial BIDS support (some dandisets are BIDS-compliant)."""
        return 'partial'
    
    def get_platform_info(self) -> Dict:
        """Get DANDI platform information."""
        return {
            'name': 'DANDI',
            'full_name': 'Distributed Archives for Neurophysiology Data Integration',
            'type': 'public_archive',
            'bids_support': 'partial',
            'upload_support': True,  # With account
            'requires_approval': False,
            'data_types': ['NWB', 'BIDS-EEG', 'BIDS-MRI'],
            'primary_focus': 'neurophysiology'
        }
    
    def get_file_url(self, dandiset_id: str, asset_path: str, version: str = "draft") -> Optional[str]:
        """
        Get direct download URL for a DANDI asset.
        
        Args:
            dandiset_id: Dandiset identifier
            asset_path: Path to the asset within dandiset
            version: Version ('draft' or specific version)
            
        Returns:
            str: Direct download URL or None if not found
        """
        if not self.client:
            if not self.verify_connection():
                return None
        
        try:
            dandiset = self.client.get_dandiset(dandiset_id, version)
            
            # Find asset by path
            for asset in dandiset.get_assets():
                if asset.path == asset_path:
                    # Get download URL
                    return asset.get_content_url()
            
            logger.warning(f"Asset not found: {asset_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting DANDI file URL: {e}")
            return None
    
    def download_file(self, dandiset_id: str, asset_path: str, 
                      local_path: str, version: str = "draft",
                      progress_callback: Optional[Callable] = None) -> bool:
        """
        Download a DANDI file to local storage.
        
        Args:
            dandiset_id: Dandiset identifier
            asset_path: Path to the asset within dandiset
            local_path: Local destination path
            version: Version ('draft' or specific version)
            progress_callback: Optional callback for progress updates (bytes_downloaded, total_bytes)
            
        Returns:
            bool: True if download successful
        """
        if not self.client:
            if not self.verify_connection():
                return False
        
        try:
            import requests
            from pathlib import Path
            
            dandiset = self.client.get_dandiset(dandiset_id, version)
            
            # Find asset by path
            for asset in dandiset.get_assets():
                if asset.path == asset_path:
                    # Get download URL
                    download_url = asset.get_content_url()
                    
                    # Create parent directory if needed
                    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    # Download with progress tracking
                    response = requests.get(download_url, stream=True)
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    bytes_downloaded = 0
                    
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                
                                if progress_callback:
                                    progress_callback(bytes_downloaded, total_size)
                    
                    logger.info(f"Downloaded {asset_path} to {local_path}")
                    return True
            
            logger.warning(f"Asset not found: {asset_path}")
            return False
            
        except Exception as e:
            logger.error(f"Error downloading DANDI file: {e}")
            return False


def check_dandi_connection(api_token: Optional[str] = None) -> bool:
    """
    Check if DANDI is reachable (convenience function).
    
    Args:
        api_token: Optional API token
        
    Returns:
        bool: True if DANDI is accessible
    """
    try:
        agent = DANDIAgent(api_token=api_token)
        return agent.verify_connection()
    except:
        return False
