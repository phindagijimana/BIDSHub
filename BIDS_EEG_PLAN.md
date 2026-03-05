# BIDS-EEG/iEEG Support - Technical Implementation Plan

**Version:** 1.0 
**Date:** February 2026 
**Status:** Planning Phase

## Executive Summary

This document outlines the technical plan to extend BIDSHub from BIDS-MRI support to full BIDS-EEG/iEEG support. This expansion will enable researchers to work with electrophysiology data (scalp EEG, intracranial EEG) alongside neuroimaging data, creating a unified multi-modal BIDS platform.

**Target Release:** Q3 2026 
**Estimated Effort:** 6-8 weeks development + 2 weeks testing

---

## 1. Motivation & Use Cases

### Why Add EEG/iEEG Support?

**Clinical Research Needs:**
- **Epilepsy Studies:** Most epilepsy research uses iEEG from surgical candidates
- **TBI Research:** Many TBI studies include EEG assessments
- **Multi-Modal Studies:** Growing trend to combine MRI + EEG/iEEG data

**Platform Advantages:**
- Access to IEEG.org (largest iEEG repository)
- OpenNeuro has 50+ BIDS-EEG/iEEG datasets
- Differentiation from MRI-only tools

**User Workflows:**
```
Epilepsy Researcher:
1. Connect to IEEG.org
2. Browse patient datasets (anonymized)
3. Filter by electrode coverage (hippocampus, etc.)
4. Download iEEG + anatomical MRI
5. QC electrode placements
6. Export cohort for analysis

TBI + EEG Researcher:
1. Access TBI dataset with both MRI and EEG
2. Browse subjects with complete data
3. Download structural MRI + EEG recordings
4. Filter by injury severity + EEG findings
5. Export integrated dataset
```

---

## 2. Current State Analysis

### What Works Today (BIDS-MRI)

**Supported:**
- File formats: `.nii`, `.nii.gz` (NIfTI)
- Modalities: `anat`, `func`, `dwi`
- Suffixes: `T1w`, `T2w`, `FLAIR`, `bold`, `dwi`
- Validation: BIDS structure, file presence
- QC: File size checks, required files
- Download: Pennsieve, OpenNeuro

**Key Code Locations:**
```python
# src/bids_loader.py
- Line 102: extension=['.nii', '.nii.gz'] # MRI-specific
- get_subject_scans() only returns NIfTI files

# src/automated_qc.py 
- Line 29: expected_modalities = ['T1w', 'T2w', 'FLAIR', 'DWI'] # MRI-specific
- validate_scan() checks file sizes expecting MRI ranges

# src/bids_validator.py
- validate_modality_structure() assumes imaging files
```

### Gaps for EEG/iEEG

**Missing:**
- ERROR EEG/iEEG file format support (`.edf`, `.vhdr`, `.set`, `.nwb`)
- ERROR Modality-specific validation (channels, sampling rate)
- ERROR EEG-specific required files (`_channels.tsv`, `_events.tsv`)
- ERROR IEEG.org platform integration
- ERROR Electrophysiology QC checks
- ERROR EEG metadata parsing

---

## 3. BIDS-EEG/iEEG Specification Overview

### File Structure

```
sub-01/
 anat/
 sub-01_T1w.nii.gz # Anatomical MRI
 eeg/ # Scalp EEG
 sub-01_task-rest_eeg.edf # Raw EEG data
 sub-01_task-rest_eeg.json # Metadata
 sub-01_task-rest_channels.tsv # Required: channel info
 sub-01_task-rest_events.tsv # Events/annotations
 sub-01_task-rest_coordsystem.json # Optional: electrode positions
 ieeg/ # Intracranial EEG
 sub-01_task-seizure_ieeg.edf
 sub-01_task-seizure_ieeg.json
 sub-01_task-seizure_channels.tsv # Required
 sub-01_task-seizure_events.tsv
 sub-01_task-seizure_electrodes.tsv # Required: electrode positions
 sub-01_task-seizure_coordsystem.json # Required: coordinate system
```

### Required vs Optional Files

**EEG Modality:**
- Required: `*_eeg.<ext>`, `*_eeg.json`, `*_channels.tsv`
- Recommended: `*_events.tsv`, `*_coordsystem.json`

**iEEG Modality:**
- Required: `*_ieeg.<ext>`, `*_ieeg.json`, `*_channels.tsv`, `*_electrodes.tsv`, `*_coordsystem.json`
- Recommended: `*_events.tsv`

### Key Metadata Fields

**`*_eeg.json` / `*_ieeg.json`:**
```json
{
 "TaskName": "rest",
 "SamplingFrequency": 1000,
 "PowerLineFrequency": 60,
 "EEGReference": "average",
 "RecordingDuration": 3600.5,
 "RecordingType": "continuous",
 "EEGChannelCount": 64,
 "EOGChannelCount": 2,
 "ECGChannelCount": 1
}
```

**`*_channels.tsv`:**
```tsv
name type units low_cutoff high_cutoff sampling_frequency status
FP1 EEG µV 0.1 300 1000 good
FP2 EEG µV 0.1 300 1000 good
EOG1 EOG µV 0.1 300 1000 good
```

**`*_electrodes.tsv` (iEEG only):**
```tsv
name x y z size material manufacturer group
LHH1 -20.5 -15.2 -8.3 2.5 Platinum AdTech LeftHipp
LHH2 -22.1 -16.8 -9.1 2.5 Platinum AdTech LeftHipp
```

---

## 4. Supported File Formats

### Priority File Formats

| Format | Extension | Priority | Description | Library |
|--------|-----------|----------|-------------|---------|
| European Data Format | `.edf`, `.edf+` | **HIGH** | Most common, widely supported | MNE-Python |
| BrainVision | `.vhdr`, `.vmrk`, `.eeg` | **HIGH** | Common in EEG labs | MNE-Python |
| EEGLAB | `.set`, `.fdt` | **MEDIUM** | MATLAB EEG toolbox | MNE-Python |
| Neurodata Without Borders | `.nwb` | **HIGH** | Standard for iEEG, IEEG.org | pynwb |
| BioSemi | `.bdf` | **MEDIUM** | BioSemi hardware | MNE-Python |
| Neuroscan | `.cnt` | **LOW** | Legacy format | MNE-Python |

### Format Detection Logic

```python
def detect_eeg_format(file_path: Path) -> str:
 """Detect EEG file format from extension and validate."""
 ext = file_path.suffix.lower()
    
 format_map = {
 '.edf': 'edf',
 '.edf+': 'edf+',
 '.vhdr': 'brainvision',
 '.set': 'eeglab',
 '.nwb': 'nwb',
 '.bdf': 'biosemi',
 '.cnt': 'neuroscan'
 }
    
 if ext in format_map:
 return format_map[ext]
    
 raise ValueError(f"Unsupported EEG format: {ext}")
```

---

## 5. Architecture Changes

### 5.1 Enhanced BIDSLoader

**File:** `src/bids_loader.py`

**Changes Required:**

```python
class BIDSLoader:
 """Enhanced to support MRI + EEG/iEEG modalities."""
    
 # BEFORE (MRI-only):
 def get_subject_scans(self, subject: str, session: str = None):
 files = self.layout.get(
 subject=subject,
 session=session,
 extension=['.nii', '.nii.gz'], # MRI-specific
 return_type='object'
 )
    
 # AFTER (Multi-modal):
 def get_subject_scans(self, subject: str, session: str = None,
 modality: str = None):
 """
 Get scans for subject, supporting all BIDS modalities.
        
 Args:
 subject: Subject ID
 session: Optional session
 modality: Optional filter ('anat', 'func', 'eeg', 'ieeg', 'meg')
 """
 # Define supported extensions per modality
 extensions = {
 'anat': ['.nii', '.nii.gz'],
 'func': ['.nii', '.nii.gz'],
 'dwi': ['.nii', '.nii.gz'],
 'eeg': ['.edf', '.vhdr', '.set', '.bdf', '.cnt'],
 'ieeg': ['.edf', '.vhdr', '.nwb'],
 'meg': ['.fif', '.ds', '.sqd']
 }
        
 # Get files based on modality filter
 if modality:
 exts = extensions.get(modality, [])
 else:
 # Get all supported extensions
 exts = [ext for ext_list in extensions.values() 
 for ext in ext_list]
        
 files = self.layout.get(
 subject=subject,
 session=session,
 extension=exts,
 return_type='object'
 )
        
 return self._parse_scan_info(files)
    
 def _parse_scan_info(self, files):
 """Parse scan info supporting all modalities."""
 scans = []
 for f in files:
 scan_info = {
 'subject': f.entities.get('subject'),
 'session': f.entities.get('session'),
 'modality': f.entities.get('datatype'),
 'suffix': f.entities.get('suffix'),
 'task': f.entities.get('task'),
 'run': f.entities.get('run'),
 'file_path': f.path,
 'filename': f.filename,
 'extension': self._get_extension(f)
 }
            
 # Add modality-specific fields
 if scan_info['modality'] in ['eeg', 'ieeg']:
 scan_info.update(self._get_eeg_metadata(f))
            
 scans.append(scan_info)
        
 return scans
    
 def _get_eeg_metadata(self, file_obj):
 """Extract EEG-specific metadata from JSON sidecar."""
 metadata = {}
 json_file = file_obj.path.replace(
 file_obj.path.split('.')[-1], 'json'
 )
        
 if os.path.exists(json_file):
 import json
 with open(json_file) as f:
 data = json.load(f)
 metadata['sampling_frequency'] = data.get('SamplingFrequency')
 metadata['eeg_channel_count'] = data.get('EEGChannelCount')
 metadata['recording_duration'] = data.get('RecordingDuration')
 metadata['task_name'] = data.get('TaskName')
        
 return metadata
    
 def get_eeg_channels(self, subject: str, session: str = None, 
 suffix: str = 'eeg'):
 """
 Get channel information from _channels.tsv file.
        
 Returns:
 pandas.DataFrame with channel info
 """
 import pandas as pd
        
 channels_files = self.layout.get(
 subject=subject,
 session=session,
 suffix=suffix,
 extension='tsv',
 scope='raw'
 )
        
 if channels_files:
 # Find _channels.tsv file
 for f in channels_files:
 if '_channels.tsv' in f.filename:
 return pd.read_csv(f.path, sep='\t')
        
 return None
    
 def get_ieeg_electrodes(self, subject: str, session: str = None):
 """
 Get electrode information from _electrodes.tsv file.
        
 Returns:
 pandas.DataFrame with electrode positions
 """
 import pandas as pd
        
 electrode_files = self.layout.get(
 subject=subject,
 session=session,
 suffix='electrodes',
 extension='tsv'
 )
        
 if electrode_files:
 return pd.read_csv(electrode_files[0].path, sep='\t')
        
 return None
```

### 5.2 New EEG Data Handler

**File:** `src/eeg_handler.py` (NEW)

```python
"""
EEG/iEEG data handler for BIDSHub.
Provides utilities for reading, validating, and QC of EEG/iEEG data.
"""

import mne
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd


class EEGHandler:
 """Handler for EEG/iEEG data operations."""
    
 SUPPORTED_FORMATS = {
 '.edf': 'edf',
 '.vhdr': 'brainvision',
 '.set': 'eeglab',
 '.nwb': 'nwb',
 '.bdf': 'biosemi'
 }
    
 def __init__(self):
 """Initialize EEG handler."""
 self.current_data = None
    
 def read_eeg_file(self, file_path: str, preload: bool = False) -> mne.io.Raw:
 """
 Read EEG file using MNE-Python.
        
 Args:
 file_path: Path to EEG file
 preload: Whether to load data into memory
            
 Returns:
 MNE Raw object
 """
 file_path = Path(file_path)
 fmt = self._detect_format(file_path)
        
 if fmt == 'edf':
 raw = mne.io.read_raw_edf(file_path, preload=preload)
 elif fmt == 'brainvision':
 raw = mne.io.read_raw_brainvision(file_path, preload=preload)
 elif fmt == 'eeglab':
 raw = mne.io.read_raw_eeglab(file_path, preload=preload)
 elif fmt == 'biosemi':
 raw = mne.io.read_raw_bdf(file_path, preload=preload)
 elif fmt == 'nwb':
 # For NWB (iEEG.org format)
 from pynwb import NWBHDF5IO
 with NWBHDF5IO(file_path, 'r') as io:
 nwbfile = io.read()
 # Convert to MNE Raw
 # This requires custom conversion logic
 raw = self._nwb_to_mne(nwbfile)
 else:
 raise ValueError(f"Unsupported format: {fmt}")
        
 self.current_data = raw
 return raw
    
 def _detect_format(self, file_path: Path) -> str:
 """Detect EEG file format."""
 ext = file_path.suffix.lower()
 if ext not in self.SUPPORTED_FORMATS:
 raise ValueError(f"Unsupported EEG format: {ext}")
 return self.SUPPORTED_FORMATS[ext]
    
 def get_basic_info(self, file_path: str) -> Dict:
 """
 Get basic information about EEG file without loading data.
        
 Returns:
 Dict with n_channels, sfreq, duration, etc.
 """
 raw = self.read_eeg_file(file_path, preload=False)
        
 info = {
 'n_channels': len(raw.ch_names),
 'channel_names': raw.ch_names,
 'sampling_frequency': raw.info['sfreq'],
 'duration': raw.times[-1],
 'n_samples': len(raw.times),
 'channel_types': [ch['kind'] for ch in raw.info['chs']]
 }
        
 return info
    
 def validate_channels_tsv(self, eeg_file: str, channels_tsv: str) -> Tuple[bool, list]:
 """
 Validate _channels.tsv matches EEG file.
        
 Returns:
 (is_valid, errors)
 """
 raw = self.read_eeg_file(eeg_file, preload=False)
 channels_df = pd.read_csv(channels_tsv, sep='\t')
        
 errors = []
        
 # Check channel count matches
 if len(raw.ch_names) != len(channels_df):
 errors.append(
 f"Channel count mismatch: EEG file has {len(raw.ch_names)}, "
 f"channels.tsv has {len(channels_df)}"
 )
        
 # Check channel names match
 tsv_names = channels_df['name'].tolist()
 for ch_name in raw.ch_names:
 if ch_name not in tsv_names:
 errors.append(f"Channel '{ch_name}' in EEG file not found in channels.tsv")
        
 # Check required columns
 required_cols = ['name', 'type', 'units']
 for col in required_cols:
 if col not in channels_df.columns:
 errors.append(f"Required column '{col}' missing from channels.tsv")
        
 return len(errors) == 0, errors
    
 def check_data_quality(self, file_path: str) -> Dict:
 """
 Perform basic QC checks on EEG data.
        
 Returns:
 Dict with QC results
 """
 raw = self.read_eeg_file(file_path, preload=True)
        
 qc_results = {
 'file_readable': True,
 'warnings': [],
 'errors': []
 }
        
 # Check for flat channels
 data = raw.get_data()
 for i, ch_name in enumerate(raw.ch_names):
 if np.std(data[i]) < 1e-10:
 qc_results['warnings'].append(f"Flat channel detected: {ch_name}")
        
 # Check for extreme values
 if np.any(np.abs(data) > 1000): # Assuming µV
 qc_results['warnings'].append("Extreme amplitude values detected (>1000 µV)")
        
 # Check sampling frequency
 if raw.info['sfreq'] < 100:
 qc_results['warnings'].append(f"Low sampling frequency: {raw.info['sfreq']} Hz")
        
 return qc_results
    
 def _nwb_to_mne(self, nwbfile):
 """Convert NWB file to MNE Raw object (for iEEG.org data)."""
 # Placeholder for NWB conversion
 # This needs full implementation based on NWB structure
 pass


class IEEGHandler(EEGHandler):
 """Specialized handler for iEEG data with electrode positions."""
    
 def validate_electrodes_tsv(self, ieeg_file: str, electrodes_tsv: str,
 channels_tsv: str) -> Tuple[bool, list]:
 """
 Validate _electrodes.tsv for iEEG data.
        
 Checks:
 - All channels in channels.tsv have entries in electrodes.tsv
 - Required columns present (name, x, y, z)
 - Coordinate values are reasonable
 """
 channels_df = pd.read_csv(channels_tsv, sep='\t')
 electrodes_df = pd.read_csv(electrodes_tsv, sep='\t')
        
 errors = []
        
 # Check required columns
 required_cols = ['name', 'x', 'y', 'z']
 for col in required_cols:
 if col not in electrodes_df.columns:
 errors.append(f"Required column '{col}' missing from electrodes.tsv")
        
 # Check all EEG channels have electrode positions
 eeg_channels = channels_df[channels_df['type'] == 'ECOG']['name'].tolist()
 electrode_names = electrodes_df['name'].tolist()
        
 for ch_name in eeg_channels:
 if ch_name not in electrode_names:
 errors.append(
 f"iEEG channel '{ch_name}' missing from electrodes.tsv"
 )
        
 # Check coordinate ranges are reasonable (brain coordinates)
 if len(electrodes_df) > 0:
 coords = electrodes_df[['x', 'y', 'z']].values
 if np.any(np.abs(coords) > 200): # Assuming mm, brain ~200mm
 errors.append("Electrode coordinates outside expected range")
        
 return len(errors) == 0, errors
    
 def get_electrode_coverage(self, electrodes_tsv: str) -> Dict:
 """
 Analyze electrode coverage from electrodes.tsv.
        
 Returns:
 Dict with coverage info (regions, hemisphere, etc.)
 """
 electrodes_df = pd.read_csv(electrodes_tsv, sep='\t')
        
 coverage = {
 'total_electrodes': len(electrodes_df),
 'regions': [],
 'hemisphere': None
 }
        
 # Parse group column (if available) for anatomical regions
 if 'group' in electrodes_df.columns:
 coverage['regions'] = electrodes_df['group'].unique().tolist()
        
 # Determine hemisphere from x coordinates (if available)
 if 'x' in electrodes_df.columns:
 mean_x = electrodes_df['x'].mean()
 if mean_x < -5:
 coverage['hemisphere'] = 'left'
 elif mean_x > 5:
 coverage['hemisphere'] = 'right'
 else:
 coverage['hemisphere'] = 'bilateral'
        
 return coverage
```

### 5.3 Enhanced Automated QC

**File:** `src/automated_qc.py`

**Changes:**

```python
class AutomatedQC:
 """Enhanced QC supporting MRI + EEG/iEEG."""
    
 def __init__(self, bids_root: str):
 self.bids_root = Path(bids_root)
        
 # Modality-specific expected files
 self.expected_files = {
 'mri': {
 'modalities': ['T1w', 'T2w', 'FLAIR', 'DWI'],
 'extensions': ['.nii.gz', '.nii']
 },
 'eeg': {
 'required': ['_eeg.<ext>', '_eeg.json', '_channels.tsv'],
 'recommended': ['_events.tsv']
 },
 'ieeg': {
 'required': [
 '_ieeg.<ext>', '_ieeg.json', '_channels.tsv',
 '_electrodes.tsv', '_coordsystem.json'
 ],
 'recommended': ['_events.tsv']
 }
 }
        
 self.eeg_handler = EEGHandler()
 self.ieeg_handler = IEEGHandler()
    
 def validate_scan(self, scan_info: Dict) -> Dict:
 """Validate scan based on modality."""
 modality = scan_info.get('modality')
        
 if modality in ['anat', 'func', 'dwi']:
 return self._validate_mri_scan(scan_info)
 elif modality == 'eeg':
 return self._validate_eeg_scan(scan_info)
 elif modality == 'ieeg':
 return self._validate_ieeg_scan(scan_info)
 else:
 return {'status': 'unknown', 'errors': [f'Unknown modality: {modality}']}
    
 def _validate_mri_scan(self, scan_info: Dict) -> Dict:
 """Existing MRI validation logic."""
 # Current implementation
 pass
    
 def _validate_eeg_scan(self, scan_info: Dict) -> Dict:
 """Validate EEG scan."""
 errors = []
 warnings = []
        
 file_path = scan_info['file_path']
 base_path = Path(file_path)
 base_name = base_path.stem.replace('.nii', '').replace('.gz', '')
        
 # Check file exists and is readable
 if not base_path.exists():
 errors.append(f"File not found: {file_path}")
 return {'status': 'fail', 'errors': errors}
        
 try:
 # Check EEG file is readable
 info = self.eeg_handler.get_basic_info(str(file_path))
            
 # Check reasonable values
 if info['n_channels'] < 8:
 warnings.append(f"Low channel count: {info['n_channels']}")
 if info['sampling_frequency'] < 100:
 warnings.append(f"Low sampling rate: {info['sampling_frequency']} Hz")
 if info['duration'] < 60:
 warnings.append(f"Short recording: {info['duration']:.1f}s")
            
 # Check required sidecar files
 json_file = base_path.with_suffix('.json')
 if not json_file.exists():
 errors.append("Missing required _eeg.json sidecar")
            
 channels_file = base_path.parent / f"{base_name}_channels.tsv"
 if not channels_file.exists():
 errors.append("Missing required _channels.tsv file")
 else:
 # Validate channels.tsv matches EEG file
 is_valid, ch_errors = self.eeg_handler.validate_channels_tsv(
 str(file_path), str(channels_file)
 )
 if not is_valid:
 errors.extend(ch_errors)
            
 # Run QC checks
 qc_results = self.eeg_handler.check_data_quality(str(file_path))
 warnings.extend(qc_results.get('warnings', []))
 errors.extend(qc_results.get('errors', []))
            
 except Exception as e:
 errors.append(f"Error reading EEG file: {str(e)}")
        
 status = 'fail' if errors else ('warn' if warnings else 'pass')
        
 return {
 'status': status,
 'errors': errors,
 'warnings': warnings,
 'info': info if 'info' in locals() else None
 }
    
 def _validate_ieeg_scan(self, scan_info: Dict) -> Dict:
 """Validate iEEG scan (more strict than EEG)."""
 # Similar to EEG but also check electrodes.tsv and coordsystem.json
 result = self._validate_eeg_scan(scan_info)
        
 file_path = scan_info['file_path']
 base_path = Path(file_path)
 base_name = base_path.stem.replace('.nii', '').replace('.gz', '')
        
 # Additional iEEG-specific checks
 electrodes_file = base_path.parent / f"{base_name}_electrodes.tsv"
 if not electrodes_file.exists():
 result['errors'].append("Missing required _electrodes.tsv file")
 else:
 channels_file = base_path.parent / f"{base_name}_channels.tsv"
 if channels_file.exists():
 is_valid, el_errors = self.ieeg_handler.validate_electrodes_tsv(
 str(file_path), str(electrodes_file), str(channels_file)
 )
 if not is_valid:
 result['errors'].extend(el_errors)
        
 coordsystem_file = base_path.parent / f"{base_name}_coordsystem.json"
 if not coordsystem_file.exists():
 result['errors'].append("Missing required _coordsystem.json file")
        
 # Update status
 result['status'] = 'fail' if result['errors'] else (
 'warn' if result['warnings'] else 'pass'
 )
        
 return result
```

### 5.4 Enhanced BIDS Validator

**File:** `src/bids_validator.py`

**Add modality-specific validation:**

```python
def validate_modality_structure(self, modality_path: Path) -> None:
 """Validate modality folder structure based on type."""
 modality_name = modality_path.name
    
 if modality_name in ['anat', 'func', 'dwi']:
 self._validate_mri_modality(modality_path)
 elif modality_name == 'eeg':
 self._validate_eeg_modality(modality_path)
 elif modality_name == 'ieeg':
 self._validate_ieeg_modality(modality_path)
 elif modality_name == 'meg':
 self._validate_meg_modality(modality_path)

def _validate_eeg_modality(self, eeg_path: Path) -> None:
 """Validate EEG modality structure."""
 # Check for EEG files
 eeg_files = list(eeg_path.glob('*_eeg.*'))
 if not eeg_files:
 self.warnings.append(f"No EEG files found in {eeg_path}")
 return
    
 for eeg_file in eeg_files:
 if eeg_file.suffix not in ['.edf', '.vhdr', '.set', '.bdf']:
 continue
        
 base_name = eeg_file.stem
        
 # Check for required sidecar
 json_file = eeg_file.with_suffix('.json')
 if not json_file.exists():
 self.errors.append(f"Missing {base_name}.json sidecar")
        
 # Check for channels.tsv
 channels_file = eeg_path / f"{base_name}_channels.tsv"
 if not channels_file.exists():
 self.errors.append(f"Missing {base_name}_channels.tsv")

def _validate_ieeg_modality(self, ieeg_path: Path) -> None:
 """Validate iEEG modality structure (stricter than EEG)."""
 self._validate_eeg_modality(ieeg_path) # Run EEG checks first
    
 # Additional iEEG-specific checks
 ieeg_files = list(ieeg_path.glob('*_ieeg.*'))
    
 for ieeg_file in ieeg_files:
 if ieeg_file.suffix not in ['.edf', '.vhdr', '.nwb']:
 continue
        
 base_name = ieeg_file.stem
        
 # Check for electrodes.tsv
 electrodes_file = ieeg_path / f"{base_name}_electrodes.tsv"
 if not electrodes_file.exists():
 self.errors.append(f"Missing {base_name}_electrodes.tsv")
        
 # Check for coordsystem.json
 coordsystem_file = ieeg_path / f"{base_name}_coordsystem.json"
 if not coordsystem_file.exists():
 self.errors.append(f"Missing {base_name}_coordsystem.json")
```

---

## 6. Platform Integrations

### 6.1 IEEG.org Integration

**File:** `src/ieeg_client.py` (NEW)

```python
"""
IEEG.org client for accessing intracranial EEG data.
Uses ieeg-python package for API access.
"""

from ieeg.auth import Session
from ieeg.dataset import Dataset
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd


class IEEGClient:
 """Client for IEEG.org platform."""
    
 def __init__(self, username: str = None, password: str = None):
 """
 Initialize IEEG.org client.
        
 Args:
 username: IEEG.org username
 password: IEEG.org password
 """
 self.username = username
 self.password = password
 self.session = None
        
 if username and password:
 self.connect()
    
 def connect(self):
 """Establish connection to IEEG.org."""
 try:
 self.session = Session(self.username, self.password)
 print("Connected to IEEG.org")
 except Exception as e:
 raise ConnectionError(f"Failed to connect to IEEG.org: {e}")
    
 def list_datasets(self) -> List[str]:
 """
 List available datasets for user.
        
 Returns:
 List of dataset names
 """
 if not self.session:
 raise ConnectionError("Not connected. Call connect() first.")
        
 # Get user's datasets
 datasets = self.session.data.list()
 return [ds.name for ds in datasets]
    
 def get_dataset_info(self, dataset_name: str) -> Dict:
 """
 Get information about a dataset.
        
 Returns:
 Dict with dataset metadata
 """
 dataset = self.session.open_dataset(dataset_name)
        
 info = {
 'name': dataset.name,
 'n_channels': len(dataset.ch_labels),
 'channel_labels': dataset.ch_labels,
 'sampling_frequency': dataset.sample_rate,
 'duration': dataset.duration / 1e6, # Convert to seconds
 'n_samples': dataset.duration,
 'patient_id': dataset.patient_id if hasattr(dataset, 'patient_id') else None
 }
        
 dataset.close()
 return info
    
 def get_channel_info(self, dataset_name: str) -> pd.DataFrame:
 """
 Get channel information in BIDS-compatible format.
        
 Returns:
 DataFrame with columns: name, type, units, low_cutoff, high_cutoff
 """
 dataset = self.session.open_dataset(dataset_name)
        
 channels = []
 for i, label in enumerate(dataset.ch_labels):
 channels.append({
 'name': label,
 'type': 'ECOG', # Default for iEEG
 'units': 'µV',
 'sampling_frequency': dataset.sample_rate,
 'status': 'good'
 })
        
 dataset.close()
 return pd.DataFrame(channels)
    
 def get_electrode_positions(self, dataset_name: str) -> Optional[pd.DataFrame]:
 """
 Get electrode positions if available.
        
 Returns:
 DataFrame with electrode positions or None
 """
 dataset = self.session.open_dataset(dataset_name)
        
 # Check if electrode coordinates are available
 if hasattr(dataset, 'electrode_coordinates'):
 coords = dataset.electrode_coordinates
            
 electrodes = []
 for i, label in enumerate(dataset.ch_labels):
 if i < len(coords):
 electrodes.append({
 'name': label,
 'x': coords[i][0],
 'y': coords[i][1],
 'z': coords[i][2]
 })
            
 dataset.close()
 return pd.DataFrame(electrodes)
        
 dataset.close()
 return None
    
 def download_dataset(self, dataset_name: str, output_dir: str,
 bids_format: bool = True,
 progress_callback=None) -> Path:
 """
 Download dataset from IEEG.org in BIDS format.
        
 Args:
 dataset_name: Name of dataset on IEEG.org
 output_dir: Output directory for download
 bids_format: Convert to BIDS structure
 progress_callback: Optional callback for progress
            
 Returns:
 Path to downloaded/converted data
 """
 output_dir = Path(output_dir)
 output_dir.mkdir(parents=True, exist_ok=True)
        
 if progress_callback:
 progress_callback("Opening dataset...")
        
 dataset = self.session.open_dataset(dataset_name)
        
 if bids_format:
 # Create BIDS structure
 subject_id = dataset.patient_id if hasattr(dataset, 'patient_id') else '001'
 subject_dir = output_dir / f"sub-{subject_id}" / "ieeg"
 subject_dir.mkdir(parents=True, exist_ok=True)
            
 # Download data
 if progress_callback:
 progress_callback("Downloading iEEG data...")
            
 # Save as NWB (native IEEG.org format)
 nwb_file = subject_dir / f"sub-{subject_id}_ieeg.nwb"
 # ... download logic using ieeg-python package
            
 # Create BIDS sidecar files
 if progress_callback:
 progress_callback("Creating BIDS metadata...")
            
 # _ieeg.json
 json_file = subject_dir / f"sub-{subject_id}_ieeg.json"
 metadata = {
 'TaskName': 'clinical',
 'SamplingFrequency': dataset.sample_rate,
 'PowerLineFrequency': 60,
 'RecordingDuration': dataset.duration / 1e6,
 'iEEGReference': 'bipolar',
 'ECOGChannelCount': len(dataset.ch_labels)
 }
 import json
 with open(json_file, 'w') as f:
 json.dump(metadata, f, indent=2)
            
 # _channels.tsv
 channels_file = subject_dir / f"sub-{subject_id}_channels.tsv"
 channels_df = self.get_channel_info(dataset_name)
 channels_df.to_csv(channels_file, sep='\t', index=False)
            
 # _electrodes.tsv
 electrodes_file = subject_dir / f"sub-{subject_id}_electrodes.tsv"
 electrodes_df = self.get_electrode_positions(dataset_name)
 if electrodes_df is not None:
 electrodes_df.to_csv(electrodes_file, sep='\t', index=False)
            
 # _coordsystem.json
 coordsystem_file = subject_dir / f"sub-{subject_id}_coordsystem.json"
 coordsystem = {
 'iEEGCoordinateSystem': 'ACPC',
 'iEEGCoordinateUnits': 'mm'
 }
 with open(coordsystem_file, 'w') as f:
 json.dump(coordsystem, f, indent=2)
            
 if progress_callback:
 progress_callback("Download complete!")
            
 dataset.close()
 return subject_dir
        
 else:
 # Download in native format
 # ... raw download logic
 dataset.close()
 return output_dir
```

### 6.2 OpenNeuro EEG/iEEG Enhancement

**File:** `src/openneuro_agent.py`

**Add EEG/iEEG dataset detection:**

```python
def get_dataset_modalities(self, dataset_id: str) -> List[str]:
 """
 Detect modalities in OpenNeuro dataset.
    
 Returns:
 List of modalities: ['anat', 'func', 'eeg', 'ieeg', etc.]
 """
 modalities = set()
    
 # Check dataset description
 url = f"{self.base_url}/datasets/{dataset_id}"
 response = requests.get(url)
    
 if response.status_code == 200:
 data = response.json()
        
 # Parse modalities from file list
 if 'files' in data:
 for file_info in data['files']:
 path = file_info.get('filename', '')
                
 # Detect modality from path
 if '/anat/' in path:
 modalities.add('anat')
 elif '/func/' in path:
 modalities.add('func')
 elif '/dwi/' in path:
 modalities.add('dwi')
 elif '/eeg/' in path:
 modalities.add('eeg')
 elif '/ieeg/' in path:
 modalities.add('ieeg')
 elif '/meg/' in path:
 modalities.add('meg')
    
 return list(modalities)

def is_eeg_dataset(self, dataset_id: str) -> bool:
 """Check if dataset contains EEG/iEEG data."""
 modalities = self.get_dataset_modalities(dataset_id)
 return 'eeg' in modalities or 'ieeg' in modalities
```

---

## 7. Database Schema Updates

### 7.1 Scan Metadata Table

**File:** `src/database.py`

**Add EEG-specific columns:**

```sql
-- New columns for scans table
ALTER TABLE scans ADD COLUMN sampling_frequency REAL;
ALTER TABLE scans ADD COLUMN channel_count INTEGER;
ALTER TABLE scans ADD COLUMN recording_duration REAL;
ALTER TABLE scans ADD COLUMN task_name TEXT;

-- New table for EEG channels
CREATE TABLE IF NOT EXISTS eeg_channels (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 scan_id INTEGER NOT NULL,
 channel_name TEXT NOT NULL,
 channel_type TEXT,
 units TEXT,
 sampling_frequency REAL,
 status TEXT,
 FOREIGN KEY (scan_id) REFERENCES scans(id)
);

-- New table for iEEG electrodes
CREATE TABLE IF NOT EXISTS ieeg_electrodes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 scan_id INTEGER NOT NULL,
 electrode_name TEXT NOT NULL,
 x REAL,
 y REAL,
 z REAL,
 size REAL,
 material TEXT,
 manufacturer TEXT,
 hemisphere TEXT,
 region TEXT,
 FOREIGN KEY (scan_id) REFERENCES scans(id)
);
```

**Python migration:**

```python
def migrate_v2_eeg_support(db_path: str):
 """Migration for EEG/iEEG support."""
 conn = sqlite3.connect(db_path)
 cursor = conn.cursor()
    
 # Add new columns to scans table
 new_columns = [
 'sampling_frequency REAL',
 'channel_count INTEGER',
 'recording_duration REAL',
 'task_name TEXT'
 ]
    
 for col in new_columns:
 try:
 cursor.execute(f"ALTER TABLE scans ADD COLUMN {col}")
 except sqlite3.OperationalError:
 pass # Column already exists
    
 # Create eeg_channels table
 cursor.execute('''
 CREATE TABLE IF NOT EXISTS eeg_channels (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 scan_id INTEGER NOT NULL,
 channel_name TEXT NOT NULL,
 channel_type TEXT,
 units TEXT,
 sampling_frequency REAL,
 status TEXT,
 FOREIGN KEY (scan_id) REFERENCES scans(id)
 )
 ''')
    
 # Create ieeg_electrodes table
 cursor.execute('''
 CREATE TABLE IF NOT EXISTS ieeg_electrodes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 scan_id INTEGER NOT NULL,
 electrode_name TEXT NOT NULL,
 x REAL,
 y REAL,
 z REAL,
 size REAL,
 material TEXT,
 manufacturer TEXT,
 hemisphere TEXT,
 region TEXT,
 FOREIGN KEY (scan_id) REFERENCES scans(id)
 )
 ''')
    
 conn.commit()
 conn.close()
```

---

## 8. UI/UX Updates

### 8.1 Platform Selection

**File:** `app.py` - Setup page

Add IEEG.org option:

```python
platform = st.radio(
 "Choose data platform",
 options=['pennsieve', 'openneuro', 'ieeg'],
 format_func=lambda x: {
 'pennsieve': 'Pennsieve (Private datasets, MRI upload support)',
 'openneuro': 'OpenNeuro (Public MRI/EEG/iEEG datasets)',
 'ieeg': 'IEEG.org (Intracranial EEG data)'
 }[x],
 key="platform_selection"
)

if platform == 'ieeg':
 st.info("**IEEG.org**: Clinical iEEG recordings from epilepsy patients")
    
 # Credentials
 username = st.text_input("IEEG.org Username", key="ieeg_username")
 password = st.text_input("IEEG.org Password", type="password", key="ieeg_password")
```

### 8.2 Browse Page - Modality Filter

Add modality filter:

```python
# Modality filter
modalities = st.multiselect(
 "Filter by Modality",
 options=['anat', 'func', 'dwi', 'eeg', 'ieeg', 'meg'],
 format_func=lambda x: {
 'anat': 'Anatomical MRI',
 'func': 'Functional MRI',
 'dwi': 'Diffusion MRI',
 'eeg': 'Scalp EEG',
 'ieeg': 'Intracranial EEG',
 'meg': 'MEG'
 }[x],
 default=['anat']
)
```

### 8.3 Subject Detail View

Show modality-specific info:

```python
# In subject details
for scan in scans:
 if scan['modality'] in ['eeg', 'ieeg']:
 st.markdown(f"**{scan['suffix'].upper()}**")
        
 col1, col2, col3 = st.columns(3)
 with col1:
 st.metric("Channels", scan.get('channel_count', 'N/A'))
 with col2:
 st.metric("Sampling Rate", f"{scan.get('sampling_frequency', 'N/A')} Hz")
 with col3:
 st.metric("Duration", f"{scan.get('recording_duration', 'N/A'):.1f}s")
        
 # For iEEG, show electrode coverage
 if scan['modality'] == 'ieeg' and scan.get('electrode_info'):
 st.write("Electrode Coverage:", ', '.join(scan['electrode_info']['regions']))
```

### 8.4 QC Dashboard

Add EEG/iEEG-specific QC:

```python
# QC results display
if scan['modality'] in ['eeg', 'ieeg']:
 qc_checks = [
 ('File Readable', scan['qc_results']['file_readable']),
 ('Channels Valid', scan['qc_results']['channels_valid']),
 ('Sampling Rate OK', scan['qc_results']['sampling_rate_ok'])
 ]
    
 if scan['modality'] == 'ieeg':
 qc_checks.append(('Electrodes Valid', scan['qc_results']['electrodes_valid']))
 qc_checks.append(('Coordinates Valid', scan['qc_results']['coordinates_valid']))
    
 for check_name, status in qc_checks:
 col1, col2 = st.columns([3, 1])
 with col1:
 st.write(check_name)
 with col2:
 if status:
 st.success("Pass")
 else:
 st.error("Fail")
```

---

## 9. Dependencies

### 9.1 New Python Packages

**Add to `requirements.txt`:**

```txt
# Existing dependencies
streamlit>=1.28.0
pybids>=0.16.0
pandas>=2.0.0
requests>=2.31.0
python-dotenv>=1.0.0
boto3>=1.28.0 # For OpenNeuro

# NEW: EEG/iEEG support
mne>=1.5.0 # EEG/MEG/iEEG data I/O and processing
mne-bids>=0.14.0 # BIDS-EEG utilities
pynwb>=2.5.0 # NWB format (for iEEG.org)
h5py>=3.10.0 # Required by pynwb
ieeg>=1.6.0 # IEEG.org API client
scipy>=1.11.0 # Signal processing (if needed)
```

### 9.2 Installation Script Update

**File:** `bin/explorer.py` or `requirements.txt`

Add conditional install for EEG support:

```bash
# Full install (with EEG support)
pip install -r requirements.txt

# Minimal install (MRI only)
pip install -r requirements-minimal.txt

# requirements-minimal.txt (without EEG deps)
# ... existing MRI-only deps
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

**File:** `tests/test_eeg_handler.py` (NEW)

```python
"""Tests for EEG/iEEG handler."""

import pytest
from pathlib import Path
from src.eeg_handler import EEGHandler, IEEGHandler
import mne
import numpy as np


@pytest.fixture
def sample_eeg_file(tmp_path):
 """Create a sample EEG file for testing."""
 # Create synthetic EEG data using MNE
 sfreq = 1000 # Hz
 duration = 60 # seconds
 n_channels = 64
    
 # Generate random data
 data = np.random.randn(n_channels, sfreq * duration) * 1e-6 # µV
    
 # Create channel names
 ch_names = [f'EEG{i+1:03d}' for i in range(n_channels)]
 ch_types = ['eeg'] * n_channels
    
 # Create MNE info
 info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=ch_types)
    
 # Create Raw object
 raw = mne.io.RawArray(data, info)
    
 # Save as EDF
 edf_file = tmp_path / "test_eeg.edf"
 raw.export(edf_file, fmt='edf')
    
 return edf_file


def test_eeg_handler_read_file(sample_eeg_file):
 """Test reading EEG file."""
 handler = EEGHandler()
 raw = handler.read_eeg_file(str(sample_eeg_file))
    
 assert raw is not None
 assert len(raw.ch_names) == 64
 assert raw.info['sfreq'] == 1000


def test_eeg_handler_get_info(sample_eeg_file):
 """Test getting EEG file info."""
 handler = EEGHandler()
 info = handler.get_basic_info(str(sample_eeg_file))
    
 assert info['n_channels'] == 64
 assert info['sampling_frequency'] == 1000
 assert info['duration'] > 0


def test_eeg_qc_flat_channel(tmp_path):
 """Test QC detection of flat channel."""
 handler = EEGHandler()
    
 # Create data with one flat channel
 sfreq = 1000
 duration = 10
 n_channels = 8
    
 data = np.random.randn(n_channels, sfreq * duration) * 1e-6
 data[0, :] = 0 # Flat channel
    
 ch_names = [f'EEG{i+1:03d}' for i in range(n_channels)]
 info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=['eeg']*n_channels)
 raw = mne.io.RawArray(data, info)
    
 edf_file = tmp_path / "flat_channel.edf"
 raw.export(edf_file, fmt='edf')
    
 qc_results = handler.check_data_quality(str(edf_file))
    
 assert any('flat channel' in w.lower() for w in qc_results['warnings'])


@pytest.fixture
def sample_ieeg_files(tmp_path):
 """Create sample iEEG files with electrodes."""
 # Create iEEG data
 sfreq = 2000
 duration = 30
 n_channels = 16
    
 data = np.random.randn(n_channels, sfreq * duration) * 1e-6
 ch_names = [f'LHH{i+1}' for i in range(n_channels)]
 info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=['ecog']*n_channels)
 raw = mne.io.RawArray(data, info)
    
 ieeg_dir = tmp_path / "ieeg"
 ieeg_dir.mkdir()
    
 ieeg_file = ieeg_dir / "sub-01_ieeg.edf"
 raw.export(ieeg_file, fmt='edf')
    
 # Create channels.tsv
 import pandas as pd
 channels_df = pd.DataFrame({
 'name': ch_names,
 'type': ['ECOG'] * n_channels,
 'units': ['µV'] * n_channels,
 'sampling_frequency': [sfreq] * n_channels,
 'status': ['good'] * n_channels
 })
 channels_file = ieeg_dir / "sub-01_channels.tsv"
 channels_df.to_csv(channels_file, sep='\t', index=False)
    
 # Create electrodes.tsv
 electrodes_df = pd.DataFrame({
 'name': ch_names,
 'x': np.linspace(-30, -20, n_channels),
 'y': np.linspace(-15, -10, n_channels),
 'z': np.linspace(-10, -5, n_channels),
 'size': [2.5] * n_channels,
 'material': ['Platinum'] * n_channels,
 'group': ['LeftHipp'] * n_channels
 })
 electrodes_file = ieeg_dir / "sub-01_electrodes.tsv"
 electrodes_df.to_csv(electrodes_file, sep='\t', index=False)
    
 return {
 'ieeg_file': ieeg_file,
 'channels_file': channels_file,
 'electrodes_file': electrodes_file
 }


def test_ieeg_handler_validate_electrodes(sample_ieeg_files):
 """Test iEEG electrode validation."""
 handler = IEEGHandler()
    
 is_valid, errors = handler.validate_electrodes_tsv(
 str(sample_ieeg_files['ieeg_file']),
 str(sample_ieeg_files['electrodes_file']),
 str(sample_ieeg_files['channels_file'])
 )
    
 assert is_valid
 assert len(errors) == 0


def test_ieeg_electrode_coverage(sample_ieeg_files):
 """Test electrode coverage analysis."""
 handler = IEEGHandler()
    
 coverage = handler.get_electrode_coverage(
 str(sample_ieeg_files['electrodes_file'])
 )
    
 assert coverage['total_electrodes'] == 16
 assert 'LeftHipp' in coverage['regions']
 assert coverage['hemisphere'] == 'left'
```

### 10.2 Integration Tests

**File:** `tests/test_eeg_integration.py` (NEW)

```python
"""Integration tests for EEG/iEEG workflow."""

import pytest
from pathlib import Path
from src.bids_loader import BIDSLoader
from src.automated_qc import AutomatedQC
from src.database import Database


def create_test_eeg_dataset(tmp_path):
 """Create minimal BIDS-EEG dataset for testing."""
 # Create BIDS structure
 dataset_root = tmp_path / "test_eeg_dataset"
 dataset_root.mkdir()
    
 # Create dataset_description.json
 import json
 with open(dataset_root / "dataset_description.json", 'w') as f:
 json.dump({
 "Name": "Test EEG Dataset",
 "BIDSVersion": "1.9.0",
 "DatasetType": "raw"
 }, f)
    
 # Create subject with EEG data
 subject_dir = dataset_root / "sub-001" / "eeg"
 subject_dir.mkdir(parents=True)
    
 # Create EEG file (using MNE)
 import mne
 import numpy as np
    
 sfreq = 1000
 n_channels = 32
 duration = 60
    
 data = np.random.randn(n_channels, sfreq * duration) * 1e-6
 ch_names = [f'EEG{i+1:03d}' for i in range(n_channels)]
 info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=['eeg']*n_channels)
 raw = mne.io.RawArray(data, info)
    
 eeg_file = subject_dir / "sub-001_task-rest_eeg.edf"
 raw.export(eeg_file, fmt='edf')
    
 # Create sidecar JSON
 with open(subject_dir / "sub-001_task-rest_eeg.json", 'w') as f:
 json.dump({
 "TaskName": "rest",
 "SamplingFrequency": sfreq,
 "PowerLineFrequency": 60,
 "EEGReference": "average",
 "EEGChannelCount": n_channels
 }, f)
    
 # Create channels.tsv
 import pandas as pd
 channels_df = pd.DataFrame({
 'name': ch_names,
 'type': ['EEG'] * n_channels,
 'units': ['µV'] * n_channels,
 'sampling_frequency': [sfreq] * n_channels,
 'status': ['good'] * n_channels
 })
 channels_df.to_csv(
 subject_dir / "sub-001_task-rest_channels.tsv",
 sep='\t', index=False
 )
    
 return dataset_root


@pytest.fixture
def eeg_dataset(tmp_path):
 """Fixture for test EEG dataset."""
 return create_test_eeg_dataset(tmp_path)


def test_load_eeg_dataset(eeg_dataset):
 """Test loading BIDS-EEG dataset."""
 loader = BIDSLoader(str(eeg_dataset), validate=False)
    
 subjects = loader.get_subjects()
 assert '001' in subjects
    
 modalities = loader.get_modalities(subject='001')
 assert 'eeg' in modalities


def test_get_eeg_scans(eeg_dataset):
 """Test getting EEG scans."""
 loader = BIDSLoader(str(eeg_dataset), validate=False)
    
 scans = loader.get_subject_scans('001', modality='eeg')
    
 assert len(scans) > 0
 assert scans[0]['modality'] == 'eeg'
 assert scans[0]['suffix'] == 'eeg'
 assert scans[0].get('sampling_frequency') == 1000
 assert scans[0].get('eeg_channel_count') == 32


def test_eeg_qc_workflow(eeg_dataset, tmp_path):
 """Test full QC workflow for EEG data."""
 # Load dataset
 loader = BIDSLoader(str(eeg_dataset), validate=False)
 scans = loader.get_subject_scans('001', modality='eeg')
    
 # Run QC
 qc = AutomatedQC(str(eeg_dataset))
 results = qc.validate_scan(scans[0])
    
 assert results['status'] in ['pass', 'warn']
 assert 'info' in results
 assert results['info']['n_channels'] == 32
 assert results['info']['sampling_frequency'] == 1000


def test_eeg_database_integration(eeg_dataset, tmp_path):
 """Test storing EEG scans in database."""
 db_path = tmp_path / "test.db"
 db = Database(str(db_path))
    
 # Add dataset
 db.add_dataset("test_eeg", "openneuro", str(eeg_dataset), "ds999999")
    
 # Load scans
 loader = BIDSLoader(str(eeg_dataset), validate=False)
 scans = loader.get_subject_scans('001', modality='eeg')
    
 # Add subject
 db.add_subject(1, '001')
    
 # Add scan with EEG metadata
 scan = scans[0]
 db.add_scan(
 dataset_id=1,
 subject_id='001',
 session=scan.get('session'),
 modality=scan['modality'],
 suffix=scan['suffix'],
 file_path=scan['file_path'],
 size=1000000,
 sampling_frequency=scan.get('sampling_frequency'),
 channel_count=scan.get('eeg_channel_count'),
 recording_duration=scan.get('recording_duration')
 )
    
 # Retrieve and verify
 stored_scans = db.get_subject_scans(1, '001')
 assert len(stored_scans) > 0
 assert stored_scans[0]['sampling_frequency'] == 1000
 assert stored_scans[0]['channel_count'] == 32
```

### 10.3 Manual Testing Checklist

**Phase 1: Basic EEG Support**
- [ ] Load BIDS-EEG dataset from OpenNeuro (e.g., ds002778)
- [ ] Browse subjects with EEG data
- [ ] View EEG file metadata (channels, sampling rate)
- [ ] Run automated QC on EEG files
- [ ] Download EEG dataset
- [ ] Export filtered EEG cohort

**Phase 2: iEEG Support**
- [ ] Load BIDS-iEEG dataset from OpenNeuro (e.g., ds003029)
- [ ] Browse subjects with iEEG data
- [ ] View electrode coverage information
- [ ] Validate electrodes.tsv matches channels
- [ ] Run automated QC on iEEG files
- [ ] Download iEEG dataset with electrode positions

**Phase 3: IEEG.org Integration**
- [ ] Connect to IEEG.org with credentials
- [ ] List available datasets
- [ ] Browse dataset metadata
- [ ] View channel and electrode information
- [ ] Download dataset in BIDS format
- [ ] Verify BIDS structure and metadata

---

## 11. Implementation Timeline

### Phase 1: Foundation (Weeks 1-2)
**Goal:** Basic EEG file support

**Tasks:**
- [ ] Install MNE-Python and dependencies
- [ ] Create `src/eeg_handler.py` with basic file reading
- [ ] Update `src/bids_loader.py` to support EEG extensions
- [ ] Add EEG modality detection
- [ ] Basic unit tests for EEG handler

**Deliverable:** Can load and read BIDS-EEG files

### Phase 2: Validation & QC (Weeks 3-4)
**Goal:** EEG-specific validation and QC

**Tasks:**
- [ ] Implement channels.tsv validation
- [ ] Add EEG-specific QC checks (flat channels, sampling rate)
- [ ] Update `src/automated_qc.py` for EEG support
- [ ] Update `src/bids_validator.py` for EEG modality
- [ ] Integration tests with BIDS-EEG datasets

**Deliverable:** Full QC workflow for EEG data

### Phase 3: iEEG Support (Weeks 5-6)
**Goal:** iEEG-specific features

**Tasks:**
- [ ] Implement `IEEGHandler` class
- [ ] Add electrodes.tsv validation
- [ ] Add electrode coverage analysis
- [ ] iEEG-specific QC checks
- [ ] Update UI for iEEG metadata display
- [ ] Tests with BIDS-iEEG datasets

**Deliverable:** Full iEEG support with electrode positions

### Phase 4: IEEG.org Integration (Weeks 7-8)
**Goal:** Connect to IEEG.org

**Tasks:**
- [ ] Install ieeg-python client
- [ ] Create `src/ieeg_client.py`
- [ ] Implement authentication
- [ ] Dataset browsing and metadata
- [ ] Download in BIDS format
- [ ] UI integration for IEEG.org platform
- [ ] End-to-end testing

**Deliverable:** Full IEEG.org platform integration

### Phase 5: Database & UI Polish (Weeks 9-10)
**Goal:** Production-ready EEG/iEEG support

**Tasks:**
- [ ] Database schema migration
- [ ] Store EEG metadata in database
- [ ] UI updates for modality filtering
- [ ] Subject detail view enhancements
- [ ] QC dashboard updates
- [ ] Documentation updates
- [ ] Performance optimization

**Deliverable:** Production-ready multi-modal BIDSHub

### Phase 6: Testing & Documentation (Weeks 11-12)
**Goal:** Testing and release

**Tasks:**
- [ ] Comprehensive integration testing
- [ ] User acceptance testing
- [ ] Documentation: user guide for EEG/iEEG
- [ ] Documentation: IEEG.org setup guide
- [ ] Performance benchmarking
- [ ] Bug fixes and polish

**Deliverable:** Release BIDSHub v2.0 with EEG/iEEG support

---

## 12. Performance Considerations

### 12.1 EEG File Sizes

**Typical Sizes:**
- Scalp EEG (64 channels, 1 hour, 1000 Hz): ~100-200 MB
- iEEG (128 channels, 1 hour, 2000 Hz): ~500 MB - 1 GB
- Long-term monitoring (24 hours): 5-20 GB

**Optimization:**
- Don't preload data by default (`preload=False`)
- Stream data for QC checks
- Use MNE's lazy loading capabilities
- Consider chunked processing for large files

### 12.2 Memory Management

```python
def process_large_eeg_file(file_path: str, chunk_duration: int = 60):
 """Process large EEG file in chunks."""
 raw = mne.io.read_raw_edf(file_path, preload=False)
    
 # Process in 60-second chunks
 n_chunks = int(np.ceil(raw.n_times / (chunk_duration * raw.info['sfreq'])))
    
 for i in range(n_chunks):
 start = i * chunk_duration * raw.info['sfreq']
 stop = min((i + 1) * chunk_duration * raw.info['sfreq'], raw.n_times)
        
 # Load only this chunk
 data_chunk = raw[:, start:stop][0]
        
 # Process chunk
 # ... QC checks, etc.
        
 # Free memory
 del data_chunk
```

### 12.3 IEEG.org Download Optimization

- Use streaming for large datasets
- Parallel channel downloads if supported
- Checkpoint downloads for resume capability
- Compress intermediate data

---

## 13. Documentation Updates

### 13.1 User Documentation

**New Pages:**
- `docs/EEG_IEEG_GUIDE.md` - Guide to using EEG/iEEG features
- `docs/IEEG_ORG_SETUP.md` - How to connect to IEEG.org
- `docs/MODALITY_COMPARISON.md` - MRI vs EEG/iEEG workflows

**Updates:**
- `README.md` - Add EEG/iEEG support to features
- `QUICKSTART.md` - Add EEG/iEEG example workflows
- `APP_SUMMARY.md` - Update with new modalities

### 13.2 API Documentation

**New Modules:**
- `src/eeg_handler.py` - Full docstrings
- `src/ieeg_client.py` - API documentation
- Update `src/bids_loader.py` docstrings

### 13.3 Developer Documentation

**New:**
- `BIDS_EEG_IEEG_TECHNICAL_PLAN.md` (this document)
- `docs/ADDING_NEW_MODALITIES.md` - Guide for future modalities (MEG, PET, etc.)

---

## 14. Future Enhancements (Post-v2.0)

### Phase 7: MEG Support
- Add MEG file formats (`.fif`, `.ds`, `.sqd`)
- MEG-specific validation and QC
- Sensor layout visualization

### Phase 8: Multi-Modal Visualization
- Joint MRI + electrode visualization
- EEG topographic maps
- Source localization display

### Phase 9: Signal Processing Features
- Basic filtering in browser
- Artifact detection
- Power spectral density plots

### Phase 10: Advanced Cohort Export
- Export with preprocessing pipelines
- Integration with MNE-BIDS-Pipeline
- Automated analysis workflows

---

## 15. Risk Assessment & Mitigation

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MNE dependency conflicts | Medium | High | Use virtual environment, pin versions |
| IEEG.org API changes | Low | Medium | Abstract client, version checking |
| Large file performance | High | Medium | Streaming, chunking, lazy loading |
| NWB format complexity | Medium | High | Use pynwb, extensive testing |
| Memory issues with large files | High | High | Chunked processing, monitoring |

### Compatibility Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| BIDS-EEG spec changes | Low | Medium | Track BIDS spec updates |
| Breaking changes in dependencies | Medium | High | Pin versions, regular updates |
| Platform API changes | Low | High | Version API calls, graceful degradation |

### User Experience Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Confusion between modalities | Medium | Medium | Clear UI labels, tooltips |
| Slow EEG loading | Medium | Medium | Progress indicators, optimization |
| Complex setup for IEEG.org | High | Medium | Step-by-step wizard, documentation |

---

## 16. Success Metrics

### Functional Metrics
- [ ] Can load and validate 100% of BIDS-EEG datasets on OpenNeuro
- [ ] Can load and validate 100% of BIDS-iEEG datasets on OpenNeuro
- [ ] Can successfully connect to and browse IEEG.org datasets
- [ ] EEG QC checks complete in <5 seconds per file
- [ ] Zero data corruption in downloads

### Performance Metrics
- [ ] EEG file loading: <3 seconds for metadata
- [ ] QC checks: <10 seconds for 1-hour recording
- [ ] Database queries: <100ms for EEG metadata
- [ ] Download speed: >5 MB/s for IEEG.org

### User Experience Metrics
- [ ] Setup wizard completion rate: >80%
- [ ] User documentation completeness: 100%
- [ ] Bug reports related to EEG: <5 per month
- [ ] User feedback score: >4/5

---

## 17. Rollout Strategy

### Internal Testing (Weeks 11-12)
- Developer testing with known datasets
- Fix critical bugs
- Performance optimization

### Beta Release (Week 13-14)
- Limited release to select users
- Collect feedback
- Monitor for issues

### Production Release (Week 15)
- Full release as BIDSHub v2.0
- Announcement to user community
- Monitoring and support

### Post-Release (Week 16+)
- Bug fixes and patches
- Feature refinements based on feedback
- Plan Phase 7+ enhancements

---

## 18. Conclusion

This technical plan provides a comprehensive roadmap for adding BIDS-EEG/iEEG support to BIDSHub. The phased approach ensures:

1. **Solid Foundation:** Build on existing MRI infrastructure
2. **Incremental Delivery:** EEG first, then iEEG, then IEEG.org
3. **Quality Focus:** Extensive testing at each phase
4. **User-Centric:** Clear documentation and intuitive UI

**Estimated Timeline:** 15 weeks (3.5 months) 
**Estimated Effort:** 300-400 hours development + testing

**Key Differentiators:**
- Only tool supporting MRI + EEG + iEEG in unified BIDS platform
- IEEG.org integration unique in BIDS ecosystem
- Production-ready QC for electrophysiology data

This expansion will position BIDSHub as a comprehensive multi-modal BIDS platform for clinical neuroscience research, particularly valuable for epilepsy and TBI studies that combine imaging and electrophysiology.

---

## Appendix A: Example BIDS-EEG Dataset Structure

```
ds002778/ # OpenNeuro EEG dataset example
 dataset_description.json
 participants.tsv
 participants.json
 task-auditoryoddball_eeg.json # Task metadata
 sub-001/
 sub-001_scans.tsv
 eeg/
 sub-001_task-auditoryoddball_eeg.set # EEGLAB format
 sub-001_task-auditoryoddball_eeg.fdt
 sub-001_task-auditoryoddball_eeg.json # Required
 sub-001_task-auditoryoddball_channels.tsv # Required
 sub-001_task-auditoryoddball_events.tsv
 sub-001_task-auditoryoddball_coordsystem.json
 sub-002/
 eeg/
 sub-002_task-auditoryoddball_eeg.set
 sub-002_task-auditoryoddball_eeg.fdt
 sub-002_task-auditoryoddball_eeg.json
 sub-002_task-auditoryoddball_channels.tsv
 sub-002_task-auditoryoddball_events.tsv
 sub-002_task-auditoryoddball_coordsystem.json
```

## Appendix B: Example BIDS-iEEG Dataset Structure

```
ds003029/ # OpenNeuro iEEG dataset example
 dataset_description.json
 participants.tsv
 participants.json
 sub-01/
 ses-presurgery/
 anat/
 sub-01_ses-presurgery_T1w.nii.gz # Anatomical MRI
 sub-01_ses-presurgery_T1w.json
 ieeg/
 sub-01_ses-presurgery_task-seizure_run-01_ieeg.vhdr
 sub-01_ses-presurgery_task-seizure_run-01_ieeg.eeg
 sub-01_ses-presurgery_task-seizure_run-01_ieeg.vmrk
 sub-01_ses-presurgery_task-seizure_run-01_ieeg.json # Required
 sub-01_ses-presurgery_task-seizure_run-01_channels.tsv # Required
 sub-01_ses-presurgery_task-seizure_run-01_events.tsv
 sub-01_ses-presurgery_task-seizure_run-01_electrodes.tsv # Required
 sub-01_ses-presurgery_task-seizure_run-01_coordsystem.json # Required
```

## Appendix C: Useful BIDS-EEG/iEEG Resources

**Official Documentation:**
- BIDS Specification (EEG): https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/03-electroencephalography.html
- BIDS Specification (iEEG): https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/04-intracranial-electroencephalography.html
- MNE-BIDS: https://mne.tools/mne-bids/
- MNE-Python: https://mne.tools/

**Example Datasets:**
- OpenNeuro EEG datasets: https://openneuro.org/search/modality/eeg
- OpenNeuro iEEG datasets: https://openneuro.org/search/modality/ieeg
- IEEG.org portal: https://www.ieeg.org/

**Python Packages:**
- MNE-Python: https://github.com/mne-tools/mne-python
- MNE-BIDS: https://github.com/mne-tools/mne-bids
- pynwb: https://github.com/NeurodataWithoutBorders/pynwb
- ieeg-python: https://github.com/ieeg-portal/ieegpy

---

**Document Control:**
- **Author:** BIDSHub Development Team
- **Version:** 1.0
- **Last Updated:** February 2026
- **Status:** Draft - Pending Implementation
- **Next Review:** Before Phase 1 kickoff
