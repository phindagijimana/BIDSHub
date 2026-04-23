# BIDSHub Troubleshooting Guide

Quick solutions to common issues in BIDSHub.

Last Updated: April 2026

---

## Before you report an issue

1. **Version and environment:** what does the sidebar show (e.g. BIDSHub v3.1.1), OS, and Python `python3 --version`?
2. **Logs:** when `./hub` fails, capture `./hub logs` (or the latest file under `logs/` if present) **after removing** API keys, tokens, and paths you do not want to share.
3. **Repro steps:** e.g. “Add Pennsieve dataset X → Sync → error message”.
4. **Non-interactive install/CI:** `BIDSHUB_NONINTERACTIVE=1` is set by `./hub install` so `init_db` does not block on an existing database; use the same in scripts if needed.

**Where logs live:** the `./hub` helper may tail Streamlit logs; project-level logs are often under `logs/` in the repository root. Do not upload `.env` or full credentials in bug reports.

---

## Install, pip, and venv

For a **full native production** walkthrough (checkout tag, `.env`, `./hub install` / `start`, upgrades), see [docs/NATIVE_PRODUCTION.md](docs/NATIVE_PRODUCTION.md).

### `resolution-too-deep` or long pip backtracking

- Install from the **committed** `requirements.txt` (fully pinned), not a loose subset.
- If you must regenerate, see [CONTRIBUTING.md](CONTRIBUTING.md): constrain `numpy` / `protobuf` / `urllib3` first, then `pip install --use-deprecated=legacy-resolver -r requirements.in` and `pip freeze` into a new `requirements.txt`.

### Broken venv (wrong `pip` shebang after moving the repo)

- Remove the `venv` folder and run `./hub install` again (creates a fresh venv for this path).

### `ModuleNotFoundError` after a partial install

- `pip install -r requirements.txt` and, for **tests** / `./hub test`, `pip install -r requirements-dev.txt`.

### Docker (optional)

- **Helper CLI (recommended):** from the repo root, `./hub-docker help` — commands `install`, `start`, `stop`, `restart`, `logs`, `checks`. **`./hub-docker start`** picks a free **host** port from **8501** through **8501+50** (override base with `BIDSHUB_DEFAULT_PORT` in the environment or `.env`; pin with `BIDSHUB_HOST_PORT`). **`checks`** reads the published port from `docker port` when possible.
- **Manual:** `docker compose build && docker compose up -d` (requires a host `.env` for `env_file` in compose; use `./hub-docker install` or `cp .env.example .env` first), then open the URL printed by start (default first try `http://localhost:8501`).
- **Data** — the compose file mounts `./data` into the container; use a path you own and back up like any local DB. The image runs as **uid 1000**; on Linux, if the database cannot be created, run `chown -R 1000:1000 data` (or your OS-specific equivalent) on the host mount.
- **Health** — the image’s healthcheck uses `http://127.0.0.1:8501/_stcore/health` (Streamlit). If the container is unhealthy, check `docker compose logs` and that dependencies installed during `docker build` completed without error.
- **Network** — the process listens on `0.0.0.0` **inside** the container; do not publish the port on hosts reachable from untrusted networks without a firewall or reverse proxy. See [SECURITY.md](SECURITY.md).
- **XNAT** is **beta** in the product: export to BIDS and validate before relying on a containerized-only setup; see the XNAT sections below and the platform table in the README.

---

## Security and networking (local app)

- **Localhost by default** — BIDSHub is a single-user desktop app. Exposing the Streamlit default port to `0.0.0.0` or a public host without a reverse proxy and auth is not supported and is unsafe.
- **Credentials** — keep Pennsieve (and any other) keys in `.env` or the OS keychain; never commit them. Rotate on GitHub/Slack if they leak.
- **Database** — `data/*.db` may contain your workflow metadata; back up and limit sharing like any local file.

---

## Quick Diagnostics

```bash
# Check BIDSHub status
./hub status

# View recent logs
./hub logs

# Database health check
./hub clean && ./hub install
```

---

## Connection Issues

### Pennsieve Connection Failed

**Error**: "Failed to connect to Pennsieve" or "Invalid credentials"

**Solutions**:

1. **Verify credentials**:
 - Go to app.pennsieve.io -> Settings -> API Keys
 - Regenerate API key/secret if unsure
 - Ensure no extra spaces when copying

2. **Test connection independently**:
 ```bash
 pip install pennsieve2
 python -c "from pennsieve import Pennsieve; ps = Pennsieve(api_token='YOUR_KEY', api_secret='YOUR_SECRET'); print(ps.datasets())"
 ```

3. **Check dataset name**:
 - Must match exactly (case-sensitive)
 - No spaces unless dataset name has spaces
 - Format: `TrackTBI` not `track-tbi`

4. **Network issues**:
 ```bash
 ping api.pennsieve.io
 # Should show successful responses
 ```

---

### OpenNeuro Dataset Not Found

**Error**: "Dataset ds000246 not found"

**Common mistakes**:
- Wrong: `DS000246` (uppercase)
- Wrong: `000246` (missing ds prefix)
- Right: `ds000246` (exact format)

**Verify**:
1. Go to openneuro.org
2. Find your dataset
3. URL shows: `openneuro.org/datasets/ds003974`
4. Use exactly: `ds003974`

---

### XNAT Authentication Failed

**Error**: "Failed to authenticate with XNAT"

**Solutions**:

1. **Check server URL format**:
 ```
 Correct: https://xnat.uni.edu
 Wrong: xnat.uni.edu (missing https://)
 Wrong: https://xnat.uni.edu/ (trailing slash)
 ```

2. **Verify credentials**:
 - Test login on XNAT web interface first
 - Ensure account has project access
 - Check if password expired

3. **Project ID**:
 - Must exist in your XNAT instance
 - Case-sensitive
 - Contact XNAT admin if unsure

---

### HPC/Remote Server SSH Failed

**Error**: "SSH connection failed" or "Permission denied"

**Solutions**:

1. **Test SSH manually**:
 ```bash
 ssh username@hpc.university.edu
 # Should connect without password if key configured
 ```

2. **SSH key setup**:
 ```bash
 # Generate key if needed
 ssh-keygen -t rsa -b 4096
   
 # Copy to remote
 ssh-copy-id username@hpc.university.edu
 ```

3. **Check BIDS path**:
 - Verify path exists: `ssh user@host "ls /path/to/bids"`
 - Ensure read permissions
 - Path must be absolute

4. **Firewall/VPN**:
 - Some HPCs require VPN connection
 - Check if SSH port (22) is blocked
 - Contact HPC support

---

## BIDS Validation Issues

### Validation Failed When Adding Dataset

**Error**: "BIDS validation failed"

**Common issues**:

1. **Missing `dataset_description.json`**:
 ```json
 {
 "Name": "My Study",
 "BIDSVersion": "1.6.0",
 "DatasetType": "raw"
 }
 ```
 Create this file in dataset root.

2. **Invalid subject folders**:
 ```
 Wrong: subject-001/ (missing 'sub-' prefix)
 Wrong: sub_001/ (underscore instead of dash)
 Right: sub-001/ (correct BIDS format)
 ```

3. **Invalid filenames**:
 ```
 Wrong: T1.nii.gz (missing subject/session)
 Wrong: sub-01-T1w.nii.gz (dash instead of underscore)
 Right: sub-01_ses-01_T1w.nii.gz (BIDS format)
 ```

4. **Run BIDS validator**:
 ```bash
 pip install bids-validator
 bids-validator /path/to/dataset/
 ```
 Fix issues shown, then re-add dataset to BIDSHub.

---

### Dataset Rejected - Not BIDS Format

**Error**: "Dataset does not follow BIDS format"

**Solutions**:

**For DICOM data**:
```bash
# Convert to BIDS
pip install dcm2bids
dcm2bids -d /dicom/folder/ -p sub-001 -s 01 -c config.json
```

**For NIfTI without BIDS structure**:
- Use BIDScoin: https://bidscoin.readthedocs.io/
- Or heudiconv: https://heudiconv.readthedocs.io/
- Manually reorganize following BIDS spec

**Resources**:
- BIDS specification: https://bids.neuroimaging.io/
- BIDS starter kit: https://bids-standard.github.io/bids-starter-kit/

---

## Data Access Issues

### No Subjects Found After Adding Dataset

**For cloud datasets**:

**Cause**: Dataset not synced yet

**Solution**:
```
1. Navigate to Subjects page
2. Look for dataset selector at top
3. Select your dataset
4. Click "Sync Subjects" button
5. Wait 30-90 seconds
6. Refresh page (F5)
7. Subjects should appear
```

**For local datasets**:

**Cause**: Invalid BIDS structure or permissions

**Check**:
```bash
# Verify structure
ls /path/to/dataset/
# Should show: sub-*/ folders

# Check permissions
ls -la /path/to/dataset/
# Should show read permissions for your user
```

**Solution**:
- Fix BIDS structure
- Navigate to Manage Datasets -> Re-index

---

### Empty Subjects Table After Filtering

**Cause**: Filters too restrictive

**Solution**:
```
1. Click "Clear Filters" button
2. Or manually reset:
 - Search: clear text
 - QC Status: All
 - Session: All
3. Gradually re-apply filters one at a time
```

---

## Download Issues

### Downloads Fail Repeatedly

**Error**: "Connection timeout" or "Download failed after 3 retries"

**Solutions**:

1. **Check internet speed**:
 ```bash
 # Run speed test
 speedtest-cli
 # Need: >5 Mbps for reliable downloads
 ```

2. **Check disk space**:
 ```bash
 # macOS/Linux
 df -h /path/to/download/directory
   
 # Windows
 dir "C:\path\to\downloads"
 ```
 Ensure sufficient space for queue.

3. **Reduce concurrent downloads**:
 - Default: 3 concurrent
 - If network unstable, try 1-2 concurrent
 - Modify in Download Manager settings (future feature)

4. **Platform-specific**:
 - **Pennsieve**: Check status.pennsieve.io for outages
 - **OpenNeuro**: Large files may timeout, retry later
 - **XNAT**: Contact server admin if persistent

---

### Insufficient Disk Space

**Error**: "Cannot download: Insufficient disk space"

**Solutions**:

1. **Free up space**:
 ```bash
 # Check usage
 df -h
   
 # Find large files
 du -sh /* | sort -h | tail -10
 ```

2. **Change download location**:
 ```
 Manage Datasets -> Select dataset -> Update Creds
 -> Change Local Working Directory to larger drive
 -> Save
 ```

3. **Download selectively**:
 - Filter by metadata first
 - Download T1w only (~12 MB vs 300 MB per subject)
 - Download in batches (50 subjects at a time)
 - Delete after analysis, re-download if needed

---

### File Integrity Errors

**Error**: "File size mismatch" or "Checksum verification failed"

**Cause**: Incomplete download or corruption

**Solutions**:

1. **Re-download**:
 ```
 Downloads -> Find failed item -> Remove
 -> Subject Details -> Re-queue scan
 -> Start download
 ```

2. **Check disk health**:
 ```bash
 # macOS
 diskutil verifyVolume /
   
 # Linux
 fsck /dev/sdX
 ```

3. **Database maintenance**:
 ```
 Manage Datasets -> Database Maintenance
 -> Run Maintenance
 -> Fixes download state mismatches
 ```

---

## Viewer Issues

### Image Won't Load

**Error**: "Image file not found" or "Failed to load NIfTI"

**For cloud datasets**:
```
Cause: Stub file (not downloaded yet)

Solution:
1. Subject Details -> Find scan
2. Check Downloaded column: Shows X No
3. Click v Queue
4. Downloads page -> Start Queue
5. After completion -> Click [View] View
```

**For local datasets**:
```
Cause: File moved/deleted

Solution:
1. Verify file exists:
 ls /path/shown/in/error
   
2. If dataset moved:
 - Remove dataset from BIDSHub
 - Re-add with correct path
 - Re-index
```

---

### Viewer Performance Slow

**Symptom**: Takes 10+ seconds to load images

**Causes and solutions**:

1. **Large 4D files** (fMRI):
 - Normal: 10-30 seconds for 200+ volumes
 - Patience required
 - Consider viewing 3D T1w first for QC

2. **Network storage** (NAS, remote mount):
 ```bash
 # Copy to local SSD first
 cp /mnt/nas/dataset/sub-001/...T1w.nii.gz ~/temp/
 # View from ~/temp/ (much faster)
 ```

3. **Low memory**:
 - Close other applications
 - Restart BIDSHub
 - Reduce browser tabs

---

## Performance Issues

### Slow Subject Browsing

**Symptom**: Table takes 5+ seconds to load

**Solutions**:

1. **Use pagination** (v3.1.1+):
 ```
 Subjects page -> Per page selector
 -> Select 25 or 50 (default)
 -> Faster than loading 1000+ subjects
 ```

2. **Deselect datasets**:
 ```
 Dataset Filter -> Uncheck unused datasets
 -> Only browse active projects
 ```

3. **Apply filters early**:
 - Set QC status, age, sex filters before browsing
 - Reduces result set size
 - Much faster rendering

4. **Cache enabled** (automatic):
 - First load: 2-3 seconds
 - Subsequent loads: <1 second (cached)
 - Cache auto-clears after 5 minutes

---

### Memory Usage High

**Symptom**: BIDSHub using 1+ GB RAM

**Causes**:
- Multiple large images opened in viewer
- Thousands of subjects loaded without pagination
- Cache growth

**Solutions**:

1. **Restart BIDSHub**:
 ```bash
 ./hub restart
 # Clears cache and resets memory
 ```

2. **Enable pagination** (should be automatic in v3.1.1+)

3. **Close viewer** when done reviewing images

4. **Deactivate large datasets** if not actively using

---

## Database Issues

### Database Corruption

**Error**: "Database malformed" or "Unable to open database"

**Solution**:
```bash
# Backup existing database
cp data/bidshub.db data/bidshub.db.backup

# Reset database
rm data/bidshub.db
./hub install

# Re-add datasets and sync
```

**Note**: Downloaded files are NOT deleted, only database metadata.

---

### Duplicate Subjects

**Symptom**: Same subject appears multiple times

**Cause**: Multiple syncs without duplicate prevention (fixed in v3.1.1+)

**Solution**:
```
Manage Datasets -> Database Maintenance
-> Run Maintenance
-> Removes duplicates (keeps latest)
```

---

### Orphaned Records

**Symptom**: Scans for deleted subjects still appear

**Solution**:
```
Manage Datasets -> Database Maintenance
-> Check Integrity
-> Shows: X orphaned scans, Y orphaned sessions
-> Run Maintenance
-> Cleans orphaned records
```

---

## Platform-Specific Issues

### Pennsieve: Package Not Found

**Error**: "Package ID not found"

**Cause**: Stub file missing package metadata

**Solution**:
1. Navigate to Subjects page
2. Select subject -> View Details
3. Re-sync dataset to refresh metadata
4. Re-queue scan for download

---

### OpenNeuro: Download Timeout

**Error**: "Connection timeout" for large files

**Cause**: OpenNeuro servers throttle large downloads

**Solution**:
- Retry download (automatic after 5-10 seconds)
- Download during off-peak hours (US nighttime)
- Smaller datasets download more reliably

---

### XNAT: Project Not Found

**Error**: "Project TBI_Study not found"

**Cause**: No access permissions or wrong ID

**Solutions**:
1. **Verify access**:
 - Login to XNAT web interface
 - Check if project appears in your projects list
 - Contact XNAT admin for access

2. **Check project ID**:
 - Use exact ID from XNAT interface
 - Case-sensitive
 - No spaces

---

### HPC: Permission Denied

**Error**: "Permission denied" when accessing BIDS path

**Cause**: No read permissions on remote directory

**Solutions**:
```bash
# Test access
ssh user@hpc "ls /path/to/bids"

# If denied, check permissions
ssh user@hpc "ls -la /path/to/bids"

# Request access from HPC admin
# Or use path where you have permissions
```

---

## QC Issues

### QC Status Not Saving

**Error**: "Invalid QC status" or "QC notes required"

**Cause**: Validation requirements (v3.1.1+)

**Solutions**:

1. **For "Fail" status**: Notes are required
 ```
 Mark as: Fail
 QC Notes: [Must provide reason for failure]
 ```

2. **For "Needs Review" status**: Notes are required
 ```
 Mark as: Needs Review
 QC Notes: [Describe why review needed]
 ```

3. **For "Pass" status**: Notes optional

---

### QC Not Syncing to Pennsieve

**Feature**: Pennsieve QC Upload (v3.1+)

**If upload fails**:

1. **Check Pennsieve connection**:
 - Verify credentials still valid
 - Test connection to dataset

2. **Verify QC data**:
 ```
 Quality Control -> Export QC CSV
 -> Open CSV -> Verify format correct
 -> Should have columns: scan_id, qc_status, qc_notes, etc.
 ```

3. **Manual upload**:
 - Export QC CSV
 - Upload manually to Pennsieve via web interface
 - Place in dataset root as `qc_results.csv`

---

## Data Transfer Issues

### Transfer Failed Between Platforms

**Error**: "Transfer failed" or "Upload failed after retries"

**Cause**: Connection issues, permissions, or incompatible paths

**Solutions**:

1. **Verify both connections**:
 ```
 Source platform: Test connection (Manage Datasets)
 Destination platform: Test connection
 Both should show OK Connected
 ```

2. **Check source exists**:
 - For Local -> Cloud: Verify local files exist
 - For Cloud -> Cloud: Verify source dataset synced

3. **Check destination permissions**:
 - Pennsieve: Need write access to dataset
 - XNAT: Need upload permissions
 - HPC: Need write permissions on remote path

4. **Retry with recovery** (automatic in v3.1.1+):
 - Failed transfers logged
 - View failed list in transfer results
 - Retry manually if needed

---

## Installation Issues

### Python Version Mismatch

**Error**: "Python 3.8+ required"

**Solution**:
```bash
# Check version
python --version

# If <3.8, install newer Python
# macOS (Homebrew)
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate
```

---

### Missing Dependencies

**Error**: "ModuleNotFoundError: No module named 'X'"

**Solution**:
```bash
# Install all dependencies
pip install -r requirements.txt

# Or quick reinstall
./hub install
```

**Common missing modules**:
- `paramiko` (for HPC/SSH): `pip install paramiko`
- `nibabel` (for MRI viewing): `pip install nibabel`
- `xnat` (for XNAT): `pip install xnat`

---

### Streamlit Port Already in Use

**Error**: "Port 8501 already in use"

**Solution**:
```bash
# CLI handles this automatically (default 8501, then up to +50)
./hub start

# Manual override to specific port
streamlit run app.py --server.port 8502
```

---

## UI Issues

### Page Not Loading

**Symptom**: Blank page or spinner forever

**Solutions**:

1. **Hard refresh**:
 - Press: `Ctrl+Shift+R` (Windows/Linux)
 - Press: `Cmd+Shift+R` (macOS)

2. **Check console**:
 - Browser: F12 -> Console tab
 - Look for JavaScript errors
 - Screenshot and report if found

3. **Restart BIDSHub**:
 ```bash
 ./hub restart
 ```

---

### Filters Not Working

**Symptom**: Changing filters doesn't update table

**Solutions**:

1. **Click "Apply Filters"** button (if present)

2. **Refresh page**: F5

3. **Clear cache**:
 - Browser: Ctrl+Shift+Delete -> Clear cache
 - Restart BIDSHub

---

## Data Integrity Issues

### Downloaded Files Missing

**Symptom**: Database shows "Downloaded: Yes" but file doesn't exist

**Cause**: File deleted manually or moved

**Solution**:
```
Manage Datasets -> Database Maintenance
-> Run Maintenance
-> Fix Download States: Verifies files exist
-> Resets status for missing files
-> Re-download from queue
```

---

### Scan Metadata Mismatch

**Symptom**: Scan info in database doesn't match file

**Cause**: Dataset updated on platform after initial sync

**Solution**:
```
Subjects page -> Select dataset -> Sync Subjects
-> Force re-sync of all metadata
-> Database updated with latest info
```

---

## Performance Troubleshooting

### App Becoming Slow Over Time

**Symptoms**:
- Initial load fast, then slows down
- Memory usage increases
- Database queries slow

**Solutions**:

1. **Database maintenance**:
 ```
 Manage Datasets -> Database Maintenance
 -> Run Maintenance
 -> Cleans orphaned records, duplicates
 -> Significantly improves performance
 ```

2. **Restart periodically**:
 - After heavy use (100+ downloads, extensive browsing)
 - Clears memory cache
 - Resets connections

3. **Reduce active datasets**:
 - Deactivate datasets not in use
 - Keeps UI responsive

---

### Large Dataset Loading Slow

**Symptom**: 1000+ subjects take 5+ seconds to load

**Solutions** (v3.1.1+):

1. **Pagination enabled by default**:
 - Loads 50 subjects at a time
 - Should be <1 second per page

2. **Reduce per-page count**:
 ```
 Subjects page -> Per page: 25
 -> Even faster loading
 ```

3. **Use filters**:
 - Apply age/sex/QC filters before viewing
 - Reduces result set dramatically

---

## Recovery Procedures

### Full Reset (Last Resort)

**When to use**: Corrupted database, persistent errors, major issues

**Procedure**:
```bash
# 1. Backup current state
mkdir -p ~/bidshub-backup/
cp -r data/ ~/bidshub-backup/data/
cp -r .env ~/bidshub-backup/.env

# 2. Clean install
./hub clean
./hub install

# 3. Re-add datasets
# Launch BIDSHub -> Manage Datasets -> Add datasets one by one
# Note: Downloaded files preserved, only database reset
```

---

### Recover from Crash

**If BIDSHub crashed during operation**:

1. **Check for zombie processes**:
 ```bash
 ps aux | grep streamlit
 # Kill any hung processes
 kill <pid>
 ```

2. **Check database integrity**:
 ```bash
 sqlite3 data/bidshub.db "PRAGMA integrity_check;"
 # Should show: ok
 ```

3. **Restart**:
 ```bash
 ./hub restart
 ```

4. **If still failing**:
 ```bash
 # View error logs
 tail -50 ~/.streamlit/logs/*.log
 ```

---

## Getting Additional Help

### Before Reporting Issues

**Collect this information**:

1. **BIDSHub version**:
 ```bash
 git log -1 --oneline
 ```

2. **Python version**:
 ```bash
 python --version
 ```

3. **Error logs**:
 ```bash
 tail -100 ~/.streamlit/logs/*.log > error_log.txt
 ```

4. **Platform and dataset**:
 - Which platform (Pennsieve, OpenNeuro, etc.)
 - Dataset ID or name
 - Steps to reproduce issue

### Contact Support

- **GitHub Issues**: https://github.com/phindagijimana/data_explorer/issues
- **Include**: Error logs, steps to reproduce, BIDSHub version
- **Screenshots**: Helpful for UI issues

### Platform-Specific Support

- **Pennsieve**: Contact your institution's Pennsieve admin
- **OpenNeuro**: support@openneuro.org
- **XNAT**: Your XNAT server administrator
- **DANDI**: help@dandiarchive.org
- **HPC**: Your institution's HPC support team

---

**For comprehensive user documentation, see: [`USER_GUIDE.md`](USER_GUIDE.md)**
