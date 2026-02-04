# Data Explorer - Detailed Setup Guide

Complete setup instructions for Data Explorer.

## Prerequisites

### System Requirements

- **Operating System**: macOS, Linux, or Windows
- **Python**: 3.8 or higher
- **Disk Space**: 
  - Application: ~100 MB
  - Downloads: Varies by dataset
- **RAM**: 4 GB minimum, 8 GB recommended
- **Internet**: Required for Pennsieve connection

### Required Accounts

- **Pennsieve Account**: Free account at [pennsieve.io](https://app.pennsieve.io)
- **API Credentials**: Generate from Pennsieve settings

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/data-explorer.git
cd data-explorer
```

### Step 2: Create Virtual Environment

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Expected installation time**: 2-5 minutes

### Step 4: Verify Installation

```bash
python -c "import streamlit; print(f'Streamlit {streamlit.__version__}')"
python -c "import bids; print(f'PyBIDS {bids.__version__}')"
python -c "import pennsieve; print(f'Pennsieve {pennsieve.__version__}')"
```

**Expected output**:
```
Streamlit 1.28.x
PyBIDS 0.16.x
Pennsieve 7.x.x
```

## Configuration

### Option 1: Environment Variables (Recommended)

Create `.env` file:

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

Edit `.env`:

```env
# BIDS Dataset
BIDS_ROOT=/path/to/your/bids/dataset

# Pennsieve Configuration
PENNSIEVE_API_KEY=your_api_key_here
PENNSIEVE_API_SECRET=your_api_secret_here
PENNSIEVE_DATASET_NAME=your_dataset_name

# Optional: Database path
DATABASE_PATH=data/tracktbi.db

# Optional: Download settings
DOWNLOAD_DIR=/path/to/download/directory
MAX_CONCURRENT_DOWNLOADS=3
```

### Option 2: Setup Wizard (Interactive)

Launch app without `.env`:

```bash
streamlit run app.py
```

The setup wizard will guide you through configuration.

## Getting Pennsieve Credentials

### Step 1: Log in to Pennsieve

1. Go to [app.pennsieve.io](https://app.pennsieve.io)
2. Log in with your credentials

### Step 2: Generate API Credentials

1. Click your profile (top right)
2. Go to "Settings"
3. Navigate to "API Keys & Secrets"
4. Click "Create API Key"
5. Copy the Key and Secret
6. **Important**: Save the secret immediately (shown only once)

### Step 3: Find Dataset Name

1. Go to "Datasets" in Pennsieve
2. Click your dataset
3. The name shown at the top is your dataset name
4. Case-sensitive! Must match exactly

## Testing the Installation

### Test Database

```bash
python scripts/init_db.py
```

**Expected output**:
```
✓ Database initialized successfully
✓ Created tables: subjects, scans, download_queue, qc_history, metadata
✓ Created 11 indexes
```

### Test BIDS Loader

```bash
python src/bids_loader.py /path/to/your/bids/dataset
```

**Expected output**:
```
Loading BIDS dataset...
✓ Loaded 660 subjects
==================================================
BIDS Dataset Summary
==================================================
dataset_name: TrackTBI
subject_count: 660
session_types: ['2WK', '6MO']
```

### Test Pennsieve Client

First, set environment variables:

```bash
export PENNSIEVE_API_KEY="your_key"
export PENNSIEVE_API_SECRET="your_secret"
python src/pennsieve_client.py TrackTBI
```

**Expected output**:
```
✓ Connected to Pennsieve as: your.email@example.com
✓ Connected to dataset: TrackTBI
```

## Running the Application

### Standard Launch

```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate     # Windows

# Run application
streamlit run app.py
```

### Custom Port

```bash
streamlit run app.py --server.port 8502
```

### Auto-open Browser

```bash
streamlit run app.py --server.headless false
```

### Production Mode

```bash
streamlit run app.py --server.headless true --server.port 8501
```

## First-Time Setup

### In the Application

1. **Launch**: Open `http://localhost:8501`

2. **Setup Page**:
   - Enter BIDS directory path
   - Enter Pennsieve dataset name
   - Enter API key
   - Enter API secret
   - Click "Initialize Dataset"

3. **Initialization** (takes 1-5 minutes):
   - ✓ Step 1/5: Verify BIDS directory
   - ✓ Step 2/5: Connect to Pennsieve
   - ✓ Step 3/5: Load BIDS dataset
   - ✓ Step 4/5: Initialize database
   - ✓ Step 5/5: Index subjects

4. **Success**: Auto-navigates to dashboard

## Troubleshooting Setup

### Python Version Issues

**Error**: `python: command not found`

**Solution**:
```bash
python3 --version  # Use python3 instead
python3 -m venv venv
```

### Permission Errors

**Error**: `Permission denied` when creating venv

**Solution**:
```bash
sudo chown -R $USER:$USER .
chmod +x venv/bin/activate
```

### Dependency Installation Failures

**Error**: `Failed building wheel for ...`

**Solution 1**: Upgrade pip
```bash
pip install --upgrade pip setuptools wheel
```

**Solution 2**: Install build dependencies

**macOS**:
```bash
xcode-select --install
```

**Ubuntu/Debian**:
```bash
sudo apt-get install python3-dev build-essential
```

**Windows**:
- Install Visual C++ Build Tools

### Pennsieve Connection Issues

**Error**: `Authentication failed`

**Solution**:
1. Verify credentials are correct
2. Try generating new API credentials
3. Check credentials have access to dataset
4. Verify dataset name is exact (case-sensitive)

**Error**: `Dataset not found`

**Solution**:
1. Check dataset name spelling (case-sensitive)
2. Verify you have permission to access dataset
3. Try viewing dataset in Pennsieve web interface first

### BIDS Dataset Issues

**Error**: `Missing dataset_description.json`

**Solution**:
1. Verify path points to BIDS root (not subdirectory)
2. Check `dataset_description.json` exists
3. Validate BIDS structure

**Error**: `No subject directories found`

**Solution**:
1. Check for directories starting with `sub-`
2. Verify BIDS structure is correct
3. Check file permissions

## Advanced Configuration

### Custom Database Location

In `.env`:
```env
DATABASE_PATH=/custom/path/to/database.db
```

### Multiple Datasets

Create separate `.env` files:

```bash
.env.tracktbi
.env.dataset2
```

Load specific config:
```bash
cp .env.tracktbi .env
streamlit run app.py
```

### Performance Tuning

For large datasets (>1000 subjects):

In `.env`:
```env
MAX_CONCURRENT_DOWNLOADS=5
```

Or in code (`src/download_manager.py`):
```python
DownloadManager(max_concurrent=5)
```

## Updating

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

### Pull Latest Code

```bash
git pull origin main
pip install --upgrade -r requirements.txt
```

### Database Migrations

If database schema changes:

```bash
# Backup existing database
cp data/tracktbi.db data/tracktbi.db.backup

# Reinitialize
python scripts/init_db.py
```

## Uninstallation

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf venv/

# Remove database (optional)
rm -rf data/*.db

# Remove .env file (optional)
rm .env
```

## Getting Help

### Check Logs

Streamlit logs are shown in terminal.

For detailed errors, check:
```bash
~/.streamlit/logs/
```

### Database Issues

Check database:
```bash
sqlite3 data/tracktbi.db
.tables
.schema subjects
.exit
```

### Report Issues

1. Check existing issues on GitHub
2. Collect error messages
3. Note your environment (OS, Python version)
4. Create new issue with details

## Next Steps

After successful setup:

1. **Read the User Guide**: `docs/USER_GUIDE.md` (coming soon)
2. **Try the workflow**: Setup → Browse → QC → Download
3. **Explore features**: Dashboard, filters, exports
4. **Provide feedback**: Report bugs, suggest features

---

**Setup Complete!** 🎉

You're ready to use Data Explorer. Launch with:

```bash
streamlit run app.py
```
