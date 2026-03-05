# BIDSHub

**Multi-platform neuroimaging dataset management and exploration tool.**

Browse, filter, and download BIDS datasets from multiple platforms simultaneously. Cross-platform metadata filtering, unified QC workflows, and MRI viewing - all from your desktop.

## WARNING: BIDS Format Required

**BIDSHub only accepts datasets in [BIDS](https://bids.neuroimaging.io/) format.**

This standardization ensures:
- **Cross-platform compatibility** - Browse and filter subjects the same way regardless of source platform
- **Unified metadata** - Age, sex, diagnosis fields work across all datasets
- **Consistent file structure** - Subjects, sessions, and scans organized identically

### Platform BIDS Status

| Platform | BIDS Status | Action Required |
|----------|-------------|-----------------|
| **OpenNeuro** | OK All datasets are BIDS | Ready to use |
| **DANDI** | WARNING: Mixed (NWB + BIDS) | Select MRI/BIDS datasets only |
| **Pennsieve** | WARNING: User-organized | Organize as BIDS before upload |
| **XNAT** | WARNING: DICOM archives | Export as BIDS (use XNAT plugin or dcm2bids) |

### Need to Convert to BIDS?

- **From DICOM**: Use [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/), [heudiconv](https://heudiconv.readthedocs.io/), or [BIDScoin](https://bidscoin.readthedocs.io/)
- **BIDS Validator**: Run [bids-validator](https://bids-standard.github.io/bids-validator/) before adding dataset
- **Learn BIDS**: Visit [bids.neuroimaging.io](https://bids.neuroimaging.io/) for specification

**BIDSHub validates datasets before adding them** - non-BIDS data will be rejected with guidance on how to fix.

## What is BIDSHub?

BIDSHub is a **desktop application** that connects to multiple neuroimaging data platforms, allowing you to browse and download BIDS-formatted datasets without uploading your data or managing complex cloud infrastructure. Aggregate subjects from up to 20 datasets across different platforms into a unified view.

**Perfect for:**
- Aggregating datasets from multiple platforms (Pennsieve, OpenNeuro, XNAT, DANDI, HCP, LORIS, FITBIR)
- Tracking quality control status across datasets
- Downloading only the subjects you need based on metadata filters
- Browsing dataset structures before downloading
- Creating custom cohorts from multiple sources
- Viewing MRI images directly in the app
- Managing longitudinal studies with multiple timepoints

**Not designed for:**
- Multi-user collaboration (single user per installation)
- Data processing/analysis (use fMRIPrep, FreeSurfer, etc.)
- Cloud/server deployment (runs locally on your machine)

## Supported Platforms

| Platform | Status | Primary Modality | BIDS Requirement | Notes |
|----------|--------|------------------|------------------|-------|
| **OpenNeuro** | OK Production | MRI, EEG, MEG | OK Native BIDS | 1000+ public datasets, all BIDS-compliant |
| **Pennsieve** | OK Production | MRI, Multi-modal | WARNING: Must organize as BIDS | Private datasets, institutional use |
| **DANDI** | OK Production | NWB, EEG, MRI | WARNING: Filter for BIDS MRI | Neurophysiology focus, mixed formats |
| **XNAT** | OK Beta (v2.1) | MRI, DICOM | WARNING: Export as BIDS | Institutional archives, requires BIDS export |
| **Local** | OK Production | Any | OK Must be BIDS | For datasets already on disk |

**Additional platforms** (v3.1.1+):
| **HPC** | OK Production | MRI, Any | OK Must be BIDS | SSH access to institutional HPC clusters |
| **Remote Server** | OK Production | MRI, Any | OK Must be BIDS | SSH access to any remote Linux server |

## Features

### Core Features
- **BIDS Validation** - Automatic validation of dataset structure before adding
- **Multi-Platform Integration** - Connect to 7 neuroimaging platforms simultaneously (Pennsieve, OpenNeuro, DANDI, XNAT, HPC, Remote Server, Local)
- **Subject Browser** - Unified view with pagination (50 subjects/page), dynamic session support
- **Cross-Platform Filtering** - Filter by age, sex, diagnosis, keywords, modalities
- **Download Manager** - Queue-based downloads with batch processing (10 subjects/batch)
- **Quality Control** - Scan-level QC with Pennsieve sync support
- **MRI Viewer** - Built-in NIfTI viewer (no download required)
- **Data Transfer** - Move data between platforms (Local ↔ Pennsieve, HPC, XNAT, Remote Server)
- **Performance** - Metadata caching, SSH connection pooling, optimized batch operations

### Multi-Dataset Support
- Aggregate up to **20 BIDS datasets** from any combination of platforms
- Unified subject browser with cross-dataset filtering
- Platform-specific credential management
- Dataset-level activate/deactivate controls
- Dynamic session handling (not limited to specific timepoints)

## Tech Stack

Python • Streamlit • SQLite • PyBIDS • Pennsieve • OpenNeuro • xnatpy • dandi • boto3

## Quick Start

### Option 1: Native Python
```bash
# Clone repository
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer

# Install (one command)
./hub install

# Launch
./hub start
```

The browser opens automatically at `http://localhost:8501` (or next available port).

### Option 2: Docker (Recommended)
```bash
# Clone repository
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer

# Create .env file with your credentials
cp .env.example .env
# Edit .env with your Pennsieve credentials and BIDS path

# Start
docker-compose up -d

# Access
open http://localhost:8501
```

**Benefits of Docker:** Zero configuration, reproducible environment, works everywhere.

### First Run Workflow

**On first launch**, BIDSHub automatically:
- Creates database
- Opens Manage Datasets page

**To add your first dataset**:

**Cloud Dataset** (OpenNeuro, Pennsieve, XNAT, DANDI):
1. Choose platform
2. Enter dataset ID/name and credentials
3. Click "Add Dataset" (BIDS validation runs automatically)
4. Navigate to "Subjects" page and click "Sync Subjects"

**Local Dataset** (data already on disk):
1. Select "Local Only" platform
2. Enter path to your BIDS dataset
3. Click "Add Dataset" (BIDS validation runs automatically)
4. Subjects are indexed immediately!

**Done!** Go to Dashboard to see your data.

## CLI Commands

```bash
./hub start # Launch BIDSHub
./hub stop # Stop BIDSHub
./hub restart # Restart after changes
./hub install # Install dependencies
./hub status # Check if running
./hub clean # Clean database and cache
./hub help # Show all commands
```

**Cross-platform:** Same commands work on macOS, Linux, and Windows.

## Configuration

Optional: Create `.env` file:

```env
BIDS_ROOT=/path/to/bids/dataset
PENNSIEVE_API_KEY=your_key
PENNSIEVE_API_SECRET=your_secret
PENNSIEVE_DATASET_NAME=your_dataset
```

Or configure via UI on first launch.

## Troubleshooting

**BIDS Validation Failed?**
- Run `bids-validator` on your dataset: `bids-validator /path/to/dataset`
- Check for required files: `dataset_description.json`, subjects starting with `sub-`
- Verify file naming follows BIDS convention: `sub-01_ses-baseline_T1w.nii.gz`
- See [bids.neuroimaging.io](https://bids.neuroimaging.io/) for full specification
- Use [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/) to convert DICOM to BIDS

**Dataset rejected for missing metadata?**
- Ensure `participants.tsv` exists with `participant_id` column
- Add demographic fields: `age`, `sex`, `diagnosis`, `group`
- BIDSHub works with sparse metadata but filtering requires populated fields

**Port conflict?**
- CLI automatically finds available port (8500-8550)

**Can't connect to platform?**
- Verify credentials are correct (API key, secret, token)
- Check internet connection
- Ensure dataset/project ID is exact (case-sensitive)
- For Pennsieve: dataset name must match exactly
- For OpenNeuro: use dataset ID format (e.g., `ds000246`)
- For DANDI: use 6-digit dandiset ID (e.g., `000001`)

**Database issues?**
```bash
./hub clean
./hub install
```

**More help:**
```bash
./hub help
./hub status
./hub logs
```

## Documentation

- **[USER_GUIDE.md](USER_GUIDE.md)** - Complete user documentation, platform connections, workflows
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Solutions to common issues
- **[BIDS_EEG_PLAN.md](BIDS_EEG_PLAN.md)** - Future EEG/iEEG support plan

## Requirements

### Native Installation
- Python 3.8+
- **BIDS-formatted dataset** (required for all platforms)
- Platform credentials (varies by platform - see [Platform Integration Guide](PLATFORM_INTEGRATION_GUIDE.md))
- Pennsieve Agent (auto-installed with `./hub install`, only needed for Pennsieve)

### Docker Installation
- Docker Desktop (Mac/Windows) or Docker Engine (Linux)
- **BIDS-formatted dataset** (required for all platforms)
- Platform credentials (varies by platform)
- **No Python or Pennsieve Agent needed** (bundled in container)

### BIDS Dataset Requirements
Your dataset must include:
- `dataset_description.json` with `Name` and `BIDSVersion` fields
- Subject folders named `sub-<ID>` (e.g., `sub-01`, `sub-patient001`)
- Modality folders (`anat`, `func`, `dwi`, `fmap`, etc.) containing imaging data
- Files following BIDS naming: `sub-<ID>[_ses-<ID>][_<key>-<value>]_<suffix>.nii.gz`
- Recommended: `participants.tsv` with demographics, `README` with dataset description

Run `bids-validator` on your dataset before adding to BIDSHub.

## License

MIT License - see [LICENSE](LICENSE) file

## Support

- **Documentation**: [USER_GUIDE.md](USER_GUIDE.md) - Complete guide
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- **Issues**: [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues)

---

**Version**: 3.1.1 
**Status**: Production Ready 
**Last Updated**: February 2026
