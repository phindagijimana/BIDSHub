"""
Human Connectome Project (HCP) Integration for BIDSHub.

Provides interface to HCP datasets via AWS S3.
HCP provides high-quality multimodal MRI data (structural, functional, diffusion).
"""

from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging

from src.base_agent import BasePlatformAgent


logger = logging.getLogger(__name__)


class HCPAgent(BasePlatformAgent):
    """
    Interface to Human Connectome Project data via AWS S3.
    
    HCP data is stored in AWS S3 buckets with a custom folder structure.
    This agent maps HCP structure to BIDS-like conventions for compatibility.
    """
    
    # HCP AWS S3 configuration
    HCP_BUCKET = 'hcp-openaccess'
    HCP_REGION = 'us-east-1'
    
    # Available HCP datasets
    HCP_DATASETS = {
        'HCP_1200': {
            'name': 'HCP Young Adult 1200 Subjects',
            'description': 'High-quality multimodal MRI from 1200 healthy young adults',
            'subject_count': 1200
        },
        'HCP_Retest': {
            'name': 'HCP Test-Retest',
            'description': 'Test-retest reliability dataset (46 subjects, scanned twice)',
            'subject_count': 46
        },
        'HCP_7T': {
            'name': 'HCP 7T',
            'description': '7 Tesla high-resolution MRI subset',
            'subject_count': 184
        }
    }
    
    def __init__(self, aws_access_key: str, aws_secret_key: str):
        """
        Initialize HCP agent.
        
        Args:
            aws_access_key: AWS Access Key ID from ConnectomeDB
            aws_secret_key: AWS Secret Access Key from ConnectomeDB
        """
        super().__init__(credentials={
            'aws_access_key': aws_access_key,
            'aws_secret_key': aws_secret_key
        })
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.s3_client = None
        self._verify_installation()
    
    def _verify_installation(self):
        """Verify boto3 is installed."""
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "AWS SDK (boto3) not found. Install with: pip install boto3"
            )
    
    def verify_connection(self) -> bool:
        """
        Verify AWS credentials for HCP S3 bucket.
        
        Returns:
            bool: True if connection successful
        """
        try:
            import boto3
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.HCP_REGION
            )
            
            # Test by listing objects (limit to 1)
            response = self.s3_client.list_objects_v2(
                Bucket=self.HCP_BUCKET,
                MaxKeys=1
            )
            
            logger.info(f"Connected to HCP S3 bucket: {self.HCP_BUCKET}")
            return True
            
        except Exception as e:
            logger.error(f"HCP S3 connection failed: {e}")
            return False
    
    def get_datasets(self) -> List[Dict]:
        """
        List available HCP releases.
        
        Returns:
            List of HCP dataset dictionaries
        """
        return [
            {
                'id': dataset_id,
                'name': info['name'],
                'description': info['description'],
                'subject_count': info['subject_count']
            }
            for dataset_id, info in self.HCP_DATASETS.items()
        ]
    
    def get_dataset_structure(self, dataset_id: str = 'HCP_1200') -> Dict:
        """
        Get structure for an HCP dataset.
        
        Args:
            dataset_id: HCP dataset ID (e.g., 'HCP_1200')
            
        Returns:
            Dictionary with subjects and available scans
        """
        if not self.s3_client:
            if not self.verify_connection():
                return {'subjects': [], 'total_scans': 0}
        
        try:
            structure = {
                'subjects': [],
                'total_scans': 0,
                'scan_types': []
            }
            
            # List subjects in S3 (they're in folders like HCP_1200/100307/)
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.HCP_BUCKET,
                Prefix=f'{dataset_id}/',
                Delimiter='/'
            )
            
            for page in pages:
                for prefix in page.get('CommonPrefixes', []):
                    subject_folder = prefix['Prefix'].rstrip('/')
                    subject_id = subject_folder.split('/')[-1]
                    
                    # HCP uses numeric IDs (6 digits)
                    if subject_id.isdigit() and len(subject_id) == 6:
                        # Get available scans for this subject
                        scans = self._get_subject_scans(dataset_id, subject_id)
                        
                        if scans:
                            structure['subjects'].append({
                                'subject_id': f"sub-{subject_id}",  # BIDS format
                                'hcp_id': subject_id,  # Original HCP ID
                                's3_prefix': subject_folder,
                                'scans': scans
                            })
                            structure['total_scans'] += len(scans)
            
            return structure
            
        except Exception as e:
            logger.error(f"Error getting HCP structure: {e}")
            return {'subjects': [], 'total_scans': 0}
    
    def _get_subject_scans(self, dataset_id: str, subject_id: str) -> List[Dict]:
        """
        Get available scans for an HCP subject.
        
        HCP structure: HCP_1200/{subject_id}/{modality}/{files}
        Example modalities: T1w, T2w, MNINonLinear, rfMRI_REST1_LR, etc.
        """
        scans = []
        
        try:
            # List available folders for subject
            response = self.s3_client.list_objects_v2(
                Bucket=self.HCP_BUCKET,
                Prefix=f'{dataset_id}/{subject_id}/',
                Delimiter='/'
            )
            
            for prefix in response.get('CommonPrefixes', []):
                folder = prefix['Prefix'].rstrip('/').split('/')[-1]
                
                # Map HCP folders to BIDS modalities
                if folder in ['T1w', 'T2w']:
                    scans.append({
                        'modality': 'anat',
                        'suffix': folder,
                        's3_folder': prefix['Prefix']
                    })
                elif 'rfMRI' in folder or 'tfMRI' in folder:
                    scans.append({
                        'modality': 'func',
                        'suffix': folder,
                        's3_folder': prefix['Prefix']
                    })
                elif 'Diffusion' in folder:
                    scans.append({
                        'modality': 'dwi',
                        'suffix': 'dwi',
                        's3_folder': prefix['Prefix']
                    })
        
        except Exception as e:
            logger.error(f"Error getting HCP scans: {e}")
        
        return scans
    
    def download_file(self,
                     s3_key: str,
                     target_path: str,
                     progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
        """
        Download file from HCP S3 bucket.
        
        Args:
            s3_key: S3 object key (e.g., 'HCP_1200/100307/T1w/T1w_acpc_dc.nii.gz')
            target_path: Local target path
            progress_callback: Optional progress callback
            
        Returns:
            bool: True if download successful
        """
        if not self.s3_client:
            if not self.verify_connection():
                return False
        
        try:
            if progress_callback:
                progress_callback(0, f"Starting download from HCP S3...")
            
            # Create parent directory
            Path(target_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            if progress_callback:
                progress_callback(50, "Downloading...")
            
            self.s3_client.download_file(
                self.HCP_BUCKET,
                s3_key,
                target_path
            )
            
            if progress_callback:
                progress_callback(100, "Download complete")
            
            logger.info(f"Downloaded: {s3_key} -> {target_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading from HCP S3: {e}")
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return False
    
    def list_subject_files(self, dataset_id: str, subject_id: str) -> List[Dict]:
        """
        List all files for an HCP subject.
        
        Args:
            dataset_id: HCP dataset ID
            subject_id: HCP subject ID (6-digit number)
            
        Returns:
            List of file dictionaries with S3 keys and sizes
        """
        if not self.s3_client:
            if not self.verify_connection():
                return []
        
        files = []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.HCP_BUCKET,
                Prefix=f'{dataset_id}/{subject_id}/'
            )
            
            for page in pages:
                for obj in page.get('Contents', []):
                    # Only include imaging files
                    key = obj['Key']
                    if any(key.endswith(ext) for ext in ['.nii.gz', '.nii', '.json']):
                        files.append({
                            's3_key': key,
                            'filename': key.split('/')[-1],
                            'size_bytes': obj['Size'],
                            'modified': str(obj['LastModified'])
                        })
        
        except Exception as e:
            logger.error(f"Error listing HCP files: {e}")
        
        return files
    
    def get_bids_compliance(self) -> str:
        """HCP uses custom structure, not strict BIDS."""
        return 'partial'
    
    def get_platform_info(self) -> Dict:
        """Get HCP platform information."""
        return {
            'name': 'HCP',
            'full_name': 'Human Connectome Project',
            'type': 'public_archive',
            'bids_support': 'partial',
            'upload_support': False,
            'requires_approval': True,  # Need ConnectomeDB account
            'data_types': ['structural MRI', 'functional MRI', 'diffusion MRI'],
            'primary_focus': 'high-quality multimodal MRI',
            'access_method': 'AWS S3',
            'registration_url': 'https://db.humanconnectome.org'
        }


def check_hcp_connection(aws_access_key: str, aws_secret_key: str) -> bool:
    """
    Check if HCP S3 is accessible (convenience function).
    
    Args:
        aws_access_key: AWS access key
        aws_secret_key: AWS secret key
        
    Returns:
        bool: True if accessible
    """
    try:
        agent = HCPAgent(aws_access_key, aws_secret_key)
        return agent.verify_connection()
    except:
        return False
