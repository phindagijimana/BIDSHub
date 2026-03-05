"""
Standardized Metadata Handler for Cross-Platform Compatibility (v3.1.1+).

Provides consistent metadata extraction and defaults across all platforms.
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MetadataHandler:
    """Handles metadata extraction and standardization across platforms."""
    
    @staticmethod
    def get_default_subject_metadata() -> Dict:
        """
        Get default/empty subject metadata structure.
        
        Returns:
            dict: Standard metadata dict with None values
        """
        return {
            'age': None,
            'sex': None,
            'diagnosis': None,
            'participant_group': None,
            'handedness': None,
            'site': None,
            'sessions': [],
            'has_anat': False,
            'has_func': False,
            'has_dwi': False,
            'has_fmap': False,
            'metadata': {}
        }
    
    @staticmethod
    def parse_participants_tsv(tsv_path: str) -> Dict[str, Dict]:
        """
        Parse participants.tsv file into metadata dict.
        
        Args:
            tsv_path: Path to participants.tsv
            
        Returns:
            dict: {subject_id: {metadata}}
        """
        result = {}
        
        try:
            tsv_file = Path(tsv_path)
            if not tsv_file.exists():
                return result
            
            with open(tsv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                
                for row in reader:
                    # Get subject ID
                    subject_id = row.get('participant_id', '')
                    if not subject_id:
                        continue
                    
                    # Ensure sub- prefix
                    if not subject_id.startswith('sub-'):
                        subject_id = f'sub-{subject_id}'
                    
                    # Parse metadata with flexible field names
                    metadata = MetadataHandler.get_default_subject_metadata()
                    
                    # Age
                    if 'age' in row:
                        try:
                            metadata['age'] = float(row['age'])
                        except (ValueError, TypeError):
                            pass
                    
                    # Sex
                    if 'sex' in row:
                        metadata['sex'] = row['sex'].upper() if row['sex'] else None
                    elif 'gender' in row:
                        metadata['sex'] = row['gender'].upper() if row['gender'] else None
                    
                    # Diagnosis
                    if 'diagnosis' in row:
                        metadata['diagnosis'] = row['diagnosis']
                    elif 'group' in row:
                        metadata['diagnosis'] = row['group']
                    
                    # Participant group
                    if 'participant_group' in row:
                        metadata['participant_group'] = row['participant_group']
                    elif 'group' in row and 'diagnosis' not in row:
                        metadata['participant_group'] = row['group']
                    
                    # Handedness
                    if 'handedness' in row:
                        metadata['handedness'] = row['handedness']
                    
                    # Site
                    if 'site' in row:
                        metadata['site'] = row['site']
                    
                    # Store all raw metadata
                    metadata['metadata'] = {k: v for k, v in row.items() if k != 'participant_id'}
                    
                    result[subject_id] = metadata
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing participants.tsv: {e}")
            return result
    
    @staticmethod
    def enrich_subject_metadata(subject_dict: Dict, participants_data: Dict[str, Dict]) -> Dict:
        """
        Enrich subject dict with metadata from participants.tsv.
        
        Args:
            subject_dict: Subject dict with default/partial metadata
            participants_data: Parsed participants.tsv data
            
        Returns:
            dict: Enriched subject dict
        """
        subject_id = subject_dict.get('subject_id', '')
        
        if subject_id in participants_data:
            tsv_metadata = participants_data[subject_id]
            
            # Update fields if not already set
            for key in ['age', 'sex', 'diagnosis', 'participant_group', 'handedness', 'site']:
                if subject_dict.get(key) is None and tsv_metadata.get(key) is not None:
                    subject_dict[key] = tsv_metadata[key]
            
            # Merge metadata dicts
            subject_dict['metadata'].update(tsv_metadata.get('metadata', {}))
        
        return subject_dict
    
    @staticmethod
    def normalize_metadata_values(metadata: Dict) -> Dict:
        """
        Normalize metadata values for consistency.
        
        Args:
            metadata: Raw metadata dict
            
        Returns:
            dict: Normalized metadata
        """
        normalized = metadata.copy()
        
        # Normalize sex values
        if 'sex' in normalized and normalized['sex']:
            sex = str(normalized['sex']).upper()
            if sex in ['M', 'MALE', 'MAN']:
                normalized['sex'] = 'M'
            elif sex in ['F', 'FEMALE', 'WOMAN']:
                normalized['sex'] = 'F'
            elif sex in ['O', 'OTHER', 'X']:
                normalized['sex'] = 'O'
            else:
                normalized['sex'] = None
        
        # Normalize handedness
        if 'handedness' in normalized and normalized['handedness']:
            hand = str(normalized['handedness']).upper()
            if hand in ['R', 'RIGHT']:
                normalized['handedness'] = 'R'
            elif hand in ['L', 'LEFT']:
                normalized['handedness'] = 'L'
            elif hand in ['A', 'AMBIDEXTROUS', 'BOTH']:
                normalized['handedness'] = 'A'
            else:
                normalized['handedness'] = None
        
        # Ensure age is numeric or None
        if 'age' in normalized:
            try:
                normalized['age'] = float(normalized['age']) if normalized['age'] else None
            except (ValueError, TypeError):
                normalized['age'] = None
        
        return normalized
    
    @staticmethod
    def merge_scan_metadata(scan_dict: Dict, json_sidecar: Dict) -> Dict:
        """
        Merge scan dict with JSON sidecar metadata.
        
        Args:
            scan_dict: Scan dict from database
            json_sidecar: Parsed JSON sidecar
            
        Returns:
            dict: Merged scan dict
        """
        if not json_sidecar:
            return scan_dict
        
        # Add imaging parameters if available
        imaging_params = {}
        
        param_keys = [
            'EchoTime', 'RepetitionTime', 'FlipAngle', 'MagneticFieldStrength',
            'Manufacturer', 'ManufacturersModelName', 'SequenceName',
            'SliceThickness', 'PixelBandwidth', 'InversionTime'
        ]
        
        for key in param_keys:
            if key in json_sidecar:
                imaging_params[key] = json_sidecar[key]
        
        if imaging_params:
            scan_dict['imaging_params'] = imaging_params
        
        return scan_dict
    
    @staticmethod
    def create_minimal_dataset_description(name: str, bids_version: str = "1.6.0") -> Dict:
        """
        Create minimal dataset_description.json content.
        
        Args:
            name: Dataset name
            bids_version: BIDS version
            
        Returns:
            dict: Minimal dataset description
        """
        return {
            "Name": name,
            "BIDSVersion": bids_version,
            "DatasetType": "raw"
        }
