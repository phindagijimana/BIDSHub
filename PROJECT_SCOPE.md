# Data Explorer - Project Scope

**Version:** 1.0  
**Status:** In Development - Production Readiness Phase  
**Last Updated:** February 6, 2026

---

## What is Data Explorer?

**Data Explorer is a local desktop application that helps researchers efficiently manage BIDS neuroimaging datasets stored on Pennsieve.**

Think of it as:
- 📁 A smart file browser for remote BIDS datasets
- 📥 A selective download manager (map structure, download only what you need)
- ✅ A quality control tracker for subject review workflows
- 📊 An export tool for sharing subject lists and QC reports

---

## Core Value Proposition

**Problem:** Researchers using Pennsieve for BIDS datasets face challenges:
- Must download entire datasets (100s of GB) to browse structure
- No way to track which subjects have been QC'd
- Difficult to selectively download specific subjects/sessions
- No centralized view across all subjects

**Solution:** Data Explorer provides:
- **Smart Mapping:** See full dataset structure without downloading files
- **Selective Downloads:** Download only the subjects/sessions you need
- **QC Tracking:** Track review status, add notes, flag subjects
- **Local Database:** Fast search, filter, and browse
- **Export Tools:** Generate reports for analysis pipelines

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│           User's Local Computer                 │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │   Data Explorer (Streamlit App)           │ │
│  │   - Browse subjects                       │ │
│  │   - Track QC status                       │ │
│  │   - Manage downloads                      │ │
│  │   - Export reports                        │ │
│  └─────────────┬─────────────────────────────┘ │
│                │                                 │
│  ┌─────────────┴─────────────────────────────┐ │
│  │   Local SQLite Database                   │ │
│  │   - Subjects table                        │ │
│  │   - Scans metadata                        │ │
│  │   - Download queue                        │ │
│  │   - QC notes                              │ │
│  └─────────────┬─────────────────────────────┘ │
│                │                                 │
│  ┌─────────────┴─────────────────────────────┐ │
│  │   Python Backend                          │ │
│  │   - PyBIDS (BIDS parsing)                 │ │
│  │   - Pennsieve SDK (API access)            │ │
│  │   - Pennsieve Agent (mapping/downloads)   │ │
│  └───────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────┘
                  │
                  │ API Calls
                  │
┌─────────────────▼───────────────────────────────┐
│           Pennsieve Cloud Platform              │
│                                                 │
│  - BIDS dataset storage                         │
│  - File metadata                                │
│  - Permission management                        │
│  - File downloads                               │
└─────────────────────────────────────────────────┘
```

---

## Technology Stack

### Frontend
- **Streamlit** - Web-based UI framework (Python)
- Custom theming (Chase Bank navy blue)

### Backend
- **Python 3.8+** - Core language
- **SQLite** - Local database
- **PyBIDS** - BIDS dataset parsing
- **Pennsieve SDK** - Cloud API access
- **Pandas** - Data manipulation

### Distribution
- **Native:** Python virtual environment + CLI
- **Docker:** (Future) Containerized deployment
- **Electron:** (Future) Desktop app with bundled Python

---

## What's In Scope ✅

### Core Features (v1.0)
- [x] Setup wizard for Pennsieve connection
- [x] Subject browser with search/filter
- [x] Session and scan visualization
- [x] QC status tracking (pending, pass, fail, needs_review)
- [x] QC notes per subject
- [x] Download queue management
- [x] Progress tracking for downloads
- [x] Export subject lists (CSV)
- [x] Export QC reports
- [ ] Smart dataset mapping (Pennsieve Agent)
- [ ] Selective file downloads
- [ ] Dashboard with statistics

### Technical Requirements
- [ ] Cross-platform (macOS, Windows, Linux)
- [ ] Performance: 500+ subjects
- [ ] Error handling and logging
- [ ] Data backup/restore
- [ ] Comprehensive documentation
- [ ] Unit and integration tests

---

## What's Out of Scope ❌

### Not Planned for v1.0
- ❌ Multi-user support (single user per installation)
- ❌ Web server deployment (local only)
- ❌ User authentication system (uses Pennsieve credentials)
- ❌ Real-time collaboration
- ❌ Webhook integrations
- ❌ Browser extensions
- ❌ Embedded in Pennsieve UI
- ❌ Mobile apps
- ❌ Cloud storage (data lives on user's computer + Pennsieve)
- ❌ Data processing/analysis (use other tools for that)
- ❌ DICOM conversion
- ❌ Neuroimaging viewers (use FSLeyes, Slicer, etc.)

### Explicitly NOT Building
- **Not a Pennsieve replacement** - Complements it
- **Not a BIDS validator** - Use bids-validator
- **Not an analysis pipeline** - Use fMRIPrep, etc.
- **Not a neuroimaging viewer** - Use existing tools
- **Not a server application** - Runs locally

---

## Target Users

### Primary
- **Researchers** managing BIDS datasets on Pennsieve
- **Data managers** tracking QC status across subjects
- **Lab members** downloading specific subjects for analysis

### User Personas

**Dr. Sarah (Principal Investigator)**
- Needs: Overview of dataset status, QC progress
- Uses: Dashboard, QC reports, subject browser
- Pain point: "Which subjects are ready for analysis?"

**Mike (PhD Student)**
- Needs: Download specific subjects for processing
- Uses: Subject browser, download manager, selective downloads
- Pain point: "Don't want to download 200 GB to analyze 10 subjects"

**Lisa (Data Manager)**
- Needs: Track QC status, coordinate with team
- Uses: QC dashboard, notes, exports
- Pain point: "Need to know what's been reviewed and what needs attention"

---

## Design Principles

### 1. Local-First
- Works offline after initial download
- Fast (local database)
- No server setup required
- User owns their data

### 2. Simple & Focused
- Does ONE thing well: BIDS + Pennsieve + QC
- No feature creep
- Intuitive UI for non-programmers
- Quick to learn (< 10 minutes)

### 3. Reliable
- Graceful error handling
- Resume interrupted downloads
- Never lose data
- Clear error messages

### 4. Efficient
- Smart mapping (structure without files)
- Selective downloads
- Caching for performance
- Minimal storage footprint

### 5. Open & Extensible
- Open source
- Clear code structure
- Python ecosystem (easy to extend)
- Export data in standard formats

---

## Non-Goals

These are things we're explicitly **NOT** trying to achieve:

1. **Replace Pennsieve** - Data Explorer complements Pennsieve, doesn't replace it
2. **Real-time collaboration** - Single user workflow is sufficient
3. **Universal BIDS tool** - Optimized for Pennsieve datasets specifically
4. **All-in-one platform** - Focus on browse/QC/download, not analysis
5. **Enterprise features** - No user management, audit logs, compliance features
6. **Perfect UI** - Good enough for researchers, not winning design awards
7. **Zero configuration** - Some setup required (Pennsieve credentials)
8. **AI/ML features** - Leave that to analysis tools
9. **Data processing** - Export to analysis pipelines, don't do processing

---

## Success Criteria

### v1.0 Launch Ready When:

**Functionality**
- ✅ All core features work reliably
- ✅ Handles 500+ subjects without performance issues
- ✅ Zero data loss scenarios
- ✅ Graceful error recovery

**Quality**
- ✅ 80% test coverage
- ✅ All critical paths tested
- ✅ Cross-platform verified
- ✅ No critical bugs

**User Experience**
- ✅ Setup completes in < 5 minutes
- ✅ Documentation covers all features
- ✅ Error messages actionable
- ✅ Beta users rate 4+/5

**Deployment**
- ✅ One-command installation
- ✅ Reliable updates
- ✅ Troubleshooting guide
- ✅ Works on fresh systems

---

## Roadmap

### Phase 1: v1.0 Production Ready (CURRENT)
**Timeline:** 4-6 weeks  
**Focus:** Complete core features, testing, documentation

**Deliverables:**
- All checklist items from PRODUCTION_READINESS.md
- Comprehensive documentation
- Beta testing with real users
- Bug fixes and polish

### Phase 2: Deployment Options
**Timeline:** 2-3 months after v1.0  
**Focus:** Alternative deployment methods

**Deliverables:**
- Docker containerization
- One-line installer script
- Package managers (Homebrew, Chocolatey)
- Simplified setup for non-technical users

### Phase 3: Enhanced Features (If Needed)
**Timeline:** 6+ months, based on user feedback  
**Focus:** Features users actually request

**Possible Additions:**
- Webhook integration (if auto-sync needed)
- Batch operations
- Advanced filtering
- Custom reports
- Integration improvements

### Phase 4: Desktop App (Optional)
**Timeline:** 12+ months, if demand exists  
**Focus:** Native Electron application

**Deliverables:**
- Electron version with same features
- Installers for Mac/Windows/Linux
- Auto-update mechanism
- Migration path from Streamlit

---

## Decision Framework

When evaluating new features, ask:

### Should we add this feature?

**✅ YES if:**
- Directly supports core workflow (browse, QC, download)
- Requested by multiple users
- Low maintenance burden
- Fits local-first architecture
- Solves real pain point

**❌ NO if:**
- Adds significant complexity
- Requires server infrastructure
- Only 1 user wants it
- Better solved by another tool
- Out of scope (see list above)
- Would delay v1.0 launch

### Example Decisions

**Feature Request: "Add image viewer"**
- ❌ NO - Out of scope, use FSLeyes/Slicer

**Feature Request: "Bulk QC status updates"**
- ✅ YES - Core QC workflow, simple to add

**Feature Request: "Multi-user with permissions"**
- ❌ NO - Adds major complexity, changes architecture

**Feature Request: "Export to Excel"**
- ✅ YES - Simple, useful for sharing

**Feature Request: "Run fMRIPrep from app"**
- ❌ NO - Out of scope, use separate pipeline

---

## Communication Guidelines

### Describing Data Explorer

**Elevator Pitch (30 seconds):**
"Data Explorer is a desktop app that helps researchers manage BIDS datasets stored on Pennsieve. It lets you browse subjects, track quality control status, and selectively download data without needing the entire dataset locally."

**One-liner:**
"A local desktop app for browsing, QC tracking, and selective downloading of Pennsieve BIDS datasets."

**NOT this:**
- "A Pennsieve tool" (it's independent)
- "A BIDS validator" (wrong tool)
- "A cloud application" (it's local)
- "An analysis platform" (just browse/QC)

### Setting Expectations

**What users should expect:**
- Local application (runs on your computer)
- Requires Python 3.8+ (or Docker)
- Setup takes 5 minutes
- Works offline after initial sync
- Single user per installation

**What users should NOT expect:**
- Web application accessible anywhere
- Real-time sync with Pennsieve
- Built-in image viewing
- Data analysis features
- Zero setup required

---

## Measuring Success

### Metrics (Optional)

**Adoption:**
- Number of installations
- Active users per week
- Datasets managed

**Usage:**
- Subjects indexed
- Files downloaded via app
- QC reviews completed
- Reports exported

**Quality:**
- Bug report rate
- User satisfaction (surveys)
- Documentation clarity ratings
- Time to first successful setup

**Performance:**
- Startup time
- Subject list load time
- Search response time
- Download success rate

---

## Conclusion

Data Explorer is a **focused, local application** that does one thing well: helps researchers efficiently work with Pennsieve BIDS datasets through smart downloading, organized QC tracking, and easy exports.

**Keep it simple. Keep it local. Keep it focused.**

Any feature that doesn't serve this core mission should be questioned, no matter how cool it seems.

---

## Questions?

If you're unsure whether something is in scope:

1. Check this document
2. Ask: "Does this help browse/QC/download BIDS data from Pennsieve?"
3. Ask: "Does this require server infrastructure or multi-user support?"
4. Ask: "Would this delay the v1.0 launch?"
5. When in doubt, defer to post-v1.0

**Remember:** Ship a great v1.0 first. Everything else can wait.
