# Data Explorer v1.0 - MVP Implementation Plan

**Purpose:** This is the actionable plan for building v1.0 (MVP)  
**For future features:** See [PENNSIEVE_MAPPING_INTEGRATION.md](PENNSIEVE_MAPPING_INTEGRATION.md)

---

**Goal:** Production-ready single-dataset tool  
**Timeline:** 4-6 weeks  
**Status:** 🟡 In Progress

**Document Scope:**
- ✅ What we're building RIGHT NOW
- 🔨 Specific tasks with time estimates
- 📋 Testing checklist
- 🎯 MVP definition of done

**This is the implementation plan** - start here to build v1.0.

---

## Mission: Turn Pennsieve CLI into UI + Docker Deployment

**Current:** Users run terminal commands  
**Target:** Users click buttons in UI + Deploy via Docker

```
Before: $ pennsieve map TrackTBI /path/to/local
After:  [Map Dataset] button → Shows progress → Done

Installation:
- Native: ./explorer install && ./explorer start
- Docker: docker-compose up -d ⭐ NEW in v1.0
```

---

## Pennsieve CLI Coverage Analysis

### Available Pennsieve CLI Commands

**Core Commands:**
- `pennsieve agent` - Start gRPC server
- `pennsieve config` - Show configuration
- `pennsieve dataset` - Set working dataset
- `pennsieve manifest` - List upload sessions
- `pennsieve profile` - Manage user profiles
- `pennsieve upload` - Upload files to Pennsieve
- `pennsieve whoami` - Show logged-in user info

**Map Commands (BETA):**
- `pennsieve map <dataset> <path>` - Map dataset structure locally
- `pennsieve map pull <path>` - Download specific files
- `pennsieve map push` - ⚠️ NOT YET IMPLEMENTED by Pennsieve
- `pennsieve map fetch` - ⚠️ NOT YET IMPLEMENTED by Pennsieve
- `pennsieve map diff` - ⚠️ NOT YET IMPLEMENTED by Pennsieve

### ✅ Covered in Data Explorer v1.0

| CLI Command | Data Explorer Feature | Status |
|-------------|----------------------|--------|
| `pennsieve map <dataset> <path>` | "Smart Mapping" button in setup | ✅ v1.0 |
| `pennsieve map pull <path>` | Download manager with selective downloads | ✅ v1.0 |
| `pennsieve dataset` | Dataset selection in UI config | ✅ v1.0 |
| `pennsieve whoami` | Credential validation on setup | ✅ v1.0 |

### ❌ NOT Covered in v1.0 (Future Features)

| CLI Command | Reason | Future Version |
|-------------|--------|----------------|
| `pennsieve upload` | v1.0 is read-only (download focus) | v1.1+ if needed |
| `pennsieve map push` | Not implemented by Pennsieve yet | When Pennsieve adds |
| `pennsieve map fetch` | Not implemented by Pennsieve yet | When Pennsieve adds |
| `pennsieve map diff` | Not implemented by Pennsieve yet | When Pennsieve adds |
| `pennsieve manifest` | Upload-focused, not needed for v1.0 | v1.1+ if needed |
| `pennsieve profile` | Uses .env instead of profiles | Maybe v1.1+ |
| `pennsieve config` | Uses .env instead of config files | Maybe v1.1+ |
| `pennsieve agent` | gRPC server not needed for our use | Not planned |

### 🔮 Future Considerations (v1.1+)

**If Users Request:**
1. **Upload Support** (`pennsieve upload`)
   - Add "Upload to Pennsieve" feature
   - Reverse workflow: Local → Pennsieve
   - Use case: Upload processed data back

2. **Sync Features** (`map push/fetch/diff`)
   - Only when Pennsieve implements them
   - Would enable bidirectional sync
   - "Download changes from Pennsieve"
   - "Upload local changes to Pennsieve"

3. **Profile Management** (`profile`)
   - Switch between multiple Pennsieve accounts
   - Team collaboration features
   - Currently: Single user per installation

### Design Decision: Read-Only for v1.0

**Rationale:**
- Primary use case: Download and analyze data
- Uploading less common than downloading
- Simpler permissions (viewer vs manager)
- Reduces risk of data corruption
- Focus on core value: Smart downloads + QC

**User can still upload via:**
- Pennsieve web interface
- Native Pennsieve CLI
- Pennsieve Python SDK directly

**v1.0 Focus:** Download, browse, QC, export (read-only operations)

---

## Four Core Deliverables

### 1. ✅ Subjects Browser + Statistics (80% Done)
- Subject list with search/filter
- Dashboard with dataset statistics
- Subject detail with scan metadata
- **Needs:** Enhanced stats, better metadata display

### 2. 🟡 QC Dashboard (70% Done)
- Manual QC status tracking per subject
- Bulk updates and notes
- Activity logging
- **Needs:** Automated QC checks, separate columns for auto/manual QC, export reports, progress charts

### 3. 🔴 Download & Upload Manager (60% Done) - PRIORITY
- Queue-based downloads and uploads
- **Needs:** Pennsieve Agent integration, metadata filtering, progress tracking, upload UI

### 4. 🔴 Docker Deployment (0% Done) - PRIORITY
- Containerized application
- One-command deployment
- **Needs:** Dockerfile, docker-compose, documentation

---

## Critical Tasks (Week 1-2)

### Task 1: Pennsieve Agent Integration (8h) 🔴
**Create:** `src/pennsieve_agent.py`

**Core Functions:**
```python
class PennsieveAgent:
    def map_dataset(dataset, path, api_key, api_secret)
        # Map structure without downloading files
    
    def pull_file(file_path, api_key, api_secret, progress_callback)
        # Download specific file with progress
    
    def batch_pull(file_paths, ...)
        # Download multiple files
    
    def get_mapped_status(file_path)
        # Check: not_mapped | mapped (stub) | downloaded
```

**Integration Points:**
- Setup wizard: Add "Smart Mapping" option
- Download manager: Connect to actual Pennsieve downloads
- Progress tracking: Real-time updates during map/download

---

### Task 2: Metadata-Based Filtering (6h) 🔴
**Create:** `src/metadata_filter.py`

**Purpose:** Filter subjects/scans by metadata before downloading

**Filter Types:**
```python
# Subject Metadata (from participants.tsv)
{
    'age': {'min': 18, 'max': 65},      # Numeric range
    'sex': ['M', 'F'],                   # Categorical
    'diagnosis': ['TBI'],                # Categorical
    'site': ['01', '02']                 # Multi-select
}

# Scan Filters
{
    'sessions': ['2WK', '6MO'],          # Timepoints
    'modalities': ['T1w', 'T2w'],        # Scan types
    'qc_status': ['pass']                # QC filter
}
```

**UI Flow:**
```
1. Set filters in Download Manager
2. Preview matched subjects + size estimate
3. Click "Add Filtered to Queue"
4. All matching scans added

Example: "TBI subjects, age 18-45, QC passed, T1w only"
Result: 23 subjects, 23 scans, 1.2 GB (vs 150 subjects, 60 GB)
```

**Core Class:**
```python
class MetadataFilter:
    def __init__(self, bids_root):
        self.participants_df = pd.read_csv('participants.tsv', sep='\t')
    
    def get_available_fields() -> List[str]
        # Return columns: age, sex, diagnosis, etc.
    
    def filter_subjects(criteria: Dict) -> List[str]
        # Apply filters, return matching subject IDs
    
    def get_summary_stats(subjects) -> Dict
        # Calculate age range, sex distribution, etc.
```

---

### Task 3: Automated QC System (6h) 🔴

**Create:** `src/automated_qc.py`

**Purpose:** Run automated checks on scans, separate from manual human review

**Two Types of QC:**

| **Automated QC** | **Manual QC** |
|------------------|---------------|
| Computer checks | Human review |
| File exists, readable | Visual inspection |
| BIDS compliance | Artifacts, quality |
| Expected scans present | Clinical assessment |
| File size reasonable | Motion, coverage |
| Metadata complete | Usability decision |

**Why Separate Columns?**
- Auto QC = Technical checks (fast, objective, catches missing files/errors)
- Manual QC = Quality assessment (slow, subjective, catches artifacts/motion)
- **Both needed:** File may exist (auto ✓) but be unusable (manual ✗)
- **Workflow:** Auto QC first → Flags problems → Manual review focuses on issues

**Database Schema Update:**

```sql
-- subjects table now has TWO sets of QC columns:

-- AUTOMATED QC (computer checks)
ALTER TABLE subjects ADD COLUMN automated_qc_status TEXT DEFAULT 'pending';
-- Values: 'pending' | 'pass' | 'warning' | 'fail'

ALTER TABLE subjects ADD COLUMN automated_qc_date TIMESTAMP;
-- When automated QC last ran

ALTER TABLE subjects ADD COLUMN automated_qc_results JSON;
-- Detailed results: {'checks': {...}, 'issues': [...], 'warnings': [...]}

-- MANUAL QC (human review) - EXISTING COLUMNS
-- qc_status TEXT          - Manual review: 'pending' | 'pass' | 'fail' | 'needs_review'
-- qc_notes TEXT           - Human reviewer notes
-- reviewed_by TEXT        - Who reviewed it
-- review_date TIMESTAMP   - When human reviewed
-- flagged BOOLEAN         - Needs attention

-- This allows tracking:
-- Auto QC: ✓ Pass (all files present) + Manual QC: ✗ Fail (poor quality)
-- Auto QC: ✗ Fail (missing files) + Manual QC: - Pending (not yet reviewed)
```

**Automated Checks:**

```python
class AutomatedQC:
    """Run automated quality checks on BIDS subjects."""
    
    def run_subject_qc(self, subject_id: str, session: str) -> dict:
        """
        Run all automated checks for a subject/session.
        
        Returns:
            {
                'status': 'pass' | 'fail' | 'warning',
                'checks': {
                    'files_exist': True,
                    'bids_compliant': True,
                    'expected_scans': {'T1w': True, 'T2w': True, 'FLAIR': False},
                    'file_sizes_ok': True,
                    'metadata_complete': True,
                    'stub_files': 2  # Number of unmapped files
                },
                'issues': ['Missing FLAIR scan', 'T2w file is stub (not downloaded)']
            }
        """
        results = {
            'status': 'pass',
            'checks': {},
            'issues': [],
            'warnings': []
        }
        
        # Check 1: Files exist and are readable
        scans = self.bids_loader.get_subject_scans(subject_id, session)
        for scan in scans:
            if not Path(scan['file_path']).exists():
                results['issues'].append(f"Missing: {scan['file_path']}")
                results['status'] = 'fail'
            elif self.bids_loader.is_stub_file(scan['file_path']):
                results['warnings'].append(f"Stub file: {Path(scan['file_path']).name}")
        
        # Check 2: Expected scans present
        expected = ['T1w', 'T2w', 'FLAIR', 'DWI']
        found_modalities = [s['suffix'] for s in scans]
        for modality in expected:
            if modality not in found_modalities:
                results['warnings'].append(f"Missing recommended scan: {modality}")
        
        # Check 3: File sizes reasonable
        for scan in scans:
            path = Path(scan['file_path'])
            if path.exists() and not self.bids_loader.is_stub_file(path):
                size_mb = path.stat().st_size / (1024 * 1024)
                if size_mb < 1:  # Suspiciously small
                    results['issues'].append(f"Suspiciously small file: {path.name} ({size_mb:.1f} MB)")
                    results['status'] = 'fail'
                elif size_mb > 500:  # Suspiciously large
                    results['warnings'].append(f"Large file: {path.name} ({size_mb:.1f} MB)")
        
        # Check 4: Metadata/JSON sidecar exists
        for scan in scans:
            nii_path = Path(scan['file_path'])
            json_path = nii_path.with_suffix('.json')
            if nii_path.exists() and not json_path.exists():
                results['warnings'].append(f"Missing JSON sidecar: {json_path.name}")
        
        # Set overall status
        if results['issues']:
            results['status'] = 'fail'
        elif results['warnings']:
            results['status'] = 'warning'
        else:
            results['status'] = 'pass'
        
        results['checks'] = {
            'total_scans': len(scans),
            'downloaded': sum(1 for s in scans if not self.bids_loader.is_stub_file(s['file_path'])),
            'stubs': sum(1 for s in scans if self.bids_loader.is_stub_file(s['file_path']))
        }
        
        return results
    
    def run_batch_qc(self, subject_ids: List[str], progress_callback=None) -> dict:
        """Run automated QC on multiple subjects."""
        results = {}
        total = len(subject_ids)
        
        for i, subject_id in enumerate(subject_ids):
            if progress_callback:
                progress_callback(i + 1, total, subject_id)
            
            # Run QC for each session
            subject_results = {}
            for session in ['2WK', '6MO']:
                session_result = self.run_subject_qc(subject_id, session)
                subject_results[session] = session_result
            
            # Overall status (worst of both sessions)
            statuses = [subject_results[s]['status'] for s in subject_results]
            if 'fail' in statuses:
                overall = 'fail'
            elif 'warning' in statuses:
                overall = 'warning'
            else:
                overall = 'pass'
            
            results[subject_id] = {
                'overall_status': overall,
                'sessions': subject_results
            }
        
        return results
```

**UI Updates:**

**QC Dashboard - Two Columns:**

```
┌─────────────────────────────────────────────────────────────┐
│ QC Dashboard                                                │
├─────────────────────────────────────────────────────────────┤
│ Subject ID  │ Auto QC │ Manual QC │ Notes    │ Actions      │
├─────────────┼─────────┼───────────┼──────────┼──────────────┤
│ TBI011007   │ ✓ Pass  │ ✓ Pass    │ Good     │ [View]       │
│ TBI011008   │ ⚠ Warn  │ - Pending │ Missing  │ [Review]     │
│ TBI011009   │ ✗ Fail  │ - Pending │ File err │ [Fix][Review]│
│ TBI011010   │ ✓ Pass  │ ✗ Fail    │ Motion   │ [View]       │
└─────────────────────────────────────────────────────────────┘

Legend:
✓ Pass - All checks passed
⚠ Warning - Minor issues (missing recommended scans, stubs)
✗ Fail - Critical issues (missing files, corrupt data)
- Pending - Not yet checked
```

**Subject Detail - Automated QC Card:**

```
┌─────────────────────────────────────────────────────────────┐
│ 🤖 Automated QC Results                    Last run: 2min ago│
├─────────────────────────────────────────────────────────────┤
│ Overall: ⚠ Warning                                          │
│                                                             │
│ ✓ Files exist and readable (10/10)                         │
│ ✓ File sizes reasonable                                    │
│ ⚠ 2 stub files (not downloaded)                            │
│ ⚠ Missing FLAIR scan                                       │
│ ✓ Metadata complete                                        │
│                                                             │
│ [Run QC Again] [View Details] [Export Report]              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 👤 Manual QC Review                                         │
├─────────────────────────────────────────────────────────────┤
│ Status: [Pass ▼]                                            │
│ Notes:  [Good quality, minor motion in T2w_________]        │
│ Flag: ☐ Needs attention                                    │
│                                                             │
│ [Update QC Status]                                          │
└─────────────────────────────────────────────────────────────┘
```

**Workflow Integration:**

```
1. User maps/downloads dataset
   ↓
2. Automated QC runs on all subjects (background)
   ↓ Results stored in database
3. Dashboard shows auto QC status
   - ✓ Pass: 120 subjects
   - ⚠ Warning: 25 subjects
   - ✗ Fail: 5 subjects
   ↓
4. User reviews flagged subjects (manual QC)
   - Opens subject detail
   - Sees automated issues
   - Adds human review notes
   - Sets manual QC status
   ↓
5. Export combined report
   - Auto QC + Manual QC columns
```

---

### Task 4: Enhanced Dashboard Statistics (4h) 🟡

**Add to Dashboard:**
- Total subjects/sessions/scans
- Modality breakdown (T1w: 150, T2w: 148, FLAIR: 145, etc.)
- Completeness metrics (both sessions vs single session)
- Dataset indexing date

**New Database Function:**
```python
# database.py
def get_modality_counts() -> dict:
    # Returns: {'T1w': 150, 'T2w': 148, ...}
```

---

### Task 5: Docker Deployment (6h) 🔴

**Create:** `Dockerfile`, `docker-compose.yml`, deployment docs

**Purpose:** Package entire application for easy deployment

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Initialize database
RUN python scripts/init_db.py

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  data-explorer:
    build: .
    container_name: data-explorer
    ports:
      - "8501:8501"
    volumes:
      # Persist database
      - ./data:/app/data
      # Mount BIDS dataset (read-only)
      - ${BIDS_ROOT}:/bids:ro
      # Optional: Mount download directory
      - ${DOWNLOAD_DIR:-./downloads}:/downloads
    environment:
      # Pennsieve credentials
      - PENNSIEVE_API_KEY=${PENNSIEVE_API_KEY}
      - PENNSIEVE_API_SECRET=${PENNSIEVE_API_SECRET}
      - PENNSIEVE_DATASET_NAME=${PENNSIEVE_DATASET_NAME}
      # Application config
      - BIDS_ROOT=/bids
      - DATABASE_PATH=/app/data/tracktbi.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Optional: nginx reverse proxy for production
  nginx:
    image: nginx:alpine
    container_name: data-explorer-nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - data-explorer
    restart: unless-stopped
    profiles:
      - production
```

**.env.example (for Docker):**

```bash
# Pennsieve Credentials
PENNSIEVE_API_KEY=your_api_key_here
PENNSIEVE_API_SECRET=your_api_secret_here
PENNSIEVE_DATASET_NAME=TrackTBI

# BIDS Dataset Location (on host)
BIDS_ROOT=/path/to/your/bids/dataset

# Download Directory (optional)
DOWNLOAD_DIR=/path/to/downloads
```

**Docker Deployment Documentation:**

```markdown
# Docker Deployment

## Quick Start

1. **Create .env file:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Start container:**
   ```bash
   docker-compose up -d
   ```

3. **Access application:**
   ```
   http://localhost:8501
   ```

## Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Update
docker-compose pull
docker-compose up -d

# Clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Production Deployment

```bash
# With nginx reverse proxy
docker-compose --profile production up -d
```

## Volumes

- `./data` - SQLite database (persisted)
- `${BIDS_ROOT}` - BIDS dataset (mounted read-only)
- `${DOWNLOAD_DIR}` - Downloads (optional)

## Environment Variables

Required:
- PENNSIEVE_API_KEY
- PENNSIEVE_API_SECRET
- PENNSIEVE_DATASET_NAME
- BIDS_ROOT

Optional:
- DOWNLOAD_DIR
- DATABASE_PATH

## Troubleshooting

**Container won't start:**
```bash
docker-compose logs data-explorer
```

**Permission issues:**
```bash
# Fix data directory permissions
sudo chown -R $USER:$USER ./data
```

**Network issues:**
```bash
# Check if port 8501 is available
lsof -i :8501
```
```

**Benefits of Docker Deployment:**

✅ **Zero Setup** - No Python installation needed  
✅ **Reproducible** - Same environment everywhere  
✅ **Isolated** - Doesn't affect host system  
✅ **Scalable** - Easy to deploy multiple instances  
✅ **Professional** - IT departments prefer containers  
✅ **Cross-platform** - Works on Mac, Windows, Linux

**Use Cases:**

- **Server deployment** - Lab server accessible to team
- **Multi-user** - Multiple containers for different users
- **Cloud deployment** - AWS, Azure, GCP
- **IT environments** - Organizations that use Docker
- **Production** - Stable, reproducible deployments

---

### Task 6: Download Progress UI (8h) 🔴

**Update:** `page_downloads()` in `app.py`

**Features:**
- Real-time progress bars during downloads
- Status updates: queued → downloading → completed/failed
- Batch download with per-file progress
- Error handling and retry logic

**Integration:**
```python
def start_downloads_with_agent():
    agent = PennsieveAgent()
    queue_items = dm.get_queue_items(status='queued')
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, item in enumerate(queue_items):
        def progress_callback(pct, msg):
            status_text.text(f"[{i+1}/{total}] {msg}")
            progress_bar.progress((i + pct/100) / total)
        
        success = agent.pull_file(item['file_path'], ..., progress_callback)
        dm.update_status(item['id'], 'completed' if success else 'failed')
    
    st.success("✓ All downloads complete!")
```

---

## UI Mockup: Metadata Filtering

```
┌────────────────────────────────────────────────────────────┐
│ 📊 Download Manager - Filter by Metadata                   │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Subject Filters         │  Scan Filters                  │
│  ─────────────────       │  ────────────                  │
│  ☑ Age: [18] to [45]    │  Sessions: ☑ 2WK  ☑ 6MO      │
│  Sex: ☑ M  ☑ F          │  Modalities: ☑ T1w ☑ T2w      │
│  Diagnosis: ☑ TBI       │  QC: ☑ Pass □ Pending         │
│                          │                                 │
├────────────────────────────────────────────────────────────┤
│ Preview: 23 subjects | Age 18-44 (mean 32.5) | ~2.3 GB   │
├────────────────────────────────────────────────────────────┤
│  [Add Filtered to Queue]  [Export List]  [Clear Filters]  │
└────────────────────────────────────────────────────────────┘
```

---

## Implementation Priority

**Week 1: Core Features**
1. Pennsieve Agent (8h) - Make downloads work
2. Metadata Filtering (6h) - Smart subject selection
3. Automated QC (6h) - Auto checks + separate columns
4. Dashboard Stats (4h) - Better overview
**Total: 24h**

**Week 2: UI & Deployment**
5. Docker Deployment (6h) - Containerize application
6. Download Progress UI (8h) - Real-time tracking
7. Metadata Display (2h) - Better scan info
8. QC Charts (3h) - Progress visualization
**Total: 19h**

**Week 3: Testing & Documentation**
9. End-to-end testing with real dataset
10. Test Docker deployment on different systems
11. Bug fixes and performance optimization
12. Documentation updates (native + Docker)

**Week 4: Beta & Launch**
13. Beta user testing (native and Docker)
14. Final bug fixes
15. Release v1.0

---

## File Structure

```
data-explorer/
├── app.py                      # Streamlit app (update pages)
├── src/
│   ├── database.py             ✅ Complete
│   ├── bids_loader.py          ✅ Complete
│   ├── pennsieve_client.py     ✅ Complete
│   ├── pennsieve_agent.py      🚫 CREATE NEW (map/download)
│   ├── metadata_filter.py      🚫 CREATE NEW (filter subjects)
│   ├── automated_qc.py         🚫 CREATE NEW (auto QC checks)
│   ├── download_manager.py     ⚠️  Needs Agent integration
│   ├── qc_manager.py           ⚠️  Needs auto QC integration
│   ├── theme.py                ✅ Complete
│   └── utils.py                ✅ Complete
├── Dockerfile                  🚫 CREATE NEW
├── docker-compose.yml          🚫 CREATE NEW
├── .dockerignore               🚫 CREATE NEW
├── .env.example                ⚠️  Update for Docker
├── requirements.txt            ⚠️  Add: pennsieve>=7.0.0 (includes CLI)
└── docs/
    └── DOCKER_DEPLOYMENT.md    🚫 CREATE NEW
```

---

## Testing Checklist

### Pennsieve Integration
- [ ] Agent detectable on system
- [ ] Credentials validation works
- [ ] Map dataset completes successfully
- [ ] Files show correct status (stub vs downloaded)
- [ ] Download single file works
- [ ] Download batch works with progress
- [ ] Resume interrupted downloads

### Metadata Filtering
- [ ] Load participants.tsv correctly
- [ ] Filter by age range
- [ ] Filter by categorical fields
- [ ] Combine multiple filters (AND logic)
- [ ] Preview shows accurate counts
- [ ] Size estimate reasonable
- [ ] Add filtered subjects to queue
- [ ] Export filtered list

### Automated QC
- [ ] Detects missing files
- [ ] Identifies stub files (not downloaded)
- [ ] Checks file sizes reasonable
- [ ] Detects missing metadata
- [ ] Flags missing expected scans
- [ ] Runs on all subjects quickly (< 10s for 150 subjects)
- [ ] Results stored in database
- [ ] Separate from manual QC status

### Download Manager
- [ ] Queue displays correctly
- [ ] Progress updates in real-time
- [ ] Status changes: queued → downloading → completed
- [ ] Failed downloads marked clearly
- [ ] Can retry failed downloads
- [ ] Storage estimates accurate

### Docker Deployment
- [ ] Docker image builds successfully
- [ ] Container starts without errors
- [ ] Application accessible on http://localhost:8501
- [ ] Database persists across container restarts
- [ ] BIDS dataset accessible from container
- [ ] Environment variables loaded correctly
- [ ] Volumes mounted properly
- [ ] Health check passes
- [ ] docker-compose up/down works
- [ ] Logs accessible via docker-compose logs
- [ ] Works on Mac, Windows, Linux
- [ ] Documentation clear and complete

---

## Success Criteria

**v1.0 is ready when:**
- ✅ Map dataset without downloading (Smart Mapping)
- ✅ Filter subjects by metadata (age, sex, diagnosis, etc.)
- ✅ Automated QC runs and flags issues (separate from manual QC)
- ✅ Manual QC workflow for human review
- ✅ Download specific files with progress tracking
- ✅ Dashboard shows comprehensive stats
- ✅ Export works for subjects and QC reports (both auto + manual)
- ✅ **Docker deployment works out of the box**
- ✅ **Two installation options: Native Python OR Docker**
- ✅ Tested with TrackTBI (150+ subjects)
- ✅ Performance: < 2s page loads, auto QC < 10s
- ✅ 3+ beta users successfully use it (both native and Docker)
- ✅ No critical bugs

---

## Example Workflow (v1.0)

### Installation Options

**Option A: Native Python**
```bash
./explorer install && ./explorer start
```

**Option B: Docker (Recommended for IT/Production)**
```bash
docker-compose up -d
# Access: http://localhost:8501
```

### Usage Workflow

```
1. Setup (5 minutes)
   ├─ Enter BIDS path, Pennsieve credentials
   ├─ Choose "Smart Mapping" (recommended)
   └─ System maps structure (no downloads)

2. Browse (instant)
   ├─ Dashboard shows 150 subjects, statistics
   ├─ Subject browser with search/filter
   └─ Subject detail shows all scans (stubs)

3. QC Workflow (ongoing)
   ├─ Automated QC runs on all subjects
   ├─ Dashboard shows: 120 pass, 25 warnings, 5 failed
   ├─ Review flagged subjects (manual QC)
   ├─ See automated issues + add human notes
   ├─ Update manual QC status
   └─ Export combined QC report (auto + manual)

4. Selective Download (2 minutes)
   ├─ Set filters: Age 18-45, TBI, Pass QC, T1w only
   ├─ Preview: 23 subjects, 1.2 GB
   ├─ Add to queue
   └─ Start downloads with progress
```

**Result:** Working with 150-subject dataset without downloading 60 GB!

---

## Next Steps (This Week)

**Week 1: Core Features**
- Day 1-2: Create `pennsieve_agent.py` (map, pull, progress)
- Day 2-3: Create `metadata_filter.py` + `automated_qc.py`
- Day 3-4: Integrate agent into setup + download UI
- Day 4-5: Integrate automated QC into dashboard + subject detail

**Week 2: UI & Docker**
- Day 6-7: Build download progress with real-time updates
- Day 8: Create Dockerfile + docker-compose.yml
- Day 9: Test Docker deployment on Mac/Windows/Linux
- Day 10: Documentation (native + Docker)

**Week 3: Testing**
- Day 11-12: Test end-to-end with TrackTBI dataset
- Day 13-14: Bug fixes, polish, performance optimization

**Week 4: Beta & Launch**
- Day 15-17: Beta user testing (native and Docker)
- Day 18-19: Final bug fixes
- Day 20: Release v1.0 🚀

---

## Prerequisites & Dependencies

### User Requirements

**Option 1: Native Installation**
```bash
# Required:
- Python 3.8+
- Pennsieve Agent (CLI tool)

# Installation:
pip install pennsieve
# OR
brew install pennsieve/tools/pennsieve  # macOS only
```

**Option 2: Docker Installation**
```bash
# Required:
- Docker Desktop (Mac/Windows) or Docker Engine (Linux)

# Pennsieve Agent included in container ✅
# No separate installation needed!
```

**Important:** Pennsieve Agent is a separate CLI tool that must be installed alongside Data Explorer (native) or is bundled in Docker.

---

## Handling Pennsieve Agent Installation

### Solution 1: Check on Startup (Native)

Add to `app.py`:
```python
def check_pennsieve_agent():
    """Check if Pennsieve Agent is installed."""
    import shutil
    
    agent_path = shutil.which('pennsieve')
    
    if not agent_path:
        st.error("""
        ⚠️ Pennsieve Agent not found!
        
        Data Explorer requires the Pennsieve Agent CLI tool for dataset mapping.
        
        **Install Pennsieve Agent:**
        
        **macOS:**
        ```
        brew install pennsieve/tools/pennsieve
        ```
        
        **Linux/Windows:**
        ```
        pip install pennsieve
        ```
        
        After installation, restart Data Explorer.
        
        [Installation Guide](https://docs.pennsieve.io/docs/pennsieve-agent)
        """)
        return False
    
    return True

# In main():
if not check_pennsieve_agent():
    st.stop()
```

### Solution 2: Auto-install via pip (Native)

Add to `requirements.txt`:
```txt
pennsieve>=7.0.0
```

The Pennsieve SDK includes the CLI tool when installed via pip.

### Solution 3: Bundle in Docker (Docker)

In `Dockerfile`:
```dockerfile
# Pennsieve Agent installation
RUN pip install --no-cache-dir pennsieve

# Verify installation
RUN pennsieve --version || echo "Warning: Pennsieve Agent not found"
```

**Docker users get it automatically!** ✅

---

## Recommended Approach

### For v1.0:

**Native Installation:**
1. Add `pennsieve` to `requirements.txt`
2. Auto-installs when user runs `./explorer install`
3. Add startup check with helpful error message
4. Link to docs if installation fails

**Docker Installation:**
1. Bundle Pennsieve Agent in Docker image
2. No user action needed
3. Works out of the box

### User Experience:

**Native:**
```bash
$ ./explorer install
Installing dependencies...
✓ Pennsieve Agent installed
✓ All dependencies ready

$ ./explorer start
Checking Pennsieve Agent... ✓
Launching Data Explorer...
```

**Docker:**
```bash
$ docker-compose up -d
✓ Pennsieve Agent included
✓ Ready to use immediately
```

---

## Resources Needed

### Development
- [ ] Pennsieve Agent installed on dev machine (auto via pip)
- [ ] Valid TrackTBI API credentials
- [ ] Sample participants.tsv for testing filters
- [ ] Network connection for download testing

### Docker Testing
- [ ] Docker Desktop installed (Mac/Windows) or Docker Engine (Linux)
- [ ] Test machines: macOS, Windows, Linux
- [ ] BIDS dataset for volume mounting
- [ ] Port 8501 available
- [ ] Verify Pennsieve Agent works in container

---

## Definition of Done

**Feature is DONE when:**
1. Code written and passes tests
2. Integrated into UI and working
3. Tested with real dataset
4. Documented with examples
5. No critical bugs
6. Performance acceptable

**v1.0 is DONE when:**
1. All 3 core features complete
2. Tested with 150+ subjects
3. 3+ beta users confirm it works
4. Documentation complete
5. Ready to share with research community

---

## Questions to Answer

- [ ] Is Pennsieve Agent installed? (`pennsieve --version`)
- [ ] Do we have test credentials?
- [ ] What's the expected dataset size?
- [ ] What metadata columns are in participants.tsv?
- [ ] Any known issues with Pennsieve API?

---

---

## v1.0 Deployment Options

**Two ways to run Data Explorer:**

| Feature | Native Python | Docker | 
|---------|--------------|--------|
| **Setup** | `./explorer install` | `docker-compose up -d` |
| **Requirements** | Python 3.8+ | Docker only |
| **Size** | ~150 MB | ~800 MB |
| **Speed** | Fast | Fast |
| **Updates** | `./explorer update` | `docker-compose pull` |
| **Best For** | Developers, researchers | IT depts, production, servers |
| **Multi-user** | No | Yes (multiple containers) |

**Both included in v1.0 release!**

---

**Focus:** Ship a great single-dataset tool with two deployment options.

**Ship v1.0. Then iterate.** 🚀

---

## What Happens After v1.0?

**This document ends here.** 

For future improvements and long-term vision, see:
📋 **[PENNSIEVE_MAPPING_INTEGRATION.md](PENNSIEVE_MAPPING_INTEGRATION.md)** - Future roadmap

**Includes:**
- Multi-dataset support (v2.0+)
- Advanced features (v1.1-1.5)
- Integration options (webhooks, extensions)
- Strategic vision

**First: Ship v1.0. Then: Evaluate based on user feedback.**
