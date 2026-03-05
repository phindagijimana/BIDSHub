"""
LORIS Integration for BIDSHub.

Provides interface to LORIS (Longitudinal Online Research and Imaging System) instances.
LORIS is used by multiple institutions for managing longitudinal neuroimaging studies.
"""

from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging
import requests

from src.base_agent import BasePlatformAgent


logger = logging.getLogger(__name__)


class LORISAgent(BasePlatformAgent):
    """
    Interface to LORIS neuroimaging database.
    
    LORIS is self-hosted by institutions, so each instance has its own URL.
    Supports BIDS export and has good EEG/iEEG support.
    """
    
    # Known LORIS instances (for documentation/examples)
    KNOWN_INSTANCES = {
        'demo': 'https://demo.loris.ca',
        'mcgill': 'https://loris.mcin.ca',  # McGill Center for Integrative Neuroscience
    }
    
    def __init__(self, instance_url: str, username: str, password: str):
        """
        Initialize LORIS agent.
        
        Args:
            instance_url: LORIS instance URL (e.g., 'https://demo.loris.ca')
            username: LORIS username
            password: LORIS password
        """
        super().__init__(credentials={
            'instance_url': instance_url,
            'username': username,
            'password': password
        })
        self.instance_url = instance_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = None
        self.token = None
    
    def verify_connection(self) -> bool:
        """
        Verify LORIS credentials.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Authenticate with LORIS
            response = requests.post(
                f'{self.instance_url}/login',
                json={'username': self.username, 'password': self.password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                
                # Create session with auth header
                self.session = requests.Session()
                self.session.headers.update({
                    'Authorization': f'Bearer {self.token}'
                })
                
                logger.info(f"Connected to LORIS: {self.instance_url}")
                return True
            else:
                logger.error(f"LORIS login failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"LORIS connection failed: {e}")
            return False
    
    def get_datasets(self) -> List[Dict]:
        """
        List available LORIS projects.
        
        Returns:
            List of project dictionaries
        """
        if not self.session:
            if not self.verify_connection():
                return []
        
        projects = []
        
        try:
            response = self.session.get(
                f'{self.instance_url}/api/v0/projects',
                timeout=30
            )
            
            if response.status_code == 200:
                project_data = response.json()
                
                for proj in project_data.get('projects', []):
                    projects.append({
                        'id': proj.get('ProjectID'),
                        'name': proj.get('Name', f"Project {proj.get('ProjectID')}"),
                        'description': proj.get('Description', ''),
                        'recruitment_target': proj.get('recruitmentTarget', 'Unknown')
                    })
            
        except Exception as e:
            logger.error(f"Error listing LORIS projects: {e}")
        
        return projects
    
    def get_dataset_structure(self, project_id: str) -> Dict:
        """
        Get structure for a LORIS project.
        
        Args:
            project_id: LORIS project ID
            
        Returns:
            Dictionary with subjects and sessions
        """
        if not self.session:
            if not self.verify_connection():
                return {'subjects': [], 'total_scans': 0}
        
        try:
            # Get candidates (subjects) for project
            response = self.session.get(
                f'{self.instance_url}/api/v0/projects/{project_id}/candidates',
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get LORIS candidates: {response.status_code}")
                return {'subjects': [], 'total_scans': 0}
            
            candidates_data = response.json()
            
            structure = {
                'subjects': [],
                'total_scans': 0
            }
            
            for candidate in candidates_data.get('candidates', []):
                candid = candidate.get('CandID')
                pscid = candidate.get('PSCID')  # Project-specific ID
                
                # Get sessions for this candidate
                sessions = self._get_candidate_sessions(project_id, candid)
                
                if sessions:
                    structure['subjects'].append({
                        'subject_id': f"sub-{pscid}" if pscid else f"sub-{candid}",
                        'loris_candid': candid,
                        'loris_pscid': pscid,
                        'sessions': sessions
                    })
                    
                    # Count scans
                    for session in sessions:
                        structure['total_scans'] += len(session.get('scans', []))
            
            return structure
            
        except Exception as e:
            logger.error(f"Error getting LORIS structure: {e}")
            return {'subjects': [], 'total_scans': 0}
    
    def _get_candidate_sessions(self, project_id: str, candid: str) -> List[Dict]:
        """Get sessions for a LORIS candidate."""
        try:
            response = self.session.get(
                f'{self.instance_url}/api/v0/candidates/{candid}/visits',
                timeout=30
            )
            
            if response.status_code == 200:
                visits_data = response.json()
                
                sessions = []
                for visit in visits_data.get('visits', []):
                    session_label = visit.get('Visit_label')
                    
                    # Get imaging scans for this session
                    scans = self._get_session_scans(candid, session_label)
                    
                    if scans:
                        sessions.append({
                            'session_id': f"ses-{session_label}",
                            'loris_visit': session_label,
                            'date': visit.get('Date_visit'),
                            'scans': scans
                        })
                
                return sessions
        
        except Exception as e:
            logger.error(f"Error getting LORIS sessions: {e}")
        
        return []
    
    def _get_session_scans(self, candid: str, visit_label: str) -> List[Dict]:
        """Get imaging scans for a LORIS session."""
        try:
            response = self.session.get(
                f'{self.instance_url}/api/v0/candidates/{candid}/{visit_label}/images',
                timeout=30
            )
            
            if response.status_code == 200:
                images_data = response.json()
                
                scans = []
                for image in images_data.get('images', []):
                    scans.append({
                        'file_id': image.get('FileID'),
                        'filename': image.get('File'),
                        'scan_type': image.get('ScanType'),
                        'modality': self._infer_modality(image.get('ScanType', '')),
                        'acquisition_date': image.get('AcquisitionDate')
                    })
                
                return scans
        
        except Exception as e:
            logger.error(f"Error getting LORIS scans: {e}")
        
        return []
    
    def download_file(self,
                     file_id: str,
                     target_path: str,
                     progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """
        Download file from LORIS.
        
        Args:
            file_id: LORIS file ID
            target_path: Local target path
            progress_callback: Optional progress callback
            
        Returns:
            bool: True if download successful
        """
        if not self.session:
            if not self.verify_connection():
                return False
        
        try:
            if progress_callback:
                progress_callback(0, f"Downloading from LORIS...")
            
            # Download file
            response = self.session.get(
                f'{self.instance_url}/api/v0/files/{file_id}',
                stream=True,
                timeout=300
            )
            
            if response.status_code == 200:
                # Create parent directory
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                
                # Write file
                with open(target_path, 'wb') as f:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and total_size > 0:
                                pct = int((downloaded / total_size) * 100)
                                progress_callback(pct, f"Downloading... {pct}%")
                
                if progress_callback:
                    progress_callback(100, "Download complete")
                
                logger.info(f"Downloaded: {file_id} -> {target_path}")
                return True
            else:
                logger.error(f"Download failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error downloading from LORIS: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return False
    
    def _infer_modality(self, scan_type: str) -> str:
        """Map LORIS scan type to BIDS modality."""
        scan_type_lower = scan_type.lower()
        
        if any(t in scan_type_lower for t in ['t1', 't2', 'flair', 'pd']):
            return 'anat'
        elif any(t in scan_type_lower for t in ['fmri', 'bold', 'rest']):
            return 'func'
        elif any(t in scan_type_lower for t in ['dwi', 'dti', 'diffusion']):
            return 'dwi'
        elif 'eeg' in scan_type_lower or 'ieeg' in scan_type_lower:
            return 'eeg'
        else:
            return 'unknown'
    
    def get_bids_compliance(self) -> str:
        """LORIS has good BIDS export support."""
        return 'good'
    
    def supports_upload(self) -> bool:
        """LORIS supports data upload (with permissions)."""
        return True
    
    def get_platform_info(self) -> Dict:
        """Get LORIS platform information."""
        return {
            'name': 'LORIS',
            'full_name': 'Longitudinal Online Research and Imaging System',
            'type': 'institutional',
            'bids_support': 'good',
            'upload_support': True,
            'requires_approval': True,  # Institution-specific access
            'data_types': ['MRI', 'EEG', 'iEEG', 'behavioral', 'genetic'],
            'primary_focus': 'longitudinal multi-modal studies',
            'note': 'Each institution hosts its own LORIS instance'
        }


def check_loris_connection(instance_url: str, username: str, password: str) -> bool:
    """
    Check if LORIS instance is accessible (convenience function).
    
    Args:
        instance_url: LORIS instance URL
        username: Username
        password: Password
        
    Returns:
        bool: True if accessible
    """
    try:
        agent = LORISAgent(instance_url, username, password)
        return agent.verify_connection()
    except:
        return False
