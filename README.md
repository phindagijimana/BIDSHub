# Data Explorer

**A local desktop application for efficiently managing BIDS neuroimaging datasets stored on Pennsieve.**

Browse subjects, track quality control status, and selectively download data - all from your computer.

## What is Data Explorer?

Data Explorer is a **local desktop application** that helps you work with BIDS datasets stored on Pennsieve without downloading everything. Think of it as a smart file browser with QC tracking.

**Perfect for:**
- 📊 Tracking which subjects have been quality-checked
- 🎯 Downloading only the subjects/sessions you need
- 📁 Browsing dataset structure before downloading files
- 📝 Adding review notes and flagging subjects
- 📤 Exporting subject lists for analysis pipelines

**Not designed for:**
- ❌ Multi-user collaboration (single user per installation)
- ❌ Image viewing (use FSLeyes, Slicer, etc.)
- ❌ Data analysis (use fMRIPrep, etc.)
- ❌ Cloud/server deployment (runs locally)

## Features

- **Subject Browser** - Search, filter, and explore subjects
- **Quality Control** - Track QC status, add notes, bulk updates
- **Download Manager** - Queue-based downloads with progress tracking
- **Smart Mapping** - See dataset structure without downloading files
- **Dashboard** - Real-time statistics and metrics
- **Pennsieve Integration** - Sync with your Pennsieve datasets
- **Export** - CSV exports for analysis pipelines

## Tech Stack

Python • Streamlit • SQLite • PyBIDS • Pennsieve SDK

## Quick Start

### Option 1: Native Python
```bash
# Clone repository
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer

# Install (one command)
./explorer install

# Launch
./explorer start
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

**Benefits of Docker:** Zero setup, reproducible environment, works everywhere.

### First Run Setup

1. Enter BIDS directory path
2. Enter Pennsieve credentials (API key, secret, dataset name)
3. Click "Initialize Dataset"
4. Wait for indexing (~2-5 minutes)

**Done!** Dashboard opens automatically.

## CLI Commands

```bash
./explorer <command>        # macOS/Linux
explorer <command>          # Windows
```

**Cross-platform:** Same commands work everywhere.

See [QUICKSTART.md](QUICKSTART.md) for all available commands.

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

**Port conflict?**
- CLI automatically finds available port (8500-8550)

**Can't connect to Pennsieve?**
- Verify credentials are correct
- Check internet connection
- Ensure dataset name is exact (case-sensitive)

**Database issues?**
```bash
./explorer clean
./explorer install
```

**More help:**
```bash
./explorer help
./explorer status
./explorer logs
```

## Documentation

**Not sure which doc to read?** → [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md)

### For Users
- [QUICKSTART.md](QUICKSTART.md) - 2-minute setup guide
- [PROJECT_SCOPE.md](PROJECT_SCOPE.md) - What Data Explorer is (and isn't)

### For Developers

**Building v1.0 (MVP)?**
- ⭐ **[V1_IMPLEMENTATION_PLAN.md](V1_IMPLEMENTATION_PLAN.md)** - Start here!
  - Actionable tasks for v1.0
  - What we're building NOW
  - Time estimates and testing checklist

**Planning future features?**
- 🔮 **[PENNSIEVE_MAPPING_INTEGRATION.md](PENNSIEVE_MAPPING_INTEGRATION.md)** - Read after v1.0
  - Features for v1.1+
  - Long-term vision (v2.0+)
  - Ideas to evaluate after v1.0

**Other:**
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) - Production checklist (detailed)
- [DOCUMENTATION_GUIDE.md](DOCUMENTATION_GUIDE.md) - Which doc to read when

## Requirements

### Native Installation
- Python 3.8+
- Pennsieve account with API credentials
- BIDS-formatted dataset
- Pennsieve Agent (auto-installed with `./explorer install`)

### Docker Installation
- Docker Desktop (Mac/Windows) or Docker Engine (Linux)
- Pennsieve account with API credentials
- BIDS-formatted dataset
- **No Python or Pennsieve Agent needed** (bundled in container)

## License

MIT License - see [LICENSE](LICENSE) file

## Support

- **Issues**: [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues)
- **Documentation**: [QUICKSTART.md](QUICKSTART.md)
- **Questions**: Open an issue

---

**Version**: 1.0.0 (MVP)  
**Status**: Production Ready  
**Last Updated**: February 2026
