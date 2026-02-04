# Data Explorer - Quick Start Guide

Get up and running in 2 minutes! ⚡

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/phindagijimana/data_explorer.git
cd data-explorer

# One-command installation (works on all platforms!)
python explorer.py install
```

**That's it!** The CLI will:
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Initialize the database
- ✅ Set up logs directory

---

## 🎯 Launch Application

```bash
python explorer.py start
```

**✅ Works on macOS, Linux, and Windows!**

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
python explorer.py status
```
**Shows:**
- Running status (yes/no)
- PID and port
- CPU and memory usage
- Virtual environment status
- Database status

### View Logs
```bash
python explorer.py logs
```
**Shows:**
- Live application logs
- Press Ctrl+C to exit

### Stop Application
```bash
python explorer.py stop
```

### Restart Application
```bash
python explorer.py restart
```

---

## 🔧 Maintenance Commands

### Update to Latest Version
```bash
python explorer.py update
```
**Does:**
- Pull latest code from GitHub
- Update dependencies
- Preserves your data and configuration

### Run Tests
```bash
python explorer.py test
```
**Tests:**
- Database functionality
- All dependencies
- Module imports

### View Configuration
```bash
python explorer.py config
```
**Shows:**
- Current .env settings
- BIDS path
- Pennsieve credentials

### Clean Install
```bash
python explorer.py clean
python explorer.py install
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
python explorer.py install
python explorer.py start
# Configure in browser, then use normally
```

### Daily Use
```bash
cd data-explorer
python explorer.py start
# Work in browser
python explorer.py stop
```

### After Git Pull
```bash
git pull
python explorer.py update
python explorer.py restart
```

### Troubleshooting
```bash
python explorer.py status    # Check what's running
python explorer.py logs      # See error messages
python explorer.py restart   # Try restarting
python explorer.py test      # Verify installation
```

---

## 🆘 Getting Help

### Show All Commands
```bash
python explorer.py help
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
   - Stop current: `python explorer.py stop`
   - Update .env with new paths
   - Restart: `python explorer.py start`

3. **Check Before Starting**
   ```bash
   python explorer.py status  # See if already running
   ```

4. **Keep Logs Open While Working**
   ```bash
   python explorer.py logs    # In separate terminal
   ```

5. **Quick Restart After Code Changes**
   ```bash
   python explorer.py restart
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
python explorer.py stop
python explorer.py clean
cd ..
rm -rf data-explorer
```

---

## 🎉 You're Ready!

```bash
python explorer.py start
```

Open browser → Configure → Explore your data!

---

**Need more help?** Check the full documentation:
- [README.md](README.md) - Complete documentation
- [SETUP.md](docs/SETUP.md) - Detailed setup guide
- [GitHub Issues](https://github.com/phindagijimana/data_explorer/issues) - Report problems

---

**Happy exploring!** 🧠✨
