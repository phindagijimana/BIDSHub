# Data Explorer

A professional BIDS dataset management tool with Pennsieve integration.

## Overview

Data Explorer is a web-based application for exploring, managing, and downloading BIDS (Brain Imaging Data Structure) neuroimaging datasets stored on the Pennsieve platform. Built for researchers working with large-scale neuroimaging data.

## Features

### ✅ Completed (v1.0 MVP)

- **Dataset Setup**: One-time initialization with progress tracking
- **Dashboard**: Real-time statistics and overview metrics
- **Subject Browser**: Search, filter, and browse all subjects
- **Subject Detail**: View scans for each subject with QC controls
- **Quality Control Workflow**: 
  - Track QC status (pending/pass/fail/needs review)
  - Add notes and flag subjects
  - QC history tracking
  - Bulk QC updates
  - Export QC reports
- **Download Manager**: 
  - Selective downloads from Pennsieve
  - Queue management
  - Concurrent downloads (3 simultaneous)
  - Progress tracking
  - Start/pause/resume controls
- **Pennsieve Integration**: Direct cloud access to imaging files with real file sizes
- **Export Capabilities**: Export subject lists and QC reports to CSV
- **Professional UI**: Chase Bank-inspired navy blue and white theme

## Tech Stack

- **Framework**: Streamlit (Python web framework)
- **Database**: SQLite
- **BIDS Processing**: PyBIDS
- **Cloud Integration**: Pennsieve Python SDK
- **Visualization**: Plotly

## Installation

### Prerequisites

- Python 3.8 or higher
- pip
- Pennsieve account with API credentials

### Setup

### Quick Install (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer

# 2. One-command installation (works on all platforms)
python explorer.py install
```

This will:
- Create virtual environment
- Install all dependencies
- Initialize the database
- Set up logs directory

### Manual Installation

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
source venv/bin/activate  # Mac/Linux
# OR
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database
python scripts/init_db.py

# 5. Configure environment variables
cp .env.example .env
# Edit .env with your settings
```

## Configuration

Create a `.env` file based on `.env.example`:

```env
BIDS_ROOT=/path/to/your/bids/dataset
PENNSIEVE_API_KEY=your_api_key
PENNSIEVE_API_SECRET=your_api_secret
PENNSIEVE_DATASET_NAME=your_dataset_name
```

## Usage

## CLI Commands

Data Explorer includes a unified CLI for easy management across all platforms:

### **Recommended: Cross-Platform CLI (Works Everywhere!)**

```bash
python explorer.py <command>
```

**Works on:** ✅ macOS, ✅ Linux, ✅ Windows

### **Platform-Specific CLIs (Alternative)**

```bash
./explorer <command>        # Mac/Linux only
explorer.bat <command>      # Windows only
```

### Available Commands

| Command | Description |
|---------|-------------|
| `install` | Install dependencies and initialize database |
| `start` | Start the application (auto-finds port 8500-8550) |
| `stop` | Stop the application |
| `restart` | Restart the application |
| `status` | Check if running (PID, port, CPU, memory) |
| `logs` | View live application logs |
| `update` | Pull latest code and update dependencies |
| `test` | Run tests (database, imports, modules) |
| `clean` | Remove virtual environment and cache |
| `config` | Show current configuration |
| `help` | Show all commands |

### Quick Start

```bash
# First time setup
python explorer.py install

# Start application
python explorer.py start

# Check status
python explorer.py status

# View logs
python explorer.py logs

# Stop application
python explorer.py stop
```

**Works on macOS, Linux, and Windows!** ✅

### Starting the Application

**Option 1: CLI (Recommended - Works Everywhere)**

```bash
python explorer.py start
```

**Works on:** ✅ macOS, ✅ Linux, ✅ Windows

**Option 2: Platform-Specific CLIs**

```bash
./explorer start          # Mac/Linux
explorer.bat start        # Windows
```

**Option 3: Smart Launchers**

```bash
python launch.py         # Cross-platform
./launch.sh              # Mac/Linux
launch.bat               # Windows
```

**Option 4: Manual Launch**

```bash
# Activate virtual environment
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Start the application
streamlit run app.py
```

The application automatically finds an available port (default: 8501, range: 8500-8550) and opens in your browser.

### First-Time Setup

1. **Launch the app** - Run `streamlit run app.py`
2. **Enter BIDS directory path** - Path to your local BIDS dataset
3. **Enter Pennsieve credentials**:
   - Dataset name (e.g., "TrackTBI")
   - API Key
   - API Secret
4. **Click "Initialize Dataset"**
5. **Wait for indexing** - Progress bar shows 5 steps:
   - Verify BIDS directory
   - Connect to Pennsieve
   - Load BIDS dataset
   - Initialize database
   - Index all subjects
6. **Dashboard opens automatically** when complete

### Workflow

#### 1. Dashboard
- View overview metrics (subjects, sessions, scans)
- Check data completeness
- Monitor QC status
- Quick access to all features

#### 2. Browse Subjects
- Search by subject ID
- Filter by QC status
- Filter by session (2WK/6MO/both)
- Export filtered list to CSV
- Click subject to view details

#### 3. Subject Detail
- View scans for each session
- Update QC status
- Add QC notes
- Flag for review
- Add scans to download queue

#### 4. Download Manager
- View download queue
- Check storage estimation
- Start/pause/resume downloads
- Monitor progress
- Clear queue

#### 5. QC Dashboard
- View QC statistics
- Filter by status
- Bulk update QC status
- View recent activity
- Export QC report

## Project Structure

```
data-explorer/
├── app.py                    # Main Streamlit application
├── src/
│   ├── bids_loader.py       # PyBIDS wrapper
│   ├── pennsieve_client.py  # Pennsieve API client
│   ├── database.py          # SQLite operations
│   ├── download_manager.py  # Download orchestration
│   ├── qc_manager.py        # QC workflow
│   ├── theme.py             # UI theme (Chase Bank navy)
│   └── utils.py             # Helper functions
├── scripts/
│   └── init_db.py           # Database initialization
├── data/                     # Local data storage
├── assets/                   # Static assets
└── tests/                    # Tests
```

## Features

### Dashboard
- Overview metrics (subjects, sessions, scans)
- Session completeness statistics
- Modality availability charts

### Subject Browser
- Search and filter subjects
- View QC status
- Export subject lists

### Subject Detail
- View all scans for a subject
- Download individual files or sessions
- Update QC status and notes

### Download Manager
- Storage estimation
- Queue management
- Progress tracking
- Concurrent downloads

### QC Dashboard
- QC status overview
- Filter subjects needing review
- Track QC history
- Export QC reports

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

This project follows PEP 8 style guidelines.

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Support

For issues or questions, please open a GitHub issue.

## Troubleshooting

### Setup Issues

**"BIDS directory not found"**
- Check the path is correct
- Ensure you have read permissions
- Path should point to the root of your BIDS dataset

**"Failed to connect to Pennsieve"**
- Verify your API credentials
- Check internet connection
- Ensure dataset name matches exactly
- Try generating new API credentials

**"Initialization failed"**
- Check error details in expander
- Ensure BIDS dataset has `dataset_description.json`
- Verify at least one subject directory exists (`sub-*`)

### Performance Issues

**Slow loading**
- Large datasets (>1000 subjects) may take time to index
- Consider using a faster disk (SSD)
- Close other applications

**Download fails**
- Check internet connection
- Verify Pennsieve credentials are still valid
- Ensure sufficient disk space
- Try downloading individual files

### Common Errors

**"Package ID not found"**
- Stub files may not contain valid package IDs
- Try re-downloading dataset from Pennsieve
- Check file is actually a Pennsieve stub

**"Database locked"**
- Close and restart the application
- Ensure only one instance is running
- Check file permissions on `data/` directory

## Roadmap

### Version 1.1 (Polish)
- [ ] Advanced filtering
- [ ] Sortable tables
- [ ] Keyboard shortcuts
- [ ] Improved error messages
- [ ] Loading animations

### Version 1.5 (Generalization)
- [ ] Support for other session naming patterns
- [ ] Auto-detect cohorts
- [ ] Custom metadata fields
- [ ] Multiple BIDS datasets

### Version 2.0 (Advanced)
- [ ] Data visualization (brain images)
- [ ] MRIQC integration
- [ ] fMRIPrep integration
- [ ] Multi-user support
- [ ] Docker deployment

See `MISSING_FEATURES.md` for complete roadmap.

---

**Status**: MVP (v1.0.0)  
**Last Updated**: February 3, 2026
