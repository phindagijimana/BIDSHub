"""
Metadata-based filtering for BIDS datasets.

Filter subjects and scans by participant metadata (age, sex, diagnosis, etc.)
and scan properties (modality, session, acquisition parameters).

v1.5+: Supports multi-dataset filtering across multiple BIDS datasets.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional


class MetadataFilter:
    """Filter subjects and scans based on metadata criteria (v1.5+ supports multi-dataset)."""
    
    def __init__(self, bids_root: str = None, datasets: List[Dict] = None):
        """
        Initialize metadata filter for single or multiple BIDS datasets.
        
        Args:
            bids_root: Path to BIDS dataset root directory (single dataset, legacy)
            datasets: List of dataset dicts with id, name, root_path (v1.5+ multi-dataset)
        """
        self.bids_root = Path(bids_root) if bids_root else None
        self.datasets = datasets or []
        
        # For single dataset (backwards compatibility)
        if bids_root and not datasets:
            self.participants_df = self._load_participants(self.bids_root)
            self.participants_dfs = {0: self.participants_df} if self.participants_df is not None else {}
        
        # For multi-dataset (v1.5+)
        elif datasets:
            self.participants_dfs = {}  # dataset_id -> DataFrame
            
            for dataset in datasets:
                if dataset.get('root_path'):
                    df = self._load_participants(Path(dataset['root_path']))
                    if df is not None:
                        # Add dataset_id column for tracking
                        df['_dataset_id'] = dataset['id']
                        df['_dataset_name'] = dataset['name']
                        self.participants_dfs[dataset['id']] = df
            
            # For backwards compatibility
            self.participants_df = None
            if len(self.participants_dfs) == 1:
                self.participants_df = list(self.participants_dfs.values())[0]
        else:
            self.participants_df = None
            self.participants_dfs = {}
    
    def _load_participants(self, bids_root: Path = None) -> Optional[pd.DataFrame]:
        """Load participants.tsv with metadata."""
        if bids_root is None:
            bids_root = self.bids_root
        
        if not bids_root:
            return None
        
        participants_file = bids_root / 'participants.tsv'
        
        if not participants_file.exists():
            print(f"Warning: participants.tsv not found at {participants_file}")
            return None
        
        try:
            df = pd.read_csv(participants_file, sep='\t')
            
            # Standardize participant_id column (remove 'sub-' prefix if present)
            if 'participant_id' in df.columns:
                df['participant_id'] = df['participant_id'].str.replace('sub-', '', regex=False)
            
            return df
        except Exception as e:
            print(f"Error loading participants.tsv: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if metadata filtering is available."""
        return bool(self.participants_dfs) or self.participants_df is not None
    
    def get_available_fields(self) -> List[str]:
        """
        Get list of metadata fields available for filtering.
        
        Returns:
            List of column names (excluding participant_id)
        """
        if self.participants_df is None:
            return []
        
        fields = [col for col in self.participants_df.columns 
                 if col != 'participant_id']
        return fields
    
    def get_field_values(self, field_name: str) -> List:
        """
        Get unique values for a metadata field.
        
        Args:
            field_name: Name of field (e.g., 'sex', 'diagnosis')
            
        Returns:
            List of unique values for the field
        """
        if self.participants_df is None or field_name not in self.participants_df.columns:
            return []
        
        values = self.participants_df[field_name].dropna().unique().tolist()
        return sorted(values, key=str)
    
    def get_field_type(self, field_name: str) -> str:
        """
        Determine field type for appropriate UI widget.
        
        Args:
            field_name: Name of field
            
        Returns:
            'numeric' | 'categorical' | 'unknown'
        """
        if self.participants_df is None or field_name not in self.participants_df.columns:
            return 'unknown'
        
        dtype = self.participants_df[field_name].dtype
        
        if pd.api.types.is_numeric_dtype(dtype):
            return 'numeric'
        else:
            return 'categorical'
    
    def filter_subjects(self, criteria: Dict, dataset_ids: List[int] = None):
        """
        Filter subjects based on metadata criteria.
        
        Args:
            criteria: Dictionary of filter criteria
                Examples:
                - {'age': {'min': 18, 'max': 65}}
                - {'sex': ['M', 'F']}
                - {'diagnosis': ['TBI']}
                - {'age': {'min': 30}, 'sex': ['M']}
            dataset_ids: List of dataset IDs to filter (v1.5+ multi-dataset mode)
                If None and multi-dataset mode is active, filters across ALL datasets
        
        Returns:
            - Single-dataset mode: List[str] of subject IDs (without 'sub-' prefix)
            - Multi-dataset mode: List[Dict] with {subject_id, dataset_id, dataset_name}
        """
        # Multi-dataset mode (v1.5+)
        # Activate if we have multiple datasets OR dataset_ids is explicitly provided
        if self.participants_dfs and (len(self.participants_dfs) > 1 or dataset_ids is not None):
            results = []
            
            # Use specified datasets or all datasets if not specified
            if dataset_ids is not None:
                target_datasets = dataset_ids if dataset_ids else list(self.participants_dfs.keys())
            else:
                target_datasets = list(self.participants_dfs.keys())
            
            for ds_id in target_datasets:
                if ds_id not in self.participants_dfs:
                    continue
                
                df = self.participants_dfs[ds_id]
                
                if not criteria:
                    # No filters - return all subjects from this dataset
                    filtered_df = df
                else:
                    filtered_df = self._apply_filters_to_df(df, criteria)
                
                # Add to results with dataset context
                for _, row in filtered_df.iterrows():
                    results.append({
                        'subject_id': row['participant_id'],
                        'dataset_id': row.get('_dataset_id', ds_id),
                        'dataset_name': row.get('_dataset_name', f'Dataset {ds_id}')
                    })
            
            return results
        
        # Single-dataset mode (backwards compatibility)
        if self.participants_df is None:
            return []
        
        if not criteria:
            # No filters - return all subjects
            return self.participants_df['participant_id'].tolist()
        
        df = self._apply_filters_to_df(self.participants_df, criteria)
        
        # Return subject IDs (backwards compatibility)
        return [subj_id.replace('sub-', '') for subj_id in df['participant_id'].tolist()]
    
    def _apply_filters_to_df(self, df: pd.DataFrame, criteria: Dict) -> pd.DataFrame:
        """Apply filter criteria to a dataframe."""
        df = df.copy()
        
        for field, condition in criteria.items():
            if field not in df.columns:
                continue
            
            # Numeric range filter
            if isinstance(condition, dict):
                if 'min' in condition:
                    df = df[df[field] >= condition['min']]
                if 'max' in condition:
                    df = df[df[field] <= condition['max']]
            
            # Categorical filter (list of values)
            elif isinstance(condition, list):
                if condition:  # Only apply if list is not empty
                    df = df[df[field].isin(condition)]
            
            # Single value filter
            else:
                df = df[df[field] == condition]
        
        return df
    
    def get_filter_summary(self, criteria: Dict) -> Dict:
        """
        Get summary statistics for filtered subjects.
        
        Args:
            criteria: Filter criteria
        
        Returns:
            dict: {
                'total_subjects': int,
                'demographics': {...},
                'available_data': {...}
            }
        """
        filtered_subjects = self.filter_subjects(criteria)
        
        if not filtered_subjects or self.participants_df is None:
            return {
                'total_subjects': 0,
                'demographics': {},
                'available_data': {}
            }
        
        # Filter dataframe to matching subjects
        df_filtered = self.participants_df[
            self.participants_df['participant_id'].isin(filtered_subjects)
        ]
        
        summary = {
            'total_subjects': len(filtered_subjects),
            'demographics': {},
            'available_data': {}
        }
        
        # Age statistics
        if 'age' in df_filtered.columns:
            age_series = pd.to_numeric(df_filtered['age'], errors='coerce').dropna()
            if not age_series.empty:
                summary['demographics']['age'] = {
                    'mean': float(age_series.mean()),
                    'min': float(age_series.min()),
                    'max': float(age_series.max()),
                    'std': float(age_series.std()) if len(age_series) > 1 else 0
                }
        
        # Sex distribution
        if 'sex' in df_filtered.columns:
            sex_counts = df_filtered['sex'].value_counts().to_dict()
            summary['demographics']['sex'] = sex_counts
        
        # Diagnosis distribution
        if 'diagnosis' in df_filtered.columns:
            dx_counts = df_filtered['diagnosis'].value_counts().to_dict()
            summary['demographics']['diagnosis'] = dx_counts
        
        return summary
    
    def export_filtered_list(self, criteria: Dict, output_path: str) -> bool:
        """
        Export filtered subject list to CSV.
        
        Args:
            criteria: Filter criteria
            output_path: Path to save CSV file
            
        Returns:
            bool: True if export successful
        """
        filtered_subjects = self.filter_subjects(criteria)
        
        if not filtered_subjects or self.participants_df is None:
            return False
        
        try:
            df_filtered = self.participants_df[
                self.participants_df['participant_id'].isin(filtered_subjects)
            ]
            
            # Add 'sub-' prefix back for BIDS compliance
            df_export = df_filtered.copy()
            df_export['participant_id'] = 'sub-' + df_export['participant_id'].astype(str)
            
            df_export.to_csv(output_path, sep='\t', index=False)
            return True
            
        except Exception as e:
            print(f"Error exporting filtered list: {e}")
            return False
