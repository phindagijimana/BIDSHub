# BIDSHub

**Multi-platform neuroimaging dataset management and exploration** — browse, filter, and download BIDS datasets from several platforms in one place.

**Datasets must be [BIDS](https://bids.neuroimaging.io/).** BIDSHub validates on add.

## What it does

- **Connect once, browse everywhere** — OpenNeuro, DANDI, Pennsieve, XNAT, HPC clusters, and generic SSH servers in one interface.
- **Filter by metadata** — search subjects by age, sex, diagnosis, modality, and session across multiple datasets.
- **Quality control** — manual + automated QC at subject and scan level, with history and export.
- **Built-in NIfTI viewer** — multiplanar + 3D view ([NiiVue](https://github.com/niivue/niivue)); no external tools.
- **Selective download & transfer** — queue subjects/scans, download or move data between platforms.
- **Cohort export** — assemble a new BIDS dataset from selected subjects (symlink / copy / hardlink).
- **Local-first** — your data and database stay on your machine; nothing is uploaded.

## Requirements

- **Desktop app:** macOS 12+ on **Apple Silicon**, or **Windows 10/11 (64-bit)**. ~600 MB free disk. No Python needed.
  *Intel Macs and Linux aren't packaged yet — use the native install below.*
- **Native:** Python **3.10+** on macOS / Linux / Windows.
- **Docker:** Docker with Compose v2 (bash / WSL).

## Documentation (three files)

| | |
|---|---|
| **[USER_GUIDE.md](USER_GUIDE.md)** | Concise: BIDS, install, platforms, workflows, security / maintainers |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Concise: install, Docker, BIDS, connections, fixes |
| **README.md** (this file) | Short intro and CLI only |

## Quick start

### Desktop app (no Python needed)

Download the installer for your OS from the **[latest release](https://github.com/phindagijimana/BIDSHub/releases/latest)**:

| OS | File |
|----|------|
| macOS (Apple Silicon) | `BIDSHub.dmg` |
| Windows 10/11 (x64) | `BIDSHub-Setup.exe` |

**1 · Verify the download with the checksum (recommended).** Every release ships a
`SHA256SUMS` file. Compute your file's hash and confirm it matches — this proves
the download wasn't corrupted or tampered with, which matters because the apps
aren't code-signed yet:

```bash
# macOS / Linux
shasum -a 256 BIDSHub.dmg          # compare the hash to the line in SHA256SUMS
```
```powershell
# Windows (PowerShell)
Get-FileHash .\BIDSHub-Setup.exe -Algorithm SHA256    # compare to SHA256SUMS
```

**2 · Install & launch.**
- **macOS:** open `BIDSHub.dmg`, drag **BIDSHub** into **Applications**, then launch it.
- **Windows:** run `BIDSHub-Setup.exe`, follow the installer, then launch **BIDSHub** from the Start menu / desktop.

The app starts a local server and opens in its own window; nothing is uploaded.

**3 · First launch — allow the unsigned app to run.** Because the apps aren't
code-signed yet, the OS blocks them the first time. After verifying the checksum
(step 1), allow it — this is needed only once:
- **macOS (Gatekeeper):** right-click (Control-click) **BIDSHub** in Applications → **Open** → **Open** again. If macOS says the app "is damaged," clear the quarantine flag once: `xattr -dr com.apple.quarantine /Applications/BIDSHub.app`
- **Windows (SmartScreen):** when "**Windows protected your PC**" appears on the installer or app, click **More info** → **Run anyway**.

**Windows — Microsoft Edge WebView2 runtime.** The app window uses Edge WebView2,
preinstalled on Windows 11 and current Windows 10. The installer installs it
automatically if missing; if the app installs but **no window appears**, install
the free [Evergreen WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)
from Microsoft and relaunch.

**Your data** lives in a per-user folder — macOS: `~/Library/Application Support/BIDSHub`,
Windows: `%APPDATA%\BIDSHub` (database, downloads, cohorts, and `logs/desktop.log`).

**Using it:** click **Getting Started**, then **Manage Datasets → Add New Dataset**
to connect a platform (OpenNeuro / DANDI are public; Pennsieve / XNAT / HPC need
your credentials). Expand the dataset and click **Sync** to pull its subjects,
then use **Browse Subjects**, **QC Dashboard**, **Viewer**, and **Export**. Or
click **Try with sample data** for a real demo brain.

### Native (recommended for developers)

Python on the host; one database under `./data` (not containerized in this path).

```bash
git clone https://github.com/phindagijimana/BIDSHub.git
cd BIDSHub
./hub install    # venv, locked deps, .env from .env.example, init DB
./hub start      # launch Streamlit (default http://localhost:8501 or next free 8501–8551)
./hub stop       # stop the app
./hub help       # all commands
```

**Docker (optional, Compose v2; bash / WSL):** builds/runs a single app container; host `./data` is mounted, volumes kept on `./hub-docker stop` by default.

```bash
git clone https://github.com/phindagijimana/BIDSHub.git
cd BIDSHub
./hub-docker install   # .env, build or pull image
./hub-docker start
./hub-docker stop      # stop container; data volume on host is kept
./hub-docker help
```

**Pre-built image:** set `BIDSHUB_DOCKER_FILE=docker-compose.image.yml` and `BIDSHUB_IMAGE=…` — [USER_GUIDE.md](USER_GUIDE.md#native-and-docker-cli).

**Windows (native):** `bin\explorer.bat`.

**Secrets:** keep API keys in **`.env`** only (never commit).

## Supported platforms

Add datasets in **Manage Datasets → Add New Dataset**.

| Platform | Data | Credentials needed |
|----------|------|--------------------|
| **OpenNeuro** | Public BIDS MRI | None |
| **DANDI** | Public (NWB / electrophysiology) | None (token for embargoed) |
| **Pennsieve** | Private datasets (supports upload) | API key + secret |
| **XNAT** | Institutional imaging archives | Server URL + username/password |
| **HPC cluster** | BIDS on a cluster | SSH host + user (password or key) |
| **Remote server** | BIDS over SSH/SFTP | SSH host + user (password or key) |
| **Local** | A BIDS folder on disk | None |

## Updating

- **Desktop:** download the newest installer from the [latest release](https://github.com/phindagijimana/BIDSHub/releases/latest) and reinstall — your per-user data folder is preserved.
- **Native:** `git pull && ./hub update`

## License

MIT — see [LICENSE](LICENSE).

## Support

**Issues:** [GitHub Issues](https://github.com/phindagijimana/BIDSHub/issues)

**Current version:** see [Releases](https://github.com/phindagijimana/BIDSHub/releases).
