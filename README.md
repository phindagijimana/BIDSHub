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
./explorer install

# Launch
./explorer start
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

- [QUICKSTART.md](QUICKSTART.md) - 2-minute setup guide

## Requirements

- Python 3.8+
- Pennsieve account with API credentials
- BIDS-formatted dataset

## License

MIT License - see [LICENSE](LICENSE) file

## Support

- **Issues**: [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues)
- **Documentation**: [QUICKSTART.md](QUICKSTART.md)
- **Questions**: Open an issue

## Roadmap

Future enhancements planned:
- Advanced filtering and sorting
- Data visualization (brain images)
- MRIQC and fMRIPrep integration
- Multi-user support
- Docker deployment

---

**Version**: 1.0.0 (MVP)  
**Status**: Production Ready  
**Last Updated**: February 2026
