"""
BIDS Dataset Loader for Data Explorer.

Wraps PyBIDS to provide clean interface for loading and querying
BIDS-structured neuroimaging datasets.
"""

from bids import BIDSLayout
from typing import List, Dict, Optional
from pathlib import Path
import os


class BIDSLoader:
    """Wrapper for PyBIDS BIDSLayout with additional utilities."""
    
    def __init__(self, bids_root: str, validate: bool = False):
        """
        Initialize BIDS dataset loader.
        
        Args:
            bids_root: Path to BIDS dataset root directory
            validate: Whether to validate BIDS compliance (slow)
        """
        self.bids_root = Path(bids_root)
        
        if not self.bids_root.exists():
            raise FileNotFoundError(f"BIDS directory not found: {bids_root}")
        
        # Initialize PyBIDS layout
        print(f"Loading BIDS dataset from: {bids_root}")
        print("This may take a moment...")
        
        self.layout = BIDSLayout(
            str(self.bids_root),
            validate=validate,
            derivatives=False  # Don't index derivatives for MVP
        )
        
        print(f"✓ Loaded {len(self.get_subjects())} subjects")
    
    def get_subjects(self) -> List[str]:
        """
        Get list of all subject IDs.
        
        Returns:
            List of subject IDs (without 'sub-' prefix)
        """
        return self.layout.get_subjects()
    
    def get_sessions(self, subject: str = None) -> List[str]:
        """
        Get list of all sessions, optionally for a specific subject.
        
        Args:
            subject: Optional subject ID to filter by
            
        Returns:
            List of session labels (without 'ses-' prefix)
        """
        if subject:
            return self.layout.get_sessions(subject=subject)
        return self.layout.get_sessions()
    
    def get_modalities(self, subject: str = None, session: str = None) -> List[str]:
        """
        Get list of modalities (datatype folders).
        
        Args:
            subject: Optional subject ID
            session: Optional session label
            
        Returns:
            List of modalities (e.g., ['anat', 'func', 'dwi'])
        """
        return self.layout.get_datatypes(subject=subject, session=session)
    
    def get_subject_scans(self, subject: str, session: str = None) -> List[Dict]:
        """
        Get all scans for a subject.
        
        Args:
            subject: Subject ID
            session: Optional session label
            
        Returns:
            List of dictionaries with scan information
        """
        # Get all NIfTI files for this subject
        files = self.layout.get(
            subject=subject,
            session=session,
            extension=['.nii', '.nii.gz'],
            return_type='object'
        )
        
        scans = []
        for f in files:
            scan_info = {
                'subject': f.entities.get('subject'),
                'session': f.entities.get('session'),
                'modality': f.entities.get('datatype'),
                'suffix': f.entities.get('suffix'),
                'acquisition': f.entities.get('acquisition'),
                'task': f.entities.get('task'),
                'run': f.entities.get('run'),
                'file_path': f.path,
                'filename': f.filename,
                'extension': f.extension
            }
            scans.append(scan_info)
        
        return scans
    
    def check_completeness(self, subject: str, 
                          expected_sessions: List[str] = None) -> Dict:
        """
        Check data completeness for a subject.
        
        Args:
            subject: Subject ID
            expected_sessions: List of expected session labels
            
        Returns:
            Dict with completeness information
        """
        subject_sessions = self.get_sessions(subject=subject)
        
        completeness = {
            'subject': subject,
            'has_sessions': len(subject_sessions) > 0,
            'session_count': len(subject_sessions),
            'sessions': subject_sessions
        }
        
        if expected_sessions:
            completeness['expected_sessions'] = expected_sessions
            completeness['has_all_sessions'] = all(
                ses in subject_sessions for ses in expected_sessions
            )
            completeness['missing_sessions'] = [
                ses for ses in expected_sessions 
                if ses not in subject_sessions
            ]
        
        # Get scan counts per session
        session_scans = {}
        for session in subject_sessions:
            scans = self.get_subject_scans(subject, session)
            session_scans[session] = {
                'scan_count': len(scans),
                'modalities': list(set(s['modality'] for s in scans if s['modality']))
            }
        
        completeness['session_scans'] = session_scans
        
        return completeness
    
    def get_file_size(self, file_path: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            file_path: Path to file
            
        Returns:
            File size in bytes
        """
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0
    
    def is_stub_file(self, file_path: str) -> bool:
        """
        Check if file is a Pennsieve stub (very small placeholder file).
        
        Args:
            file_path: Path to file
            
        Returns:
            bool: True if stub file (< 1 KB)
        """
        size = self.get_file_size(file_path)
        return size < 1024  # Less than 1 KB is likely a stub
    
    def get_dataset_description(self) -> Optional[Dict]:
        """
        Get dataset_description.json contents.
        
        Returns:
            Dict with dataset description or None
        """
        desc_file = self.bids_root / 'dataset_description.json'
        if desc_file.exists():
            import json
            with open(desc_file, 'r') as f:
                return json.load(f)
        return None
    
    def get_summary(self) -> Dict:
        """
        Get dataset summary statistics.
        
        Returns:
            Dict with summary information
        """
        subjects = self.get_subjects()
        all_sessions = self.get_sessions()
        
        # Count scans
        total_scans = 0
        stub_count = 0
        
        for subject in subjects:
            scans = self.get_subject_scans(subject)
            total_scans += len(scans)
            for scan in scans:
                if self.is_stub_file(scan['file_path']):
                    stub_count += 1
        
        summary = {
            'dataset_name': self.bids_root.name,
            'bids_root': str(self.bids_root),
            'subject_count': len(subjects),
            'session_types': sorted(set(all_sessions)),
            'session_type_count': len(set(all_sessions)),
            'total_scans': total_scans,
            'stub_files': stub_count,
            'real_files': total_scans - stub_count
        }
        
        # Add dataset description if available
        desc = self.get_dataset_description()
        if desc:
            summary['dataset_description'] = desc
        
        return summary
    
    def validate_pennsieve_structure(self) -> bool:
        """
        Check if dataset has Pennsieve integration.
        
        Returns:
            bool: True if .pennsieve folder exists
        """
        pennsieve_dir = self.bids_root / '.pennsieve'
        return pennsieve_dir.exists()
    
    def get_modality_coverage(self) -> Dict[str, int]:
        """
        Get modality coverage across all subjects.
        
        Returns:
            Dict mapping modality to subject count
        """
        modality_subjects = {}
        
        for subject in self.get_subjects():
            modalities = self.get_modalities(subject=subject)
            for modality in modalities:
                if modality not in modality_subjects:
                    modality_subjects[modality] = set()
                modality_subjects[modality].add(subject)
        
        # Convert sets to counts
        return {
            modality: len(subjects) 
            for modality, subjects in modality_subjects.items()
        }


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python bids_loader.py <bids_root>")
        sys.exit(1)
    
    bids_root = sys.argv[1]
    
    try:
        loader = BIDSLoader(bids_root)
        
        print("\n" + "=" * 50)
        print("BIDS Dataset Summary")
        print("=" * 50)
        
        summary = loader.get_summary()
        for key, value in summary.items():
            if key != 'dataset_description':
                print(f"{key}: {value}")
        
        print("\n" + "=" * 50)
        print("Modality Coverage")
        print("=" * 50)
        
        coverage = loader.get_modality_coverage()
        for modality, count in sorted(coverage.items()):
            print(f"{modality}: {count} subjects")
        
        # Check Pennsieve integration
        if loader.validate_pennsieve_structure():
            print("\n✓ Pennsieve integration detected")
        else:
            print("\n✗ No Pennsieve integration found")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
