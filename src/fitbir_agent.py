"""
FITBIR Integration for BIDSHub.

Provides interface to FITBIR (Federal Interagency Traumatic Brain Injury Research)
informatics system. FITBIR requires NIH credentials and institutional approval.
"""

from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging
import requests

from src.base_agent import BasePlatformAgent


logger = logging.getLogger(__name__)


class FITBIRAgent(BasePlatformAgent):
    """
    Interface to FITBIR TBI research data platform.
    
    FITBIR requires NIH Researcher Auth Service (RAS) credentials and
    institutional approval for data access.
    
    NOTE: API documentation is limited. This implementation provides
    a foundation that may need adjustment based on actual API behavior.
    """
    
    FITBIR_BASE_URL = 'https://fitbir.nih.gov'
    
    def __init__(self, username: str, password: str):
        """
        Initialize FITBIR agent.
        
        Args:
            username: NIH RAS username
            password: NIH RAS password
        """
        super().__init__(credentials={
            'username': username,
            'password': password
        })
        self.username = username
        self.password = password
        self.session = None
        self.token = None
    
    def verify_connection(self) -> bool:
        """
        Verify FITBIR credentials.
        
        NOTE: Authentication endpoint may differ from implementation.
        This is based on common NIH authentication patterns.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Attempt authentication
            # NOTE: Actual endpoint may be different - this is provisional
            response = requests.post(
                f'{self.FITBIR_BASE_URL}/api/v1/auth/login',
                json={'username': self.username, 'password': self.password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token') or data.get('token')
                
                if self.token:
                    self.session = requests.Session()
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.token}'
                    })
                    
                    logger.info("Connected to FITBIR")
                    return True
            
            # If 200 but no token, or non-200 response
            logger.warning(f"FITBIR authentication unclear: {response.status_code}")
            
            # For now, return False but note that implementation may need adjustment
            return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"FITBIR connection failed: {e}")
            return False
    
    def get_datasets(self) -> List[Dict]:
        """
        List available FITBIR studies.
        
        Returns:
            List of study dictionaries
            
        NOTE: API endpoint provisional - may need adjustment
        """
        if not self.session:
            if not self.verify_connection():
                return []
        
        studies = []
        
        try:
            # Attempt to list studies
            response = self.session.get(
                f'{self.FITBIR_BASE_URL}/api/v1/studies',
                timeout=30
            )
            
            if response.status_code == 200:
                studies_data = response.json()
                
                for study in studies_data.get('studies', []):
                    studies.append({
                        'id': study.get('study_id'),
                        'name': study.get('title', 'Unknown Study'),
                        'description': study.get('description', ''),
                        'pi': study.get('principal_investigator', ''),
                        'focus': 'TBI'
                    })
            else:
                logger.warning(f"FITBIR list studies returned: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error listing FITBIR studies: {e}")
        
        return studies
    
    def get_dataset_structure(self, study_id: str) -> Dict:
        """
        Get structure for a FITBIR study.
        
        Args:
            study_id: FITBIR study ID
            
        Returns:
            Dictionary with subjects and available data
            
        NOTE: Implementation provisional based on limited API docs
        """
        if not self.session:
            if not self.verify_connection():
                return {'subjects': [], 'total_scans': 0}
        
        try:
            # Get subjects in study
            response = self.session.get(
                f'{self.FITBIR_BASE_URL}/api/v1/studies/{study_id}/subjects',
                timeout=30
            )
            
            if response.status_code == 200:
                subjects_data = response.json()
                
                structure = {
                    'subjects': [],
                    'total_scans': 0
                }
                
                for subj in subjects_data.get('subjects', []):
                    subject_id = subj.get('guid', subj.get('subject_id'))
                    
                    # Get imaging data for subject
                    imaging = self._get_subject_imaging(study_id, subject_id)
                    
                    if imaging:
                        structure['subjects'].append({
                            'subject_id': f"sub-{subject_id}",
                            'fitbir_guid': subject_id,
                            'scans': imaging
                        })
                        structure['total_scans'] += len(imaging)
                
                return structure
            else:
                logger.warning(f"FITBIR study structure returned: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error getting FITBIR structure: {e}")
        
        return {'subjects': [], 'total_scans': 0}
    
    def _get_subject_imaging(self, study_id: str, subject_id: str) -> List[Dict]:
        """Get imaging data for a FITBIR subject."""
        try:
            response = self.session.get(
                f'{self.FITBIR_BASE_URL}/api/v1/studies/{study_id}/subjects/{subject_id}/imaging',
                timeout=30
            )
            
            if response.status_code == 200:
                imaging_data = response.json()
                
                scans = []
                for scan in imaging_data.get('scans', []):
                    scans.append({
                        'scan_id': scan.get('scan_id'),
                        'modality': scan.get('modality', 'unknown'),
                        'scan_type': scan.get('scan_type'),
                        'file_id': scan.get('file_id'),
                        'file_size': scan.get('file_size_bytes')
                    })
                
                return scans
        
        except Exception as e:
            logger.error(f"Error getting FITBIR imaging: {e}")
        
        return []
    
    def download_file(self,
                     file_id: str,
                     target_path: str,
                     progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """
        Download file from FITBIR.
        
        Args:
            file_id: FITBIR file identifier
            target_path: Local target path
            progress_callback: Optional progress callback
            
        Returns:
            bool: True if download successful
            
        NOTE: Implementation provisional
        """
        if not self.session:
            if not self.verify_connection():
                return False
        
        try:
            if progress_callback:
                progress_callback(0, "Downloading from FITBIR...")
            
            response = self.session.get(
                f'{self.FITBIR_BASE_URL}/api/v1/files/{file_id}/download',
                stream=True,
                timeout=300
            )
            
            if response.status_code == 200:
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                
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
                
                return True
            else:
                logger.error(f"FITBIR download failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error downloading from FITBIR: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return False
    
    def get_bids_compliance(self) -> str:
        """FITBIR BIDS compliance is unknown."""
        return 'unknown'
    
    def supports_upload(self) -> bool:
        """FITBIR supports uploads for approved researchers."""
        return True
    
    def get_platform_info(self) -> Dict:
        """Get FITBIR platform information."""
        return {
            'name': 'FITBIR',
            'full_name': 'Federal Interagency Traumatic Brain Injury Research',
            'type': 'federal_repository',
            'bids_support': 'unknown',
            'upload_support': True,
            'requires_approval': True,  # Institutional review required
            'data_types': ['MRI', 'clinical', 'imaging', 'outcomes'],
            'primary_focus': 'TBI research',
            'access_requirements': [
                'NIH RAS credentials',
                'Institutional affiliation',
                'Data use agreement',
                'Non-commercial research purpose'
            ],
            'note': 'Limited public API documentation. Implementation may require adjustment.'
        }


def check_fitbir_connection(username: str, password: str) -> bool:
    """
    Check if FITBIR is accessible (convenience function).
    
    Args:
        username: NIH username
        password: NIH password
        
    Returns:
        bool: True if accessible
    """
    try:
        agent = FITBIRAgent(username, password)
        return agent.verify_connection()
    except:
        return False
