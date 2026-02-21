# Dual Platform Support: Pennsieve + OpenNeuro

**Status**: ✅ Fully Implemented  
**Version**: v1.0

---

## Overview

Data Explorer now supports **TWO cloud platforms**:

| Platform | Type | Datasets | Upload | Use Case |
|----------|------|----------|--------|----------|
| **🔐 Pennsieve** | Private | Your research data | ✅ Yes | Active research projects |
| **🌍 OpenNeuro** | Public | 1000+ shared datasets | ❌ No | Public data access |

---

## Platform Selection Flow

### Setup Page
```
┌─────────────────────────────────────────────────┐
│  Platform Selection                             │
├─────────────────────────────────────────────────┤
│  Choose data platform:                          │
│                                                 │
│  ⚫ 🔐 Pennsieve (Private datasets, upload)     │
│  ⚪ 🌍 OpenNeuro (Public datasets, read-only)   │
│                                                 │
│  ℹ️ Pennsieve: Private research datasets        │
│     with upload/download                        │
└─────────────────────────────────────────────────┘
```

---

## Pennsieve Configuration

### When Selected:
```
BIDS Dataset Configuration
├─ BIDS Directory Path: /path/to/local/bids

Pennsieve Configuration
├─ Pennsieve Dataset Name: TrackTBI
├─ Pennsieve API Key: ••••••••
└─ Pennsieve API Secret: ••••••••

[Initialize Dataset]
```

### Features:
- ✅ Download files from your dataset
- ✅ Upload processed/derived data back
- ✅ Private, secure access
- ✅ Full read-write permissions
- ✅ Queue-based downloads with progress
- ✅ Batch uploads

---

## OpenNeuro Configuration

### When Selected:
```
BIDS Dataset Configuration
├─ BIDS Directory Path: /path/to/local/bids

OpenNeuro Configuration
├─ OpenNeuro Dataset ID: ds000246
├─ Browse datasets at openneuro.org
└─ API Token (optional): ••••••• (only for private)

[Initialize Dataset]
```

### Features:
- ✅ Download from 1000+ public datasets
- ✅ Free access, no credentials needed (for public)
- ✅ Subject-based downloads (efficient)
- ❌ Upload NOT supported (read-only)
- ✅ Optional API token for private datasets
- ✅ Same UI/workflow as Pennsieve

---

## Download Manager Behavior

### Pennsieve Mode:
```
Download Manager
├─ 🎯 Filter by Metadata
│  └─ Age, Sex, Diagnosis filters
│
├─ Storage Estimation
│  └─ Queued Items, Total Size, Available Space
│
├─ Quick Select
│  ├─ [Select Filtered Subjects]
│  └─ [Select Complete (Filtered)]
│
├─ Download Queue
│  └─ File-based queue (individual files)
│
├─ Controls
│  └─ [Start Downloads] → Uses Pennsieve Agent
│
└─ Upload to Pennsieve ⬆️
   ├─ File uploader
   ├─ Remote path input
   └─ [Upload Files] button
```

### OpenNeuro Mode:
```
Download Manager
├─ 🎯 Filter by Metadata
│  └─ Age, Sex, Diagnosis filters
│
├─ Storage Estimation
│  └─ Queued Items, Total Size, Available Space
│
├─ Quick Select
│  ├─ [Select Filtered Subjects]
│  └─ [Select Complete (Filtered)]
│
├─ Download Queue
│  └─ Subject-based queue (grouped by subject)
│
├─ Controls
│  └─ [Start Downloads] → Uses OpenNeuro Agent
│
└─ 📖 OpenNeuro is read-only. Upload not supported.
```

**Key Difference**: Upload section only appears for Pennsieve

---

## Backend Architecture

### Agent Abstraction

Both platforms use similar agent pattern:

```python
# Pennsieve Agent
class PennsieveAgent:
    def map_dataset()        # Create stub structure
    def pull_file()          # Download single file
    def batch_pull()         # Download multiple files
    def upload_file()        # Upload single file ✅
    def batch_upload()       # Upload multiple files ✅

# OpenNeuro Agent  
class OpenNeuroAgent:
    def download_dataset()   # Download entire/filtered dataset
    def download_subject()   # Download single subject
    def download_subjects_batch()  # Download multiple subjects
    # No upload methods ❌
```

### Download Execution

```python
def execute_downloads(download_manager, database):
    """Route to appropriate platform agent."""
    
    platform = st.session_state.platform
    
    if platform == 'pennsieve':
        execute_pennsieve_downloads()  # File-by-file with pennsieve CLI
    else:
        execute_openneuro_downloads()  # Subject-by-subject with openneuro-py
```

---

## Workflow Comparison

### Pennsieve Workflow
```
1. User Setup:
   - Select "Pennsieve" platform
   - Enter dataset name (e.g., "TrackTBI")
   - Enter API credentials
   - Initialize

2. Browse & Filter:
   - View subjects in dataset
   - Apply metadata filters (age, sex, etc.)
   - Preview filtered results

3. Download:
   - Add subjects to queue
   - Queue shows individual files
   - Click "Start Downloads"
   - Files downloaded one-by-one with `pennsieve map pull`

4. Upload (Optional):
   - Go to Download Manager
   - Upload processed files
   - Files pushed to "derivatives/" folder
```

### OpenNeuro Workflow
```
1. User Setup:
   - Select "OpenNeuro" platform
   - Enter dataset ID (e.g., "ds000246")
   - Browse openneuro.org to find datasets
   - Initialize (no credentials needed)

2. Browse & Filter:
   - View subjects in dataset
   - Apply metadata filters
   - Preview filtered results

3. Download:
   - Add subjects to queue
   - Queue groups by subject
   - Click "Start Downloads"
   - Subjects downloaded with `openneuro.download()`

4. Upload:
   - ❌ Not available (read-only platform)
   - Shows message: "OpenNeuro is read-only"
```

---

## Use Cases

### When to Use Pennsieve:
- ✅ Your own research data
- ✅ Need to upload processed results
- ✅ Private/sensitive data
- ✅ Collaborative projects with access control
- ✅ Active data collection (ongoing studies)

### When to Use OpenNeuro:
- ✅ Exploratory analysis on public data
- ✅ Replication studies
- ✅ Method development/testing
- ✅ Teaching/training (using example datasets)
- ✅ Meta-analysis across multiple public datasets
- ✅ No credentials available

---

## Dependencies

### requirements.txt
```
# Cloud Platform Integration
pennsieve>=7.0.0          # For Pennsieve datasets
openneuro-py>=2026.1.0    # For OpenNeuro datasets
```

### Installation
```bash
pip install -r requirements.txt
```

---

## Technical Implementation

### Files Created:
1. `src/pennsieve_agent.py` (343 lines) - Pennsieve CLI wrapper
2. `src/openneuro_agent.py` (183 lines) - OpenNeuro Python client wrapper

### Files Modified:
1. `app.py`:
   - Added platform selection in `init_session_state()`
   - Modified `page_setup()` with platform radio buttons
   - Created `execute_downloads()` router function
   - Split into `execute_pennsieve_downloads()` and `execute_openneuro_downloads()`
   - Conditional upload UI (Pennsieve only)
   - Updated sidebar to show active platform

2. `requirements.txt`:
   - Added `openneuro-py>=2026.1.0`

---

## Platform Detection

### In Sidebar:
```
Data Explorer
─────────────
Platform: 🔐 Pennsieve
Dataset: TrackTBI
```

OR

```
Data Explorer
─────────────
Platform: 🌍 Openneuro
Dataset: ds000246
```

---

## Future Enhancements

### Multi-Platform Features (v2.0+):
1. **Unified Search**: Search across Pennsieve + OpenNeuro simultaneously
2. **Cross-Platform Sync**: Download from OpenNeuro, process, upload to Pennsieve
3. **Comparative Analysis**: Compare your data (Pennsieve) vs public benchmarks (OpenNeuro)
4. **Platform Migration**: Export from one platform, import to another

### Additional Platforms (v2.5+):
- Flywheel integration
- DANDI archive support
- XNAT connectivity
- Custom S3/cloud storage

---

## Summary

**What You Can Do Now:**

✅ **Pennsieve**:
- Download your private datasets
- Upload processed results
- Full bidirectional sync
- Metadata filtering
- QC tracking

✅ **OpenNeuro**:
- Download public datasets
- No credentials needed
- Same filtering/browsing UI
- Same QC workflow
- Read-only (no upload)

**Both platforms** share the same:
- Subject browser
- Metadata filtering
- QC dashboard (automated + manual)
- Download queue management
- Progress tracking
- Database for local tracking
