"""
BIDS Utilities for Cross-Platform Compatibility (v3.1.1+).

Standardizes BIDS path handling, session detection, and validation.
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


def extract_bids_path(file_path: str) -> str:
    """
    Extract BIDS-relative path from full path.
    
    Finds the portion starting from sub-XX and preserving structure.
    
    Args:
        file_path: Full file path
        
    Returns:
        str: BIDS-relative path (e.g., 'sub-01/ses-01/anat/sub-01_T1w.nii.gz')
    """
    try:
        path_obj = Path(file_path)
        parts = path_obj.parts
        
        # Find first sub- directory
        for i, part in enumerate(parts):
            if part.startswith('sub-'):
                return str(Path(*parts[i:]))
        
        # If no sub- found, return just filename
        return path_obj.name
        
    except Exception as e:
        logger.warning(f"BIDS path extraction failed for {file_path}: {e}")
        return Path(file_path).name


def extract_subject_id(path: str) -> Optional[str]:
    """
    Extract subject ID from BIDS path.
    
    Args:
        path: File or directory path
        
    Returns:
        str: Subject ID (e.g., 'sub-01') or None
    """
    match = re.search(r'(sub-[a-zA-Z0-9]+)', path)
    return match.group(1) if match else None


def extract_session_id(path: str) -> Optional[str]:
    """
    Extract session ID from BIDS path.
    
    Args:
        path: File or directory path
        
    Returns:
        str: Session ID (e.g., 'ses-01') or None
    """
    match = re.search(r'(ses-[a-zA-Z0-9]+)', path)
    return match.group(1) if match else None


def extract_modality(path: str) -> Optional[str]:
    """
    Extract imaging modality from BIDS path.
    
    Args:
        path: File path
        
    Returns:
        str: Modality (anat, func, dwi, fmap) or None
    """
    match = re.search(r'/(anat|func|dwi|fmap)/', path)
    return match.group(1) if match else None


def normalize_subject_id(subject_id: str) -> str:
    """
    Normalize subject ID to BIDS format.
    
    Args:
        subject_id: Subject ID (may or may not have 'sub-' prefix)
        
    Returns:
        str: Normalized subject ID with 'sub-' prefix
    """
    if not subject_id:
        return 'sub-unknown'
    
    if subject_id.startswith('sub-'):
        return subject_id
    else:
        return f'sub-{subject_id}'


def normalize_session_id(session_id: str) -> str:
    """
    Normalize session ID to BIDS format.
    
    Args:
        session_id: Session ID (may or may not have 'ses-' prefix)
        
    Returns:
        str: Normalized session ID with 'ses-' prefix
    """
    if not session_id:
        return 'ses-01'
    
    if session_id.startswith('ses-'):
        return session_id
    else:
        return f'ses-{session_id}'


def parse_bids_filename(filename: str) -> Dict[str, str]:
    """
    Parse BIDS filename into components.
    
    Example: 'sub-01_ses-01_T1w.nii.gz' -> {'subject': 'sub-01', 'session': 'ses-01', 'suffix': 'T1w'}
    
    Args:
        filename: BIDS filename
        
    Returns:
        dict: Parsed components
    """
    components = {
        'subject': None,
        'session': None,
        'task': None,
        'acquisition': None,
        'run': None,
        'suffix': None,
        'extension': None
    }
    
    # Extract subject
    subject_match = re.search(r'sub-([a-zA-Z0-9]+)', filename)
    if subject_match:
        components['subject'] = f'sub-{subject_match.group(1)}'
    
    # Extract session
    session_match = re.search(r'ses-([a-zA-Z0-9]+)', filename)
    if session_match:
        components['session'] = f'ses-{session_match.group(1)}'
    
    # Extract task
    task_match = re.search(r'task-([a-zA-Z0-9]+)', filename)
    if task_match:
        components['task'] = task_match.group(1)
    
    # Extract acquisition
    acq_match = re.search(r'acq-([a-zA-Z0-9]+)', filename)
    if acq_match:
        components['acquisition'] = acq_match.group(1)
    
    # Extract run
    run_match = re.search(r'run-([0-9]+)', filename)
    if run_match:
        components['run'] = run_match.group(1)
    
    # Extract suffix (T1w, T2w, bold, etc.)
    suffix_match = re.search(r'_([A-Za-z0-9]+)\.(nii|nii\.gz|json)$', filename)
    if suffix_match:
        components['suffix'] = suffix_match.group(1)
    
    # Extract extension
    if filename.endswith('.nii.gz'):
        components['extension'] = '.nii.gz'
    elif filename.endswith('.nii'):
        components['extension'] = '.nii'
    elif filename.endswith('.json'):
        components['extension'] = '.json'
    
    return components


def detect_sessions_in_path(dataset_path: str, subject_id: str) -> List[str]:
    """
    Detect all sessions for a subject in a local BIDS dataset.
    
    Args:
        dataset_path: Path to BIDS dataset
        subject_id: Subject ID (with or without 'sub-' prefix)
        
    Returns:
        list: Session IDs (e.g., ['ses-01', 'ses-02']) or empty list
    """
    try:
        subject_id = normalize_subject_id(subject_id)
        subject_dir = Path(dataset_path) / subject_id
        
        if not subject_dir.exists():
            return []
        
        sessions = []
        
        # Look for ses-* directories
        for item in subject_dir.iterdir():
            if item.is_dir() and item.name.startswith('ses-'):
                sessions.append(item.name)
        
        # If no sessions found, check for modality folders (sessionless)
        if not sessions:
            modalities = ['anat', 'func', 'dwi', 'fmap']
            for mod in modalities:
                if (subject_dir / mod).exists():
                    return []  # Sessionless BIDS
        
        return sorted(sessions)
        
    except Exception as e:
        logger.error(f"Session detection failed for {subject_id}: {e}")
        return []


def validate_bids_structure(dataset_path: str) -> Tuple[bool, List[str]]:
    """
    Validate that dataset follows BIDS structure.
    
    Args:
        dataset_path: Path to dataset
        
    Returns:
        tuple: (is_valid: bool, errors: List[str])
    """
    errors = []
    dataset_dir = Path(dataset_path)
    
    if not dataset_dir.exists():
        return False, ["Dataset path does not exist"]
    
    # Check for dataset_description.json
    desc_file = dataset_dir / 'dataset_description.json'
    if not desc_file.exists():
        errors.append("Missing dataset_description.json")
    
    # Check for at least one sub-* directory
    subjects = list(dataset_dir.glob('sub-*'))
    if not subjects:
        errors.append("No subject directories (sub-*) found")
    
    # Check subjects have proper structure
    for subject_dir in subjects[:5]:  # Check first 5
        if not subject_dir.is_dir():
            continue
        
        # Check for sessions or modality folders
        has_sessions = any(item.name.startswith('ses-') for item in subject_dir.iterdir() if item.is_dir())
        has_modalities = any(item.name in ['anat', 'func', 'dwi', 'fmap'] for item in subject_dir.iterdir() if item.is_dir())
        
        if not has_sessions and not has_modalities:
            errors.append(f"{subject_dir.name}: No sessions or modality folders found")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def build_bids_path(subject_id: str, session_id: Optional[str],
                   modality: str, filename: str) -> str:
    """
    Build standardized BIDS path.
    
    Args:
        subject_id: Subject ID
        session_id: Session ID (optional)
        modality: Modality (anat, func, dwi, fmap)
        filename: Filename
        
    Returns:
        str: Full BIDS path
    """
    subject_id = normalize_subject_id(subject_id)
    
    if session_id:
        session_id = normalize_session_id(session_id)
        return f"{subject_id}/{session_id}/{modality}/{filename}"
    else:
        return f"{subject_id}/{modality}/{filename}"


def get_session_modalities(dataset_path: str, subject_id: str, 
                          session_id: Optional[str] = None) -> List[str]:
    """
    Get available modalities for a subject/session.
    
    Args:
        dataset_path: Path to BIDS dataset
        subject_id: Subject ID
        session_id: Optional session ID
        
    Returns:
        list: Available modalities (e.g., ['anat', 'func'])
    """
    try:
        subject_id = normalize_subject_id(subject_id)
        
        if session_id:
            session_id = normalize_session_id(session_id)
            base_path = Path(dataset_path) / subject_id / session_id
        else:
            base_path = Path(dataset_path) / subject_id
        
        if not base_path.exists():
            return []
        
        modalities = []
        for item in base_path.iterdir():
            if item.is_dir() and item.name in ['anat', 'func', 'dwi', 'fmap']:
                modalities.append(item.name)
        
        return modalities
        
    except Exception as e:
        logger.error(f"Modality detection failed: {e}")
        return []


def is_nifti_file(filename: str) -> bool:
    """Check if filename is a NIfTI file."""
    return filename.endswith('.nii') or filename.endswith('.nii.gz')


def is_json_file(filename: str) -> bool:
    """Check if filename is a JSON sidecar."""
    return filename.endswith('.json')


def get_companion_files(nifti_path: str) -> List[str]:
    """
    Get companion files for a NIfTI file (JSON, bval, bvec).
    
    Args:
        nifti_path: Path to NIfTI file
        
    Returns:
        list: List of companion file paths that exist
    """
    companions = []
    
    # Remove .nii.gz or .nii extension
    base = str(nifti_path)
    if base.endswith('.nii.gz'):
        base = base[:-7]
    elif base.endswith('.nii'):
        base = base[:-4]
    
    # Check for common companions
    possible_companions = [
        f"{base}.json",      # Sidecar JSON
        f"{base}.bval",      # DWI b-values
        f"{base}.bvec",      # DWI b-vectors
    ]
    
    for companion in possible_companions:
        if Path(companion).exists():
            companions.append(companion)
    
    return companions
