"""
Export custom cohorts as new BIDS datasets.

Allows users to create new BIDS datasets from filtered subjects across
multiple source datasets, maintaining BIDS compliance.
"""

import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd


class CohortExporter:
    """Export filtered subjects as a new BIDS dataset."""
    
    def __init__(self, database, bids_loader=None):
        """
        Initialize cohort exporter.
        
        Args:
            database: Database instance
            bids_loader: BIDSLoader instance (optional)
        """
        self.db = database
        self.bids_loader = bids_loader
    
    def export_cohort(self,
                     subject_ids: List[str],
                     dataset_ids: List[int],
                     output_path: str,
                     cohort_name: str,
                     description: str = "",
                     copy_mode: str = "symlink",
                     include_derivatives: bool = False) -> Dict:
        """
        Export selected subjects as a new BIDS dataset.
        
        Args:
            subject_ids: List of subject IDs to export
            dataset_ids: List of source dataset IDs
            output_path: Path where new BIDS dataset will be created
            cohort_name: Name of the cohort/new dataset
            description: Description for dataset_description.json
            copy_mode: 'copy', 'symlink', or 'hardlink'
            include_derivatives: Whether to include derivatives folder
            
        Returns:
            Dict with export results
        """
        output_root = Path(output_path)
        output_root.mkdir(parents=True, exist_ok=True)
        
        results = {
            'success': False,
            'cohort_name': cohort_name,
            'output_path': str(output_root),
            'subjects_exported': 0,
            'total_size_mb': 0,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Step 1: Create dataset_description.json
            self._create_dataset_description(output_root, cohort_name, description, dataset_ids)
            
            # Step 2: Create participants.tsv
            participants_data = self._create_participants_file(
                output_root, subject_ids, dataset_ids
            )
            
            # Step 3: Copy subject data
            for i, (subject_id, dataset_id) in enumerate(zip(subject_ids, dataset_ids)):
                try:
                    copied = self._copy_subject_data(
                        subject_id, dataset_id, output_root, copy_mode
                    )
                    
                    if copied:
                        results['subjects_exported'] += 1
                    else:
                        results['warnings'].append(f"No data found for {subject_id}")
                
                except Exception as e:
                    results['errors'].append(f"Error copying {subject_id}: {e}")
            
            # Step 4: Create README
            self._create_readme(output_root, cohort_name, results)
            
            # Step 5: Calculate total size
            results['total_size_mb'] = self._calculate_directory_size(output_root)
            
            # Step 6: Validate BIDS structure
            from src.bids_validator import validate_bids_dataset
            is_valid, validation_msg = validate_bids_dataset(str(output_root))
            
            if not is_valid:
                results['warnings'].append(f"BIDS validation warnings: {validation_msg}")
            
            results['success'] = results['subjects_exported'] > 0
            
        except Exception as e:
            results['errors'].append(f"Export failed: {e}")
            results['success'] = False
        
        return results
    
    def _create_dataset_description(self, output_root: Path, name: str, 
                                   description: str, dataset_ids: List[int]):
        """Create dataset_description.json for new cohort."""
        # Get source dataset info
        source_datasets = []
        for dataset_id in set(dataset_ids):
            dataset = self.db.get_dataset(dataset_id)
            if dataset:
                source_datasets.append({
                    'name': dataset['name'],
                    'platform': dataset['platform']
                })
        
        dataset_desc = {
            "Name": name,
            "BIDSVersion": "1.6.0",
            "DatasetType": "derivative",
            "GeneratedBy": [{
                "Name": "BIDSHub Cohort Exporter",
                "Version": "1.5.0",
                "Description": description or "Custom cohort exported from multiple datasets"
            }],
            "SourceDatasets": source_datasets,
            "HowToAcknowledge": "Please acknowledge the original data sources",
            "Authors": ["BIDSHub User"],
            "DatasetDOI": "",
            "License": "See source datasets for license information",
            "Acknowledgements": f"Data aggregated from {len(source_datasets)} source dataset(s)",
            "ExportDate": datetime.now().isoformat(),
            "ExportedSubjects": len(set(zip(self._get_subject_list(), dataset_ids)))
        }
        
        desc_file = output_root / 'dataset_description.json'
        with open(desc_file, 'w') as f:
            json.dump(dataset_desc, f, indent=2)
    
    def _get_subject_list(self) -> List[str]:
        """Helper to get current subject list."""
        return []  # Placeholder
    
    def _create_participants_file(self, output_root: Path, 
                                 subject_ids: List[str],
                                 dataset_ids: List[int]) -> pd.DataFrame:
        """Create participants.tsv with metadata from source datasets."""
        participants_data = []
        
        for subject_id, dataset_id in zip(subject_ids, dataset_ids):
            # Get subject from database
            subject = self.db.get_subject(subject_id, dataset_id)
            
            if subject:
                # Get source dataset
                dataset = self.db.get_dataset(dataset_id)
                
                # Load source participants.tsv if available
                source_root = Path(dataset['root_path']) if dataset and dataset.get('root_path') else None
                source_meta = {}
                
                if source_root and (source_root / 'participants.tsv').exists():
                    try:
                        source_df = pd.read_csv(source_root / 'participants.tsv', sep='\t')
                        # Find matching subject
                        subj_row = source_df[source_df['participant_id'].str.contains(subject_id)]
                        if not subj_row.empty:
                            source_meta = subj_row.iloc[0].to_dict()
                    except:
                        pass
                
                # Build participant row
                participant_row = {
                    'participant_id': f"sub-{subject_id}",
                    'source_dataset': dataset['name'] if dataset else 'unknown',
                    'source_platform': dataset['platform'] if dataset else 'unknown',
                    'has_2wk': subject.get('has_2wk', 0),
                    'has_6mo': subject.get('has_6mo', 0),
                }
                
                # Merge source metadata
                for key, value in source_meta.items():
                    if key != 'participant_id' and key not in participant_row:
                        participant_row[key] = value
                
                participants_data.append(participant_row)
        
        # Create DataFrame
        df = pd.DataFrame(participants_data)
        
        # Save to file
        participants_file = output_root / 'participants.tsv'
        df.to_csv(participants_file, sep='\t', index=False)
        
        return df
    
    def _copy_subject_data(self, subject_id: str, dataset_id: int, 
                          output_root: Path, copy_mode: str) -> bool:
        """Copy subject data from source to output."""
        # Get source dataset
        dataset = self.db.get_dataset(dataset_id)
        if not dataset or not dataset.get('root_path'):
            return False
        
        source_root = Path(dataset['root_path'])
        
        # Find subject directory
        subject_dirs = list(source_root.glob(f"sub-{subject_id}")) + \
                      list(source_root.glob(f"sub-{subject_id.replace('sub-', '')}"))
        
        if not subject_dirs:
            return False
        
        source_subject_dir = subject_dirs[0]
        dest_subject_dir = output_root / source_subject_dir.name
        
        # Copy based on mode
        if copy_mode == 'symlink':
            if not dest_subject_dir.exists():
                dest_subject_dir.symlink_to(source_subject_dir, target_is_directory=True)
        
        elif copy_mode == 'hardlink':
            self._copy_tree_hardlink(source_subject_dir, dest_subject_dir)
        
        else:  # copy
            if source_subject_dir.exists() and source_subject_dir.is_dir():
                shutil.copytree(source_subject_dir, dest_subject_dir, 
                              dirs_exist_ok=True)
        
        return dest_subject_dir.exists()
    
    def _copy_tree_hardlink(self, source: Path, dest: Path):
        """Copy directory tree using hard links."""
        dest.mkdir(parents=True, exist_ok=True)
        
        for item in source.iterdir():
            dest_item = dest / item.name
            
            if item.is_dir():
                self._copy_tree_hardlink(item, dest_item)
            else:
                if not dest_item.exists():
                    try:
                        dest_item.hardlink_to(item)
                    except:
                        shutil.copy2(item, dest_item)
    
    def _create_readme(self, output_root: Path, cohort_name: str, results: Dict):
        """Create README file for cohort."""
        readme_content = f"""# {cohort_name}

## Overview

This dataset is a custom cohort exported from BIDSHub v1.5.

**Export Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Dataset Information

- **Subjects**: {results['subjects_exported']}
- **Total Size**: {results['total_size_mb']:.2f} MB
- **Source Datasets**: Multiple (see dataset_description.json)

## Contents

This dataset contains a subset of subjects from one or more source datasets,
aggregated based on specific filtering criteria.

## Usage

This dataset follows the BIDS specification and can be used with any
BIDS-compatible analysis tools.

## Citation

Please cite the original source datasets. See dataset_description.json
for source dataset information.

## Export Details

Exported using BIDSHub v1.5 Cohort Exporter.

For questions or issues, please contact the dataset creator.
"""
        
        readme_file = output_root / 'README'
        readme_file.write_text(readme_content)
    
    def _calculate_directory_size(self, directory: Path) -> float:
        """Calculate total size of directory in MB."""
        total_size = 0
        
        try:
            for item in directory.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
        except:
            pass
        
        return total_size / (1024 * 1024)  # Convert to MB
