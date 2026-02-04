# Data Explorer - Quick Start

Get running in 2 minutes.

## Installation

```bash
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer
./explorer install        # macOS/Linux: ./explorer install | Windows: explorer install
```

This creates the virtual environment, installs dependencies, and initializes the database.

## Launch

```bash
./explorer start
```

Browser opens automatically at `http://localhost:8501` (or next available port 8500-8550).

## First-Time Setup

In the browser:

1. **BIDS Directory**: Enter path to your BIDS dataset
2. **Pennsieve Credentials**:
   - Dataset name
   - API Key
   - API Secret
3. **Click "Initialize Dataset"**
4. Wait ~2-5 minutes for indexing
5. Dashboard opens automatically

Done!

## Common Commands

```bash
./explorer status    # Check if running
./explorer logs      # View live logs
./explorer stop      # Stop application
./explorer restart   # Restart application
./explorer update    # Update from GitHub
./explorer test      # Run tests
./explorer config    # Show configuration
./explorer help      # Show all commands
```

## Troubleshooting

**Can't connect to Pennsieve?**
- Verify credentials are correct
- Check internet connection
- Ensure dataset name is exact (case-sensitive)

**Port conflict?**
- CLI automatically finds next available port (8500-8550)

**Database issues?**
```bash
./explorer clean
./explorer install
```

**Still stuck?**
```bash
./explorer logs      # Check error messages
./explorer status    # Verify running state
```

## Using the Application

**Pages:**
1. **Setup** - Initial configuration (one-time)
2. **Dashboard** - Statistics and overview
3. **Subject Browser** - Search and filter subjects
4. **Subject Detail** - View scans, update QC status
5. **Download Manager** - Queue and download files
6. **QC Dashboard** - Quality control workflow

**Common Tasks:**
- **Search subjects**: Subject Browser → Search box
- **Filter by QC**: Subject Browser → Status dropdown
- **Update QC**: Click subject → Change status → Update
- **Download files**: Subject Detail → Add to Queue → Download Manager → Start
- **Export data**: Any table → Export CSV button

## Configuration

Optional: Create `.env` file for default settings:

```env
BIDS_ROOT=/path/to/bids/dataset
PENNSIEVE_API_KEY=your_key
PENNSIEVE_API_SECRET=your_secret
PENNSIEVE_DATASET_NAME=your_dataset
```

Or configure via UI on first launch.

## Requirements

- Python 3.8+
- Pennsieve account with API credentials
- BIDS-formatted dataset

## Support

- **Documentation**: [README.md](README.md)
- **Issues**: [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues)

---

**That's it!** Start exploring your data:

```bash
./explorer start
```
