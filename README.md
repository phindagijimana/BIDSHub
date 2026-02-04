# Data Explorer

A professional web application for managing BIDS neuroimaging datasets on the Pennsieve platform.

## Features

- **Subject Browser** - Search, filter, and explore subjects
- **Quality Control** - Track QC status, add notes, bulk updates
- **Download Manager** - Queue-based downloads with progress tracking
- **Dashboard** - Real-time statistics and metrics
- **Pennsieve Integration** - Direct cloud access to imaging files
- **Export** - CSV exports for analysis pipelines

## Tech Stack

Python • Streamlit • SQLite • PyBIDS • Pennsieve SDK

## Quick Start

```bash
# Clone repository
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer

# Install (one command)
python bin/explorer.py install

# Launch
python bin/explorer.py start
```

The browser opens automatically at `http://localhost:8501` (or next available port).

### First Run Setup

1. Enter BIDS directory path
2. Enter Pennsieve credentials (API key, secret, dataset name)
3. Click "Initialize Dataset"
4. Wait for indexing (~2-5 minutes)

**Done!** Dashboard opens automatically.

## CLI Commands

```bash
python bin/explorer.py <command>
```

**Works on macOS, Linux, and Windows.**

| Command | Description |
|---------|-------------|
| `install` | Install dependencies and setup |
| `start` | Start application |
| `stop` | Stop application |
| `restart` | Restart application |
| `status` | Check status (PID, port, CPU, memory) |
| `logs` | View live logs |
| `update` | Update code and dependencies |
| `test` | Run tests |
| `config` | Show configuration |
| `help` | Show all commands |

## Configuration

Optional: Create `.env` file:

```env
BIDS_ROOT=/path/to/bids/dataset
PENNSIEVE_API_KEY=your_key
PENNSIEVE_API_SECRET=your_secret
PENNSIEVE_DATASET_NAME=your_dataset
```

Or configure via UI on first launch.

## Project Structure

```
data-explorer/
├── app.py                    # Main application
├── bin/                      # CLI tools
│   ├── explorer.py          # Cross-platform CLI (recommended)
│   ├── explorer             # Unix CLI
│   ├── explorer.bat         # Windows CLI
│   └── launch.*             # Alternative launchers
├── src/
│   ├── bids_loader.py       # BIDS integration
│   ├── pennsieve_client.py  # Cloud API client
│   ├── database.py          # Data storage
│   ├── download_manager.py  # Downloads
│   ├── qc_manager.py        # Quality control
│   ├── theme.py             # UI styling
│   └── utils.py             # Helpers
├── scripts/                  # Internal utilities
│   └── init_db.py           # Database setup
├── data/                     # Local storage
└── tests/                    # Tests
```

## Troubleshooting

**Port conflict?**
- CLI automatically finds available port (8500-8550)

**Can't connect to Pennsieve?**
- Verify credentials are correct
- Check internet connection
- Ensure dataset name is exact (case-sensitive)

**Database issues?**
```bash
python bin/explorer.py clean
python bin/explorer.py install
```

**More help:**
```bash
python bin/explorer.py help
python bin/explorer.py status
python bin/explorer.py logs
```

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - 2-minute setup guide
- [docs/SETUP.md](docs/SETUP.md) - Detailed setup instructions

## Requirements

- Python 3.8+
- Pennsieve account with API credentials
- BIDS-formatted dataset

## License

MIT License - see [LICENSE](LICENSE) file

## Support

- **Issues**: [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues)
- **Documentation**: See `docs/` directory
- **Questions**: Open an issue

## Roadmap

See [MISSING_FEATURES.md](MISSING_FEATURES.md) for planned features.

---

**Version**: 1.0.0 (MVP)  
**Status**: Production Ready  
**Last Updated**: February 2026
