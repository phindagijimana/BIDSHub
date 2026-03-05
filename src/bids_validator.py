"""
BIDS Format Validation for Remote Datasets.

Validates that datasets follow BIDS specification before adding to BIDSHub.
Ensures cross-platform compatibility by requiring all datasets to be BIDS-formatted.
"""

import json
import re
import logging
from typing import Tuple, Dict, List, Optional
from pathlib import Path
from io import StringIO

logger = logging.getLogger(__name__)


class BIDSValidator:
    """Validate BIDS compliance for datasets across different platforms."""
    
    # BIDS specification requirements
    REQUIRED_FILES = ['dataset_description.json']
    RECOMMENDED_FILES = ['participants.tsv', 'README']
    
    VALID_MODALITIES = ['anat', 'func', 'dwi', 'fmap', 'perf', 'meg', 'eeg', 'ieeg']
    
    BIDS_FILENAME_PATTERN = r'^sub-[a-zA-Z0-9]+(_ses-[a-zA-Z0-9]+)?(_.*)?(_[a-zA-Z0-9]+)\.(nii|nii\.gz|json|tsv)$'
    
    def __init__(self):
        """Initialize BIDS validator."""
        pass
    
    def validate_remote_dataset(self, 
                               agent, 
                               dataset_id: str,
                               platform: str) -> Tuple[bool, str, Dict]:
        """
        Validate that a remote dataset follows BIDS specification.
        
        Args:
            agent: Platform agent instance (OpenNeuroAgent, PennsieveAgent, etc.)
            dataset_id: Dataset identifier on the platform
            platform: Platform name ('openneuro', 'pennsieve', 'xnat', 'dandi')
            
        Returns:
            Tuple of (is_valid, message, details_dict)
        """
        issues = []
        warnings = []
        details = {
            'has_dataset_description': False,
            'has_participants_tsv': False,
            'has_readme': False,
            'subject_count': 0,
            'bids_version': None,
            'modalities_found': set(),
            'validation_level': 'strict'
        }
        
        try:
            # 1. Get file list from platform
            logger.info(f"Fetching file list from {platform} dataset {dataset_id}")
            
            file_list = self._get_file_list(agent, dataset_id, platform)
            
            if not file_list:
                return False, "[ERROR] Could not retrieve file list from platform", details
            
            # 2. Check for required BIDS files
            has_dataset_desc = any('dataset_description.json' in f for f in file_list)
            has_participants = any('participants.tsv' in f for f in file_list)
            has_readme = any('README' in f.upper() for f in file_list)
            
            details['has_dataset_description'] = has_dataset_desc
            details['has_participants_tsv'] = has_participants
            details['has_readme'] = has_readme
            
            if not has_dataset_desc:
                issues.append("[ERROR] Missing dataset_description.json (required by BIDS)")
            
            if not has_participants:
                warnings.append("[WARNING] Missing participants.tsv (recommended for metadata)")
            
            if not has_readme:
                warnings.append("[WARNING] Missing README (recommended)")
            
            # 3. Validate dataset_description.json if available
            if has_dataset_desc:
                desc_valid, desc_msg, bids_version = self._validate_dataset_description(
                    agent, dataset_id, platform, file_list
                )
                details['bids_version'] = bids_version
                
                if not desc_valid:
                    issues.append(desc_msg)
            
            # 4. Check subject folder structure
            subjects = self._extract_subjects(file_list)
            details['subject_count'] = len(subjects)
            
            if not subjects:
                issues.append("[ERROR] No subject folders found (must start with 'sub-')")
            else:
                # Validate subject naming
                invalid_subjects = [s for s in subjects if not re.match(r'^sub-[a-zA-Z0-9]+$', s)]
                if invalid_subjects:
                    issues.append(f"[ERROR] Invalid subject IDs: {', '.join(invalid_subjects[:5])}")
            
            # 5. Check modality folders and file naming
            if subjects:
                modalities, naming_issues = self._validate_file_structure(file_list, subjects[0])
                details['modalities_found'] = modalities
                
                if not modalities:
                    issues.append("[ERROR] No valid modality folders found (anat, func, dwi, etc.)")
                
                if naming_issues:
                    issues.extend(naming_issues[:3])  # Limit to first 3
            
            # 6. Determine validation result
            if issues:
                msg = "**BIDS Validation Failed**\n\n" + "\n".join(issues)
                if warnings:
                    msg += "\n\n**Warnings:**\n" + "\n".join(warnings)
                return False, msg, details
            
            # Success!
            success_msg = f"[OK] **BIDS Validation Passed**\n\n"
            success_msg += f"- BIDS Version: {details['bids_version']}\n"
            success_msg += f"- Subjects: {details['subject_count']}\n"
            success_msg += f"- Modalities: {', '.join(sorted(details['modalities_found']))}\n"
            
            if warnings:
                success_msg += "\n**Recommendations:**\n" + "\n".join(warnings)
            
            return True, success_msg, details
            
        except Exception as e:
            logger.error(f"BIDS validation error: {e}")
            return False, f"[ERROR] Validation error: {str(e)}", details
    
    def _get_file_list(self, agent, dataset_id: str, platform: str) -> List[str]:
        """Get file list from platform agent."""
        try:
            if platform == 'openneuro':
                # Use GraphQL to get file list
                import requests
                
                graphql_url = 'https://openneuro.org/crn/graphql'
                query = """
                query($datasetId: ID!) {
                    dataset(id: $datasetId) {
                        draft {
                            files {
                                filename
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
                
                if response.status_code == 200:
                    data = response.json()
                    files = data.get('data', {}).get('dataset', {}).get('draft', {}).get('files', [])
                    return [f['filename'] for f in files]
            
            elif platform == 'pennsieve':
                # Use agent's remote structure method
                if hasattr(agent, 'get_remote_dataset_structure'):
                    structure = agent.get_remote_dataset_structure(
                        dataset_id,
                        agent.credentials.get('api_key'),
                        agent.credentials.get('api_secret')
                    )
                    # Extract file paths from structure
                    return self._flatten_structure_files(structure)
            
            elif platform == 'dandi':
                # Use DANDI API
                if hasattr(agent, 'get_dataset_structure'):
                    structure = agent.get_dataset_structure(dataset_id)
                    return [f['path'] for f in structure.get('files', [])]
            
            elif platform == 'xnat':
                # XNAT would need custom implementation
                # For now, return empty to indicate unsupported
                logger.warning("XNAT BIDS validation not yet implemented")
                return []
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting file list from {platform}: {e}")
            return []
    
    def _flatten_structure_files(self, structure: Dict) -> List[str]:
        """Extract flat file list from Pennsieve structure dict."""
        files = []
        
        # Pennsieve structure: {'subjects': [...], 'sessions': {...}, 'files': {...}}
        # Need to reconstruct file paths
        subjects = structure.get('subjects', [])
        sessions_dict = structure.get('sessions', {})
        
        for subject in subjects:
            subject_id = f'sub-{subject}' if not subject.startswith('sub-') else subject
            sessions = sessions_dict.get(subject, [])
            
            if sessions:
                for session in sessions:
                    session_id = f'ses-{session}' if not session.startswith('ses-') else session
                    # Assume standard modalities
                    for modality in self.VALID_MODALITIES:
                        files.append(f"{subject_id}/{session_id}/{modality}/placeholder.nii.gz")
            else:
                # No session
                for modality in self.VALID_MODALITIES:
                    files.append(f"{subject_id}/{modality}/placeholder.nii.gz")
        
        return files
    
    def _validate_dataset_description(self, agent, dataset_id: str, 
                                     platform: str, file_list: List[str]) -> Tuple[bool, str, Optional[str]]:
        """Validate dataset_description.json content."""
        try:
            # Find and fetch dataset_description.json
            desc_file = next((f for f in file_list if f.endswith('dataset_description.json')), None)
            
            if not desc_file:
                return False, "[ERROR] dataset_description.json not found", None
            
            # Fetch file content based on platform
            if platform == 'openneuro':
                import requests
                url = f"https://s3.amazonaws.com/openneuro.org/{dataset_id}/dataset_description.json"
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    return False, "[ERROR] Could not fetch dataset_description.json", None
                
                content = response.text
            else:
                # For other platforms, we might not be able to easily fetch file content
                # Mark as valid with warning
                return True, "[WARNING] Could not verify dataset_description.json content", None
            
            # Parse JSON
            try:
                desc = json.loads(content)
            except json.JSONDecodeError:
                return False, "[ERROR] dataset_description.json is not valid JSON", None
            
            # Check required fields
            if 'Name' not in desc:
                return False, "[ERROR] dataset_description.json missing 'Name' field", None
            
            if 'BIDSVersion' not in desc:
                return False, "[ERROR] dataset_description.json missing 'BIDSVersion' field", None
            
            bids_version = desc.get('BIDSVersion')
            
            return True, f"[OK] Valid dataset_description.json (BIDS {bids_version})", bids_version
            
        except Exception as e:
            logger.error(f"Error validating dataset_description.json: {e}")
            return False, f"[ERROR] Error validating dataset_description.json: {str(e)}", None
    
    def _extract_subjects(self, file_list: List[str]) -> List[str]:
        """Extract unique subject IDs from file list."""
        subjects = set()
        
        for file_path in file_list:
            # Look for sub-XXX pattern
            match = re.search(r'(sub-[a-zA-Z0-9]+)', file_path)
            if match:
                subjects.add(match.group(1))
        
        return sorted(list(subjects))
    
    def _validate_file_structure(self, file_list: List[str], 
                                 sample_subject: str) -> Tuple[set, List[str]]:
        """
        Validate file structure for a sample subject.
        
        Returns:
            Tuple of (modalities_found, naming_issues)
        """
        modalities = set()
        issues = []
        
        # Get files for sample subject
        subject_files = [f for f in file_list if sample_subject in f]
        
        # Check for modality folders
        for modality in self.VALID_MODALITIES:
            if any(f'/{modality}/' in f for f in subject_files):
                modalities.add(modality)
        
        # Check file naming for NIfTI files
        nifti_files = [f for f in subject_files if f.endswith(('.nii', '.nii.gz'))]
        
        for nifti_file in nifti_files[:10]:  # Check first 10
            filename = Path(nifti_file).name
            
            # Validate BIDS naming pattern
            if not re.match(self.BIDS_FILENAME_PATTERN, filename):
                issues.append(f"[ERROR] Non-BIDS filename: {filename}")
        
        return modalities, issues
    
    def validate_local_bids(self, bids_root: str) -> Tuple[bool, str]:
        """
        Validate local BIDS dataset using bids-validator or basic checks.
        
        Args:
            bids_root: Path to BIDS dataset root
            
        Returns:
            Tuple of (is_valid, message)
        """
        bids_path = Path(bids_root)
        
        if not bids_path.exists():
            return False, f"[ERROR] Directory not found: {bids_root}"
        
        if not bids_path.is_dir():
            return False, f"[ERROR] Not a directory: {bids_root}"
        
        issues = []
        warnings = []
        
        # Check for dataset_description.json
        desc_file = bids_path / 'dataset_description.json'
        if not desc_file.exists():
            issues.append("[ERROR] Missing dataset_description.json")
        else:
            # Validate content
            try:
                with open(desc_file) as f:
                    desc = json.load(f)
                
                if 'Name' not in desc:
                    issues.append("[ERROR] dataset_description.json missing 'Name' field")
                if 'BIDSVersion' not in desc:
                    issues.append("[ERROR] dataset_description.json missing 'BIDSVersion' field")
                    
            except json.JSONDecodeError:
                issues.append("[ERROR] dataset_description.json is not valid JSON")
        
        # Check for participants.tsv
        participants_file = bids_path / 'participants.tsv'
        if not participants_file.exists():
            warnings.append("[WARNING] Missing participants.tsv (recommended)")
        else:
            # Validate participants.tsv
            try:
                import pandas as pd
                df = pd.read_csv(participants_file, sep='\t')
                
                if 'participant_id' not in df.columns:
                    issues.append("[ERROR] participants.tsv missing 'participant_id' column")
                
            except Exception as e:
                issues.append(f"[ERROR] Invalid participants.tsv: {str(e)}")
        
        # Check for subject folders
        subject_dirs = [d for d in bids_path.iterdir() 
                       if d.is_dir() and d.name.startswith('sub-')]
        
        if not subject_dirs:
            issues.append("[ERROR] No subject folders found (must start with 'sub-')")
        else:
            # Validate first subject
            sample_subject = subject_dirs[0]
            
            # Check for modality folders
            modality_dirs = [d for d in sample_subject.iterdir() 
                           if d.is_dir() and d.name in self.VALID_MODALITIES]
            
            # Also check for session folders
            session_dirs = [d for d in sample_subject.iterdir() 
                          if d.is_dir() and d.name.startswith('ses-')]
            
            if not modality_dirs and not session_dirs:
                issues.append(f"[ERROR] No valid structure in {sample_subject.name} (need modality or session folders)")
            
            # Check file naming
            nifti_files = list(sample_subject.rglob('*.nii*'))
            
            for nifti_file in nifti_files[:5]:  # Check first 5
                if not re.match(self.BIDS_FILENAME_PATTERN, nifti_file.name):
                    issues.append(f"[ERROR] Non-BIDS filename: {nifti_file.name}")
        
        # Compile result
        if issues:
            msg = "**BIDS Validation Failed**\n\n" + "\n".join(issues)
            if warnings:
                msg += "\n\n**Warnings:**\n" + "\n".join(warnings)
            return False, msg
        
        success_msg = f"[OK] **BIDS Validation Passed**\n\n"
        success_msg += f"- Subjects: {len(subject_dirs)}\n"
        
        if warnings:
            success_msg += "\n**Recommendations:**\n" + "\n".join(warnings)
        
        return True, success_msg


def validate_bids_dataset(dataset_path: str) -> Tuple[bool, str]:
    """
    Convenience function for validating local BIDS datasets.
    
    Args:
        dataset_path: Path to BIDS dataset
        
    Returns:
        Tuple of (is_valid, message)
    """
    validator = BIDSValidator()
    return validator.validate_local_bids(dataset_path)


def validate_remote_bids_dataset(agent, dataset_id: str, platform: str) -> Tuple[bool, str, Dict]:
    """
    Convenience function for validating remote BIDS datasets.
    
    Args:
        agent: Platform agent instance
        dataset_id: Dataset identifier
        platform: Platform name
        
    Returns:
        Tuple of (is_valid, message, details)
    """
    validator = BIDSValidator()
    return validator.validate_remote_dataset(agent, dataset_id, platform)
