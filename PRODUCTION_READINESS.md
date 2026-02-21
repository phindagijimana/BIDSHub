# Production Readiness Checklist

**Status:** 🟡 In Progress  
**Target:** Stable v1.0 Release  
**Timeline:** 4-6 weeks

---

## Progress Overview

```
Backend:        ████████░░  80%
Frontend:       ███████░░░  70%
Testing:        ████░░░░░░  40%
Documentation:  ██████░░░░  60%
Security:       ███░░░░░░░  30%
Deployment:     ████████░░  80%

Overall:        ██████░░░░  60%
```

---

## 1. Backend Stability ⚙️

### Database Schema
- [x] Subjects table with QC fields
- [x] Scans table with metadata
- [x] Download queue table
- [ ] Add indexes for common queries
- [ ] Add database versioning/migrations
- [ ] Add foreign key constraints
- [ ] Test with 1000+ subjects

**Action Items:**
```sql
-- Add in database.py
CREATE INDEX idx_subjects_qc_status ON subjects(qc_status);
CREATE INDEX idx_subjects_flagged ON subjects(flagged);
CREATE INDEX idx_scans_subject ON scans(subject_id);
CREATE INDEX idx_downloads_status ON download_queue(status);
```

### Error Handling
- [x] Basic try/catch in main operations
- [ ] Graceful Pennsieve connection failures
- [ ] Network timeout handling
- [ ] Disk space checks before downloads
- [ ] Database corruption recovery
- [ ] Invalid BIDS structure handling

**Action Items:**
1. Add `src/error_handler.py` with custom exceptions
2. Wrap all Pennsieve API calls with retry logic
3. Add connection health checks on startup

### Logging
- [ ] Structured logging (JSON format)
- [ ] Log levels (DEBUG, INFO, WARN, ERROR)
- [ ] Log rotation (prevent huge files)
- [ ] User action audit trail
- [ ] Performance metrics logging

**Action Items:**
```python
# Add to app.py
import logging
import logging.handlers

def setup_logging():
    logger = logging.getLogger('data_explorer')
    handler = logging.handlers.RotatingFileHandler(
        'logs/app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
```

### Performance
- [ ] Cache BIDS dataset structure
- [ ] Lazy load subject scans
- [ ] Paginate large subject lists
- [ ] Optimize database queries
- [ ] Profile memory usage
- [ ] Test with 2000+ subjects

**Action Items:**
1. Add `@st.cache_data` to expensive operations
2. Implement pagination in subjects table
3. Profile with `cProfile` and optimize bottlenecks

---

## 2. User Experience 🎨

### Setup Wizard
- [x] Basic configuration form
- [ ] Step-by-step wizard (vs all-at-once)
- [ ] Connection test button
- [ ] BIDS validation before proceeding
- [ ] Progress indicators with ETA
- [ ] Ability to cancel/retry

**Action Items:**
1. Split setup into 3 steps: BIDS → Credentials → Initialize
2. Add "Test Connection" button before full initialization
3. Show estimated time based on subject count

### Loading States
- [x] Basic spinners
- [ ] Progress bars for long operations
- [ ] ETA calculations
- [ ] Cancellable operations
- [ ] Background task status
- [ ] Toast notifications for completion

**Action Items:**
```python
# Enhance all long operations:
with st.spinner("Indexing subjects..."):
    progress = st.progress(0)
    for i, subject in enumerate(subjects):
        # Process subject
        progress.progress((i + 1) / len(subjects))
```

### Help & Tooltips
- [ ] Tooltips for all icons/buttons
- [ ] Help text for complex features
- [ ] In-app documentation links
- [ ] "What's this?" expandable sections
- [ ] Video tutorials embedded

**Action Items:**
1. Add `help` parameter to all inputs
2. Create "Help" sidebar section with FAQ
3. Record 5-minute walkthrough video

### Keyboard Shortcuts
- [ ] Ctrl+S to save QC notes
- [ ] Ctrl+F to focus search
- [ ] Esc to close modals
- [ ] Arrow keys for navigation
- [ ] Keyboard shortcut legend

**Action Items:**
1. Document desired shortcuts
2. Implement with Streamlit keyboard component (if available)
3. Add shortcuts guide to help section

---

## 3. Data Integrity 🔒

### Input Validation
- [ ] Validate BIDS directory structure
- [ ] Check Pennsieve credentials format
- [ ] Validate dataset name exists
- [ ] File path sanitization
- [ ] SQL injection prevention

**Action Items:**
```python
# Add src/validators.py
def validate_bids_directory(path: str) -> bool:
    """Validate BIDS directory structure."""
    required = ['dataset_description.json', 'participants.tsv']
    return all((Path(path) / f).exists() for f in required)

def validate_pennsieve_credentials(api_key: str, secret: str) -> bool:
    """Validate credential format."""
    # Add format checks
    return len(api_key) > 0 and len(secret) > 0
```

### Database Integrity
- [x] Basic schema
- [ ] Foreign key constraints
- [ ] Transaction support
- [ ] Rollback on errors
- [ ] Integrity checks on startup
- [ ] Automatic backups

**Action Items:**
```python
# Add to database.py
def enable_foreign_keys(self):
    self.conn.execute("PRAGMA foreign_keys = ON")

def begin_transaction(self):
    self.conn.execute("BEGIN TRANSACTION")

def commit(self):
    self.conn.commit()

def rollback(self):
    self.conn.rollback()
```

### Backup & Restore
- [ ] Automatic daily backups
- [ ] Manual backup command
- [ ] Restore from backup
- [ ] Export database as JSON
- [ ] Import from previous version

**Action Items:**
```bash
# Add CLI commands
./explorer backup          # Create timestamped backup
./explorer restore latest  # Restore from latest backup
./explorer export data.json
```

---

## 4. Security 🛡️

### Credential Management
- [x] .env file support
- [ ] Encrypt .env at rest
- [ ] Keyring integration (OS secure storage)
- [ ] Credential validation
- [ ] API key rotation support
- [ ] Don't log credentials

**Action Items:**
```python
# Use keyring for secure storage
import keyring

def save_credentials(api_key: str, secret: str):
    keyring.set_password("data_explorer", "api_key", api_key)
    keyring.set_password("data_explorer", "api_secret", secret)

def get_credentials():
    return (
        keyring.get_password("data_explorer", "api_key"),
        keyring.get_password("data_explorer", "api_secret")
    )
```

### API Safety
- [ ] Rate limiting for Pennsieve API
- [ ] Retry with exponential backoff
- [ ] Request timeout limits
- [ ] Connection pooling
- [ ] API usage tracking

**Action Items:**
1. Wrap Pennsieve client with rate limiter
2. Add max retries configuration
3. Log API usage statistics

### Session Security
- [ ] Session timeout (if multi-user)
- [ ] CSRF protection (if needed)
- [ ] Secure headers
- [ ] Input sanitization
- [ ] XSS prevention

**Action Items:**
1. Review Streamlit security best practices
2. Add security headers if deploying publicly
3. Sanitize all user inputs

---

## 5. Testing 🧪

### Unit Tests
- [ ] Database operations
- [ ] BIDS loader functions
- [ ] Pennsieve client methods
- [ ] QC manager logic
- [ ] Download manager
- [ ] Utils functions

**Action Items:**
```bash
# Create tests/unit/
tests/
├── unit/
│   ├── test_database.py
│   ├── test_bids_loader.py
│   ├── test_pennsieve_client.py
│   ├── test_qc_manager.py
│   └── test_download_manager.py
```

### Integration Tests
- [ ] Setup wizard flow
- [ ] Subject browsing workflow
- [ ] Download queue workflow
- [ ] QC update workflow
- [ ] Export functionality

**Action Items:**
```python
# tests/integration/test_workflows.py
def test_full_setup_workflow():
    # Test complete initialization
    pass

def test_download_workflow():
    # Test queueing and downloading
    pass
```

### End-to-End Tests
- [ ] Fresh install test
- [ ] Database migration test
- [ ] Cross-platform compatibility
- [ ] Large dataset performance
- [ ] Edge cases and error scenarios

**Action Items:**
1. Create E2E test checklist
2. Test on fresh VMs (Mac, Windows, Linux)
3. Test with real TrackTBI dataset

### Performance Benchmarks
- [ ] Startup time < 5 seconds
- [ ] Subject list load < 2 seconds (1000 subjects)
- [ ] Search response < 500ms
- [ ] Page navigation < 1 second
- [ ] Memory usage < 500 MB

**Action Items:**
```python
# tests/performance/benchmark.py
import time
import pytest

def test_subject_list_performance():
    start = time.time()
    subjects = db.get_all_subjects()
    elapsed = time.time() - start
    assert elapsed < 2.0, f"Too slow: {elapsed}s"
```

---

## 6. Documentation 📚

### User Documentation
- [x] README.md (basic)
- [ ] QUICKSTART.md with screenshots
- [ ] USER_GUIDE.md (comprehensive)
- [ ] TROUBLESHOOTING.md
- [ ] FAQ.md
- [ ] Video tutorials (5-10 minutes each)

**Action Items:**
1. Screenshot all major features
2. Write step-by-step guides for common tasks
3. Record screen capture tutorials
4. Create troubleshooting decision tree

### Developer Documentation
- [ ] API documentation (docstrings)
- [ ] Module architecture diagram
- [ ] Database schema documentation
- [ ] Contributing guide
- [ ] Development setup guide
- [ ] Code style guide

**Action Items:**
```python
# Add comprehensive docstrings
def get_subjects(self, filters: dict = None) -> list:
    """
    Get all subjects matching filters.
    
    Args:
        filters: Dictionary of filter criteria
            - qc_status: str (pending, pass, fail, needs_review)
            - has_2wk: bool
            - has_6mo: bool
    
    Returns:
        List of subject dictionaries
    
    Example:
        >>> subjects = db.get_subjects({'qc_status': 'pass'})
    """
```

### Release Documentation
- [ ] CHANGELOG.md
- [ ] Version numbering strategy
- [ ] Release notes template
- [ ] Migration guides
- [ ] Breaking changes log

**Action Items:**
1. Start CHANGELOG.md with v1.0.0 section
2. Document all features for v1.0
3. Create release checklist

---

## 7. Deployment & Distribution 🚀

### Installation
- [x] Cross-platform CLI
- [ ] One-line installer
- [ ] Windows installer (.exe)
- [ ] macOS installer (.pkg)
- [ ] Linux package (deb/rpm)
- [ ] Homebrew formula

**Action Items:**
```bash
# Create install script
# install.sh
#!/bin/bash
curl -fsSL https://raw.githubusercontent.com/user/data-explorer/main/install.sh | bash
```

### System Service
- [ ] Systemd service file (Linux)
- [ ] Launchd plist (macOS)
- [ ] Windows service
- [ ] Auto-start on boot option
- [ ] Service management commands

**Action Items:**
```bash
# Add service commands
./explorer install-service   # Install system service
./explorer enable-autostart  # Enable auto-start
./explorer disable-autostart # Disable auto-start
```

### Updates
- [x] Manual update via git
- [ ] Version check on startup
- [ ] Automatic update notifications
- [ ] In-app update mechanism
- [ ] Rollback to previous version

**Action Items:**
```python
# Add version checking
def check_for_updates():
    current = "1.0.0"
    latest = requests.get("https://api.github.com/repos/user/data-explorer/releases/latest")
    if latest.json()['tag_name'] > current:
        st.warning("New version available!")
```

---

## 8. Monitoring & Maintenance 📊

### Health Checks
- [ ] Application health endpoint
- [ ] Database connection check
- [ ] Pennsieve API check
- [ ] Disk space monitoring
- [ ] Memory usage tracking

**Action Items:**
```python
# Add health check endpoint
def health_check():
    checks = {
        'database': test_db_connection(),
        'pennsieve': test_pennsieve_connection(),
        'disk_space': check_disk_space() > 1_000_000_000,  # 1GB
    }
    return all(checks.values()), checks
```

### Error Reporting
- [ ] Crash reporting
- [ ] Error log aggregation
- [ ] Anonymous usage statistics
- [ ] Bug report template
- [ ] User feedback form

**Action Items:**
1. Add "Report Bug" button in app
2. Create GitHub issue template
3. Add optional telemetry (privacy-first)

### Analytics (Optional)
- [ ] Usage tracking (privacy-first)
- [ ] Feature adoption metrics
- [ ] Performance metrics
- [ ] Error rate tracking
- [ ] User flow analysis

**Action Items:**
1. Decide on analytics strategy
2. Add opt-in telemetry
3. Create privacy policy

---

## Priority Matrix

### Critical (Before v1.0 Launch) 🔴
- [ ] All database indexes added
- [ ] Error handling for Pennsieve failures
- [ ] Input validation on all forms
- [ ] Backup/restore functionality
- [ ] Basic unit tests (80% coverage)
- [ ] User documentation complete
- [ ] Cross-platform testing
- [ ] Performance benchmarks met

### High Priority (First patch) 🟠
- [ ] Comprehensive logging
- [ ] Integration tests
- [ ] Advanced error recovery
- [ ] In-app help system
- [ ] Credential encryption
- [ ] One-line installer

### Medium Priority (v1.1) 🟡
- [ ] Keyboard shortcuts
- [ ] Auto-update mechanism
- [ ] Performance optimizations
- [ ] Video tutorials
- [ ] System service support
- [ ] Health monitoring

### Low Priority (Future) 🟢
- [ ] Advanced analytics
- [ ] Crash reporting service
- [ ] Automated backups
- [ ] Multi-language support
- [ ] Plugin system

---

## Test Plan for Beta Release

### Week 1: Internal Testing
- [ ] Install on fresh systems (Mac, Windows, Linux)
- [ ] Complete setup wizard with real credentials
- [ ] Index 100+ subjects
- [ ] Test all navigation flows
- [ ] Test download manager
- [ ] Test QC workflow
- [ ] Export all data types
- [ ] Stress test with 1000+ subjects

### Week 2: Beta User Testing
- [ ] Recruit 3-5 beta users
- [ ] Provide setup guide
- [ ] Collect feedback via survey
- [ ] Monitor issues closely
- [ ] Daily check-ins
- [ ] Document all bugs

### Week 3: Bug Fixes
- [ ] Fix critical bugs
- [ ] Address usability issues
- [ ] Improve documentation
- [ ] Add missing features
- [ ] Retest all workflows

### Week 4: Launch Preparation
- [ ] Final testing round
- [ ] Update documentation
- [ ] Create release notes
- [ ] Tag v1.0.0 release
- [ ] Announce to users

---

## Success Criteria for v1.0 Release

### Functionality
- ✅ All core features work
- ✅ No critical bugs
- ✅ Handles 500+ subjects smoothly
- ✅ Pennsieve integration stable
- ✅ Cross-platform compatibility

### Quality
- ✅ 80% test coverage
- ✅ All critical paths tested
- ✅ Error handling robust
- ✅ Performance acceptable
- ✅ Security best practices followed

### User Experience
- ✅ Setup wizard intuitive
- ✅ Documentation complete
- ✅ Help available in-app
- ✅ Error messages clear
- ✅ Positive user feedback (4+/5)

### Deployment
- ✅ One-command install
- ✅ Reliable startup/shutdown
- ✅ Updates work smoothly
- ✅ Logs useful for debugging
- ✅ Backup/restore functional

---

## Next Steps (This Week)

1. **Add database indexes** (2 hours)
2. **Implement error handling for Pennsieve** (4 hours)
3. **Add input validation** (4 hours)
4. **Write critical unit tests** (8 hours)
5. **Update documentation** (4 hours)
6. **Test on fresh systems** (4 hours)

**Total:** ~26 hours (~1 week)

---

## Tracking Progress

Update this file weekly with completed items. Use this format:

```
## Week of [Date]
Completed:
- [x] Item 1
- [x] Item 2

In Progress:
- [ ] Item 3 (50% done)

Blocked:
- [ ] Item 4 (waiting for Pennsieve API fix)

Next Week:
- [ ] Item 5
- [ ] Item 6
```
