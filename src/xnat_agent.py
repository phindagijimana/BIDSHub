"""
XNAT Integration for BIDSHub.

Provides interface to institutional XNAT archives for neuroimaging data.
XNAT is widely used for managing DICOM and NIfTI data in research institutions.
"""

from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging

from src.base_agent import BasePlatformAgent


logger = logging.getLogger(__name__)


class XNATAgent(BasePlatformAgent):
    """
    Interface to XNAT (Extensible Neuroimaging Archive Toolkit).
    
    Supports browsing projects, subjects, experiments, and scans from
    institutional XNAT servers. Can download NIfTI or DICOM data.
    """
    
    def __init__(self, server_url: str, username: str, password: str):
        """
        Initialize XNAT agent.
        
        Args:
            server_url: XNAT server URL (e.g., 'https://xnat.example.org')
            username: XNAT username
            password: XNAT password
        """
        super().__init__(credentials={
            'server_url': server_url,
            'username': username,
            'password': password
        })
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = None
        self._verify_installation()
    
    def _verify_installation(self):
        """Verify xnat library is installed."""
        try:
            import xnat
        except ImportError:
            raise RuntimeError(
                "XNAT library not found. Install with: pip install xnat"
            )
    
    def verify_connection(self) -> bool:
        """
        Verify XNAT credentials and connection.
        
        Returns:
            bool: True if connection successful
        """
        try:
            import xnat
            
            self.session = xnat.connect(
                self.server_url,
                user=self.username,
                password=self.password
            )
            
            # Test by accessing projects
            _ = list(self.session.projects)
            
            logger.info(f"Connected to XNAT: {self.server_url}")
            return True
            
        except Exception as e:
            logger.error(f"XNAT connection failed: {e}")
            if self.session:
                self.session.disconnect()
                self.session = None
            return False
    
    def get_datasets(self) -> List[Dict]:
        """
        List available XNAT projects.
        
        Returns:
            List of project dictionaries
        """
        if not self.session:
            if not self.verify_connection():
                return []
        
        projects = []
        
        try:
            for project in self.session.projects.values():
                projects.append({
                    'id': project.id,
                    'name': project.name,
                    'description': getattr(project, 'description', ''),
                    'subject_count': len(project.subjects),
                    'pi': getattr(project, 'pi_name', 'Unknown')
                })
        
        except Exception as e:
            logger.error(f"Error listing XNAT projects: {e}")
        
        return projects
    
    def get_dataset_structure(self, project_id: str) -> Dict:
        """
        Get complete structure for an XNAT project.
        
        Args:
            project_id: XNAT project ID
            
        Returns:
            Dictionary with subjects, sessions, and scans
        """
        if not self.session:
            if not self.verify_connection():
                return {'subjects': [], 'total_scans': 0}
        
        try:
            project = self.session.projects[project_id]
            
            structure = {
                'subjects': [],
                'total_scans': 0,
                'modalities': set()
            }
            
            for subject in project.subjects.values():
                subject_data = {
                    'subject_id': subject.label,
                    'sessions': []
                }
                
                for experiment in subject.experiments.values():
                    session_data = {
                        'session_id': experiment.label,
                        'date': getattr(experiment, 'date', None),
                        'scans': []
                    }
                    
                    for scan in experiment.scans.values():
                        modality = self._infer_modality(scan.type)
                        structure['modalities'].add(modality)
                        
                        scan_data = {
                            'scan_id': scan.id,
                            'type': scan.type,
                            'modality': modality,
                            'series_description': getattr(scan, 'series_description', ''),
                            'frames': getattr(scan, 'frames', 0)
                        }
                        
                        session_data['scans'].append(scan_data)
                        structure['total_scans'] += 1
                    
                    if session_data['scans']:
                        subject_data['sessions'].append(session_data)
                
                if subject_data['sessions']:
                    structure['subjects'].append(subject_data)
            
            structure['modalities'] = list(structure['modalities'])
            
            return structure
            
        except Exception as e:
            logger.error(f"Error getting XNAT structure: {e}")
            return {'subjects': [], 'total_scans': 0}
    
    def download_file(self,
                     project_id: str,
                     subject_label: str,
                     experiment_label: str,
                     scan_id: str,
                     target_path: str,
                     progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """
        Download a scan from XNAT.
        
        Args:
            project_id: XNAT project ID
            subject_label: Subject label
            experiment_label: Experiment/session label
            scan_id: Scan ID
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
                progress_callback(0, f"Locating scan {scan_id}...")
            
            # Navigate to scan
            project = self.session.projects[project_id]
            subject = project.subjects[subject_label]
            experiment = subject.experiments[experiment_label]
            scan = experiment.scans[scan_id]
            
            if progress_callback:
                progress_callback(25, "Downloading from XNAT...")
            
            # Download scan (XNAT can provide NIfTI if available)
            # Priority: NIfTI > DICOM
            target_dir = Path(target_path).parent
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Check for NIfTI resource
            nifti_available = False
            for resource in scan.resources.values():
                if 'NIFTI' in resource.label.upper():
                    resource.download_dir(str(target_dir))
                    nifti_available = True
                    break
            
            if not nifti_available:
                # Download DICOM as fallback
                if progress_callback:
                    progress_callback(50, "Downloading DICOM (conversion may be needed)...")
                
                for resource in scan.resources.values():
                    if 'DICOM' in resource.label.upper():
                        resource.download_dir(str(target_dir))
                        break
            
            if progress_callback:
                progress_callback(100, "Download complete")
            
            return True
            
        except Exception as e:
            logger.error(f"Error downloading from XNAT: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return False
    
    def _infer_modality(self, scan_type: str) -> str:
        """
        Map XNAT scan type to BIDS modality.
        
        Args:
            scan_type: XNAT scan type description
            
        Returns:
            BIDS modality (anat, func, dwi, etc.)
        """
        scan_type_lower = scan_type.lower()
        
        # Anatomical
        if any(t in scan_type_lower for t in ['t1', 't2', 'flair', 'pd', 'mprage']):
            return 'anat'
        
        # Functional
        elif any(t in scan_type_lower for t in ['fmri', 'bold', 'resting', 'task']):
            return 'func'
        
        # Diffusion
        elif any(t in scan_type_lower for t in ['dwi', 'dti', 'diffusion', 'dsi']):
            return 'dwi'
        
        # Fieldmap
        elif any(t in scan_type_lower for t in ['fieldmap', 'fmap', 'b0']):
            return 'fmap'
        
        # PET
        elif 'pet' in scan_type_lower:
            return 'pet'
        
        # ASL
        elif 'asl' in scan_type_lower:
            return 'perf'
        
        else:
            return 'unknown'
    
    def _map_to_bids_filename(self, 
                              subject_id: str,
                              session_id: str,
                              modality: str,
                              scan_type: str) -> str:
        """
        Generate BIDS-compliant filename from XNAT metadata.
        
        Args:
            subject_id: Subject identifier
            session_id: Session identifier
            modality: BIDS modality
            scan_type: XNAT scan type
            
        Returns:
            BIDS filename pattern
        """
        # Clean IDs (ensure BIDS format)
        if not subject_id.startswith('sub-'):
            subject_id = f"sub-{subject_id}"
        if not session_id.startswith('ses-'):
            session_id = f"ses-{session_id}"
        
        # Infer suffix from scan type
        scan_type_lower = scan_type.lower()
        
        if 't1' in scan_type_lower:
            suffix = 'T1w'
        elif 't2' in scan_type_lower:
            suffix = 'T2w'
        elif 'flair' in scan_type_lower:
            suffix = 'FLAIR'
        elif 'bold' in scan_type_lower:
            suffix = 'bold'
        elif 'dwi' in scan_type_lower:
            suffix = 'dwi'
        else:
            suffix = 'unknown'
        
        return f"{subject_id}_{session_id}_{suffix}.nii.gz"
    
    def get_subjects_with_metadata(self, project_id: str) -> List[Dict]:
        """
        Fetch subject list with metadata from XNAT project.
        
        Args:
            project_id: XNAT project ID
            
        Returns:
            list: List of dicts with subject info
        """
        try:
            if not self.session:
                if not self.verify_connection():
                    return []
            
            project = self.session.projects[project_id]
            result = []
            
            for subject in project.subjects.values():
                # Get demographics if available
                age = None
                sex = None
                
                # XNAT stores demographics in subject fields
                if hasattr(subject, 'demographics'):
                    age = getattr(subject.demographics, 'age', None)
                    sex = getattr(subject.demographics, 'gender', None)
                
                # Get sessions
                sessions = [exp.label for exp in subject.experiments.values()]
                
                # Determine what modalities exist
                modalities = set()
                for exp in subject.experiments.values():
                    for scan in exp.scans.values():
                        modality = self._infer_modality(scan.type)
                        modalities.add(modality)
                
                result.append({
                    'subject_id': f'sub-{subject.label}' if not subject.label.startswith('sub-') else subject.label,
                    'age': float(age) if age else None,
                    'sex': sex.upper() if sex else None,
                    'diagnosis': None,
                    'participant_group': None,
                    'handedness': None,
                    'site': project_id,
                    'sessions': [f'ses-{s}' if not s.startswith('ses-') else s for s in sessions],
                    'has_anat': 'anat' in modalities,
                    'has_func': 'func' in modalities,
                    'has_dwi': 'dwi' in modalities,
                    'has_fmap': 'fmap' in modalities,
                    'metadata': {}
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching subjects from {project_id}: {e}")
            return []
    
    def supports_upload(self) -> bool:
        """XNAT supports data upload."""
        return True
    
    def upload_file(self, local_path: str, project_id: str, subject_id: str,
                   experiment_label: str = None, scan_label: str = None,
                   progress_callback: Callable[[int, int], None] = None) -> bool:
        """
        Upload a file to XNAT project (v3.1.1+).
        
        Args:
            local_path: Local file path
            project_id: XNAT project ID
            subject_id: Subject identifier
            experiment_label: Optional experiment label (default: MR session)
            scan_label: Optional scan label
            progress_callback: Optional callback(bytes_transferred, total_bytes)
            
        Returns:
            bool: True if upload successful
        """
        try:
            import xnat
            
            if not self.session:
                self.session = xnat.connect(
                    self.server_url,
                    user=self.username,
                    password=self.password
                )
            
            local_file = Path(local_path)
            if not local_file.exists():
                logger.error(f"Local file not found: {local_path}")
                return False
            
            # Get or create project
            try:
                project = self.session.projects[project_id]
            except KeyError:
                logger.error(f"Project {project_id} not found in XNAT")
                return False
            
            # Get or create subject
            if subject_id not in project.subjects:
                project.subjects.create(label=subject_id)
            subject = project.subjects[subject_id]
            
            # Create experiment if needed
            if not experiment_label:
                experiment_label = f"{subject_id}_MR1"
            
            if experiment_label not in subject.experiments:
                subject.experiments.create(label=experiment_label, datatype='xnat:mrSessionData')
            experiment = subject.experiments[experiment_label]
            
            # Upload file as resource
            file_size = local_file.stat().st_size
            
            if progress_callback:
                progress_callback(0, file_size)
            
            # Upload to experiment resources
            experiment.resources.create(label='NIFTI')
            resource = experiment.resources['NIFTI']
            resource.upload(str(local_path), local_file.name)
            
            if progress_callback:
                progress_callback(file_size, file_size)
            
            logger.info(f"Uploaded {local_path} to XNAT project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"XNAT upload failed: {e}")
            return False
    
    def disconnect(self):
        """Close XNAT session."""
        if self.session:
            self.session.disconnect()
            self.session = None
    
    def __del__(self):
        """Ensure session is closed on cleanup."""
        self.disconnect()
