"""
BIDS validation for datasets.

Validates BIDS datasets to ensure they conform to the BIDS specification
before being added to the Data Explorer.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json


class BIDSValidator:
    """Validate BIDS datasets for compliance with BIDS specification."""
    
    def __init__(self, bids_root: str):
        """
        Initialize BIDS validator.
        
        Args:
            bids_root: Path to BIDS dataset root directory
        """
        self.bids_root = Path(bids_root)
        self.errors = []
        self.warnings = []
        self.required_files = ['dataset_description.json']
        self.required_fields = ['Name', 'BIDSVersion']
    
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate BIDS dataset structure.
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        # Check if directory exists
        if not self.bids_root.exists():
            self.errors.append(f"Directory does not exist: {self.bids_root}")
            return False, self.errors, self.warnings
        
        # Validate required files
        self._validate_required_files()
        
        # Validate dataset_description.json
        self._validate_dataset_description()
        
        # Validate subjects
        self._validate_subjects()
        
        # Validate participants.tsv (optional but recommended)
        self._validate_participants_file()
        
        # Check for common issues
        self._check_common_issues()
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_required_files(self):
        """Check for required BIDS files."""
        for filename in self.required_files:
            filepath = self.bids_root / filename
            if not filepath.exists():
                self.errors.append(f"Missing required file: {filename}")
    
    def _validate_dataset_description(self):
        """Validate dataset_description.json."""
        desc_file = self.bids_root / 'dataset_description.json'
        
        if not desc_file.exists():
            return  # Already reported in _validate_required_files
        
        try:
            with open(desc_file, 'r') as f:
                desc = json.load(f)
            
            # Check required fields
            for field in self.required_fields:
                if field not in desc:
                    self.errors.append(f"Missing required field in dataset_description.json: {field}")
            
            # Validate BIDSVersion format
            if 'BIDSVersion' in desc:
                version = desc['BIDSVersion']
                if not isinstance(version, str):
                    self.errors.append("BIDSVersion must be a string")
                elif not version.replace('.', '').isdigit():
                    self.warnings.append(f"BIDSVersion format may be invalid: {version}")
        
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in dataset_description.json: {e}")
        except Exception as e:
            self.errors.append(f"Error reading dataset_description.json: {e}")
    
    def _validate_subjects(self):
        """Validate subject directories."""
        subject_dirs = list(self.bids_root.glob('sub-*'))
        
        if not subject_dirs:
            self.warnings.append("No subject directories found (sub-*)")
            return
        
        for subject_dir in subject_dirs:
            if not subject_dir.is_dir():
                self.warnings.append(f"Subject path is not a directory: {subject_dir.name}")
                continue
            
            # Check for session directories
            session_dirs = list(subject_dir.glob('ses-*'))
            
            if session_dirs:
                # Has sessions - validate session structure
                for session_dir in session_dirs:
                    if not session_dir.is_dir():
                        self.warnings.append(f"Session path is not a directory: {session_dir.name}")
                    else:
                        self._validate_modality_dirs(session_dir, f"{subject_dir.name}/{session_dir.name}")
            else:
                # No sessions - validate modality dirs directly under subject
                self._validate_modality_dirs(subject_dir, subject_dir.name)
    
    def _validate_modality_dirs(self, parent_dir: Path, context: str):
        """Validate modality directories (anat, func, dwi, etc.)."""
        valid_modalities = ['anat', 'func', 'dwi', 'fmap', 'meg', 'eeg', 'ieeg', 
                           'beh', 'pet', 'micr', 'perf']
        
        modality_dirs = [d for d in parent_dir.iterdir() 
                        if d.is_dir() and not d.name.startswith('.')]
        
        for mod_dir in modality_dirs:
            if mod_dir.name not in valid_modalities:
                self.warnings.append(f"Unknown modality directory in {context}: {mod_dir.name}")
            
            # Check for data files
            files = list(mod_dir.glob('*.nii.gz')) + list(mod_dir.glob('*.nii'))
            if not files:
                self.warnings.append(f"No NIfTI files found in {context}/{mod_dir.name}")
    
    def _validate_participants_file(self):
        """Validate participants.tsv if present."""
        participants_file = self.bids_root / 'participants.tsv'
        
        if not participants_file.exists():
            self.warnings.append("participants.tsv not found (recommended)")
            return
        
        try:
            import pandas as pd
            df = pd.read_csv(participants_file, sep='\t')
            
            if 'participant_id' not in df.columns:
                self.errors.append("participants.tsv missing required column: participant_id")
            
            # Check for duplicate participant IDs
            if 'participant_id' in df.columns:
                duplicates = df['participant_id'].duplicated()
                if duplicates.any():
                    dup_ids = df[duplicates]['participant_id'].tolist()
                    self.errors.append(f"Duplicate participant IDs in participants.tsv: {dup_ids}")
        
        except Exception as e:
            self.errors.append(f"Error reading participants.tsv: {e}")
    
    def _check_common_issues(self):
        """Check for common BIDS issues."""
        # Check for hidden files in root
        hidden_files = [f for f in self.bids_root.iterdir() 
                       if f.is_file() and f.name.startswith('.') 
                       and f.name not in ['.bidsignore', '.gitignore']]
        
        if hidden_files:
            self.warnings.append(f"Hidden files found in root: {[f.name for f in hidden_files]}")
        
        # Check for README
        readme_file = self.bids_root / 'README'
        if not readme_file.exists():
            self.warnings.append("README file not found (recommended)")
        
        # Check for CHANGES
        changes_file = self.bids_root / 'CHANGES'
        if not changes_file.exists():
            self.warnings.append("CHANGES file not found (recommended)")
    
    def get_validation_summary(self) -> str:
        """
        Get human-readable validation summary.
        
        Returns:
            Formatted validation summary
        """
        summary = []
        
        if not self.errors and not self.warnings:
            summary.append("✅ Dataset is valid BIDS")
        else:
            if self.errors:
                summary.append(f"❌ {len(self.errors)} Error(s):")
                for error in self.errors:
                    summary.append(f"  - {error}")
            
            if self.warnings:
                summary.append(f"⚠️  {len(self.warnings)} Warning(s):")
                for warning in self.warnings:
                    summary.append(f"  - {warning}")
        
        return "\n".join(summary)


def validate_bids_dataset(bids_root: str) -> Tuple[bool, str]:
    """
    Quick validation function for BIDS dataset.
    
    Args:
        bids_root: Path to BIDS dataset root
        
    Returns:
        Tuple of (is_valid, summary_message)
    """
    validator = BIDSValidator(bids_root)
    is_valid, errors, warnings = validator.validate()
    summary = validator.get_validation_summary()
    
    return is_valid, summary
