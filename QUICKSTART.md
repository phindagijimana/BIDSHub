# Data Explorer - Quick Start Guide

Get up and running in 2 minutes! ⚡

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer

# One-command installation
./explorer install
```

**That's it!** The CLI will:
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Initialize the database
- ✅ Set up logs directory

---

## 🎯 Launch Application

```bash
./explorer start
```

**What happens:**
- Automatically finds available port (default: 8501, range: 8500-8550)
- Opens browser at `http://localhost:8501` (or next available)
- Shows you the port and URL

---

## ⚙️ First-Time Setup (In Browser)

1. **BIDS Directory**
   ```
   Enter path: /Users/pndagiji/Documents/TrackTBI/TrackTBI
   ```

2. **Pennsieve Credentials**
   - Dataset: `TrackTBI`
   - API Key: `your_key_here`
   - API Secret: `your_secret_here`

3. **Click "Initialize Dataset"**
   - Wait for 5 steps to complete (~2-5 minutes)
   - Automatically redirects to dashboard when done

---

## 📋 Essential Commands

### Check Status
```bash
./explorer status
```
**Shows:**
- Running status (yes/no)
- PID and port
- CPU and memory usage
- Virtual environment status
- Database status

### View Logs
```bash
./explorer logs
```
**Shows:**
- Live application logs
- Press Ctrl+C to exit

### Stop Application
```bash
./explorer stop
```

### Restart Application
```bash
./explorer restart
```

---

## 🔧 Maintenance Commands

### Update to Latest Version
```bash
./explorer update
```
**Does:**
- Pull latest code from GitHub
- Update dependencies
- Preserves your data and configuration

### Run Tests
```bash
./explorer test
```
**Tests:**
- Database functionality
- All dependencies
- Module imports

### View Configuration
```bash
./explorer config
```
**Shows:**
- Current .env settings
- BIDS path
- Pennsieve credentials

### Clean Install
```bash
./explorer clean
./explorer install
```
**Removes:**
- Virtual environment
- Cache files
- (Optionally) Database

---

## 💡 Common Workflows

### First Time Setup
```bash
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer
./explorer install
./explorer start
# Configure in browser, then use normally
```

### Daily Use
```bash
cd data-explorer
./explorer start
# Work in browser
./explorer stop
```

### After Git Pull
```bash
git pull
./explorer update
./explorer restart
```

### Troubleshooting
```bash
./explorer status    # Check what's running
./explorer logs      # See error messages
./explorer restart   # Try restarting
./explorer test      # Verify installation
```

---

## 🆘 Getting Help

### Show All Commands
```bash
./explorer help
```

### Command-Specific Help
Most commands show helpful error messages if something goes wrong.

---

## 🎨 Using the Application

Once running, navigate through the sidebar:

1. **Setup** - Initial configuration (one-time)
2. **Dashboard** - Overview and statistics
3. **Subject Browser** - Search and filter subjects
4. **Subject Detail** - View individual subject data
5. **Download Manager** - Queue and download files
6. **QC Dashboard** - Quality control workflow

---

## 🔑 Key Features

| Feature | How To |
|---------|--------|
| **Search subjects** | Go to Subject Browser → Enter ID |
| **Filter by QC status** | Subject Browser → Select status dropdown |
| **Update QC status** | Click subject → Change status → Update |
| **Download files** | Subject Detail → Add to Queue → Download Manager → Start |
| **Export data** | Any page with table → Export to CSV button |
| **View QC stats** | QC Dashboard → Overview section |

---

## ⚡ Pro Tips

1. **Port Conflict?** 
   - CLI automatically finds next available port (8500-8550)
   
2. **Multiple Datasets?**
   - Stop current: `./explorer stop`
   - Update .env with new paths
   - Restart: `./explorer start`

3. **Check Before Starting**
   ```bash
   ./explorer status  # See if already running
   ```

4. **Keep Logs Open While Working**
   ```bash
   ./explorer logs    # In separate terminal
   ```

5. **Quick Restart After Code Changes**
   ```bash
   ./explorer restart
   ```

---

## 📦 What Gets Installed?

```
data-explorer/
├── venv/              ← Virtual environment
├── data/
│   └── tracktbi.db    ← SQLite database
├── logs/              ← Application logs
├── .explorer.pid      ← Process ID (when running)
├── .explorer.port     ← Port number (when running)
└── .env               ← Your configuration
```

---

## 🚫 Uninstall

```bash
./explorer stop
./explorer clean
cd ..
rm -rf data-explorer
```

---

## 🎉 You're Ready!

```bash
./explorer start
```

Open browser → Configure → Explore your data!

---

**Need more help?** Check the full documentation:
- [README.md](README.md) - Complete documentation
- [SETUP.md](docs/SETUP.md) - Detailed setup guide
- [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues) - Report problems

---

**Happy exploring!** 🧠✨
