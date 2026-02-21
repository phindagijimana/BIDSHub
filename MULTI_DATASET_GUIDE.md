# Multi-Dataset Support Guide (v1.5+)

## Overview

Data Explorer v1.5+ introduces multi-dataset support, enabling you to connect to 2-3 datasets simultaneously from Pennsieve and/or OpenNeuro. This guide covers setup, usage, and best practices for working with multiple datasets.

## What's New in v1.5

### Key Features

- **Multiple Dataset Connections**: Connect to up to 3 datasets simultaneously
- **Unified Subject Browser**: View and search subjects from all datasets in one interface
- **Cross-Dataset Filtering**: Apply metadata filters across multiple datasets
- **Unified Download Queue**: Download from multiple datasets in a single queue
- **Platform Routing**: Automatic routing of downloads to the correct platform agent (Pennsieve or OpenNeuro)
- **Dataset Management**: Easy-to-use interface for adding, editing, and removing datasets

### Architecture Changes

**v1.0 (Single Dataset)**:
```
Setup → 1 Dataset → Browse Subjects → Download
```

**v1.5 (Multi-Dataset)**:
```
Setup → N Datasets → Browse ALL Subjects → Unified Download Queue → Route to Correct Agent
```

## Database Schema Changes

### New `datasets` Table

```sql
CREATE TABLE datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL,  -- 'pennsieve' or 'openneuro'
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    dataset_id_external TEXT,  -- Pennsieve name or OpenNeuro ID
    root_path TEXT,
    status TEXT DEFAULT 'active',
    created_date TIMESTAMP,
    last_sync_date TIMESTAMP
);
```

### Modified Tables

All dataset-specific tables now include a `dataset_id` foreign key:

- `subjects` table: Added `dataset_id`, `local_subject_id`
- `scans` table: Added `dataset_id`
- `download_queue` table: Added `dataset_id`

## Getting Started

### Migration from v1.0

If you're upgrading from v1.0, run the migration script to preserve your existing data:

```bash
python scripts/migrate_to_multi_dataset.py data/tracktbi.db
```

**What the migration does**:
1. Creates `datasets` table
2. Creates a default dataset from your existing data
3. Adds `dataset_id` columns to existing tables
4. Migrates all existing subjects and scans to the default dataset
5. Creates backup of your database before making changes

### Adding Your First Dataset

1. Launch the app: `./explorer` or `streamlit run app.py`
2. Navigate to **Manage Datasets** from the sidebar
3. Click **Add New Dataset**
4. Fill in the form:
   - **Dataset Name**: Unique name (e.g., "TrackTBI Main")
   - **Platform**: Choose Pennsieve or OpenNeuro
   - **Credentials** (if Pennsieve): API key and secret
   - **Dataset ID**: Pennsieve dataset name or OpenNeuro ID (e.g., "ds000246")
   - **Local Working Directory**: Where files will be downloaded

## Managing Multiple Datasets

### Adding Additional Datasets

1. Go to **Manage Datasets** page
2. Click **Add New Dataset**
3. Configure the second dataset
4. The app supports up to 3 datasets in v1.5

### Dataset Status

Each dataset has a status:
- **Active**: Dataset is available for browsing and downloading
- **Inactive**: Dataset is temporarily disabled
- **Error**: Dataset encountered an error

Toggle status using the **Activate/Deactivate** button in the dataset card.

### Removing Datasets

**⚠️ Warning**: Removing a dataset deletes all associated subjects, scans, and download history.

1. Go to **Manage Datasets**
2. Expand the dataset card
3. Click **Remove**
4. Confirm deletion if the dataset has subjects

## Browsing Subjects Across Datasets

### Dataset Filter

When you have multiple datasets, the Subjects Browser includes a **Dataset Filter** section:

```
Show subjects from:
☑ 🔐 TrackTBI Main
☑ 🌍 ds000246
```

- **Select multiple datasets** to view subjects from all of them
- **Deselect datasets** to hide their subjects
- The subject table includes a **Dataset** column showing the source

### Subject Display

The subject table now includes:

| Subject ID | Dataset | Age | Sex | 2WK | 6MO | QC Status |
|------------|---------|-----|-----|-----|-----|-----------|
| 001 | 🔐 TrackTBI | 32 | M | ✓ | ✓ | Pass |
| 002 | 🌍 ds000246 | 28 | F | ✓ | - | Pending |

**Icons**:
- 🔐 = Pennsieve (private)
- 🌍 = OpenNeuro (public)

## Filtering Across Datasets

### Metadata Filtering

The metadata filter works across multiple datasets:

```python
# Example: Find all male subjects aged 25-40 across all datasets
Filter:
  - Age: 25-40
  - Sex: Male

Result:
  - Subject 001 from TrackTBI
  - Subject 003 from ds000246
  - Subject 007 from ABCD Study
```

### Dataset-Specific Filtering

You can also filter subjects from specific datasets:

1. Use the **Dataset Filter** to select one dataset
2. Apply metadata filters
3. Results will only include subjects from the selected dataset(s)

## Unified Download Queue

### How It Works

1. **Add subjects to queue** from any dataset
2. **Queue displays all items** with dataset information
3. **Download execution** automatically routes:
   - Pennsieve items → Pennsieve Agent
   - OpenNeuro items → OpenNeuro Agent

### Queue Display

| File | Subject | Dataset | Platform | Size | Status |
|------|---------|---------|----------|------|--------|
| sub-001_T1w.nii.gz | 001 | TrackTBI | Pennsieve | 15 MB | Queued |
| sub-002_T2w.nii.gz | 002 | ds000246 | OpenNeuro | 12 MB | Queued |

### Download Execution

Clicking **Start Downloads** will:
1. Group items by dataset and platform
2. Execute Pennsieve downloads using dataset-specific credentials
3. Execute OpenNeuro downloads using dataset-specific settings
4. Update database with download status for each dataset

## Best Practices

### Naming Conventions

- **Use descriptive dataset names**: "TrackTBI_Pilot" instead of "Dataset1"
- **Include study phase**: "ABCD_Baseline", "ABCD_FollowUp"
- **Avoid duplicate names**: Each dataset must have a unique name

### Storage Organization

Organize local directories by dataset:

```
~/data-explorer/
├── datasets/
│   ├── TrackTBI/
│   │   ├── sub-001/
│   │   └── sub-002/
│   ├── ds000246/
│   │   ├── sub-001/
│   │   └── sub-002/
│   └── ABCD/
│       └── sub-001/
```

### Credential Management

- **Pennsieve datasets** require API credentials
- **OpenNeuro datasets** are public (no credentials needed)
- Credentials are stored per-dataset in the database
- Consider using environment variables for sensitive credentials

### Performance Tips

1. **Limit active datasets**: Keep only 2-3 datasets active at a time
2. **Use dataset filters**: Filter by specific datasets to improve query speed
3. **Deactivate unused datasets**: Set status to "inactive" instead of deleting
4. **Regular cleanup**: Remove old downloaded files to save disk space

## Troubleshooting

### Issue: "Dataset not found"

**Cause**: Dataset ID was deleted or database corrupted

**Solution**:
1. Check **Manage Datasets** to verify dataset exists
2. If missing, re-add the dataset
3. If database is corrupted, restore from backup

### Issue: "Foreign key mismatch"

**Cause**: Database schema not properly migrated

**Solution**:
1. Run migration script: `python scripts/migrate_to_multi_dataset.py`
2. If error persists, restore database from backup
3. Re-initialize database with `python scripts/init_db.py`

### Issue: "Cannot add more than 3 datasets"

**Cause**: v1.5 limits to 3 datasets

**Solution**:
1. Remove unused datasets
2. Upgrade to v2.0 for unlimited datasets (when available)

### Issue: "Downloads failing for specific dataset"

**Cause**: Invalid credentials or dataset configuration

**Solution**:
1. Go to **Manage Datasets**
2. Verify dataset credentials
3. Check dataset external ID (Pennsieve name or OpenNeuro ID)
4. Test credentials manually using platform CLI/API

## API Reference

### Database Operations

```python
from src.database import Database

db = Database('data/tracktbi.db')

# Add dataset
dataset_id = db.add_dataset(
    name="TrackTBI",
    platform="pennsieve",
    api_key="your_key",
    api_secret="your_secret",
    dataset_id_external="TrackTBI",
    root_path="/path/to/data"
)

# Get all datasets
datasets = db.get_all_datasets(status='active')

# Get subjects by dataset
subjects = db.get_subjects_by_dataset(dataset_id)

# Update dataset
db.update_dataset(dataset_id, status='inactive')

# Delete dataset (CASCADE deletes subjects/scans)
db.delete_dataset(dataset_id)
```

### Metadata Filtering

```python
from src.metadata_filter import MetadataFilter

# Multi-dataset filter
datasets = [
    {'id': 1, 'name': 'TrackTBI', 'root_path': '/path1'},
    {'id': 2, 'name': 'ds000246', 'root_path': '/path2'}
]

mf = MetadataFilter(datasets=datasets)

# Filter across all datasets
results = mf.filter_subjects({'sex': ['M'], 'age': {'min': 25, 'max': 40}})

# Filter specific datasets only
results = mf.filter_subjects({'sex': ['M']}, dataset_ids=[1])

# Results format (v1.5+)
# [
#   {'subject_id': '001', 'dataset_id': 1, 'dataset_name': 'TrackTBI'},
#   {'subject_id': '003', 'dataset_id': 2, 'dataset_name': 'ds000246'}
# ]
```

## Upgrading to v2.0 (Future)

Planned enhancements for v2.0:
- **Unlimited datasets**: Remove 3-dataset limitation
- **Cross-dataset harmonization**: Automatic metadata harmonization
- **Export custom cohorts**: Create new BIDS datasets from filtered subjects
- **Dataset discovery**: Search and browse available datasets
- **Batch import**: Import multiple datasets from config file

## Support

For issues or questions:
- Check [GitHub Issues](https://github.com/your-repo/issues)
- Read [V1_IMPLEMENTATION_PLAN.md](V1_IMPLEMENTATION_PLAN.md)
- Contact: your-email@example.com

## Changelog

### v1.5.0 (2026-02-21)
- Added multi-dataset support (up to 3 datasets)
- Added dataset management UI
- Added unified download queue with platform routing
- Updated database schema with `datasets` table
- Enhanced metadata filtering for multi-dataset
- Added migration script from v1.0

### v1.0.0
- Initial release with single dataset support
