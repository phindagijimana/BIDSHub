# BIDSHub

**Multi-platform neuroimaging dataset management and exploration** — browse, filter, and download BIDS datasets from several platforms in one place.

**Datasets must be [BIDS](https://bids.neuroimaging.io/).** BIDSHub validates on add.

## Documentation (three files)

| | |
|---|---|
| **[USER_GUIDE.md](USER_GUIDE.md)** | Concise: BIDS, install, platforms, workflows, security / maintainers |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Concise: install, Docker, BIDS, connections, fixes |
| **README.md** (this file) | Short intro and CLI only |

## Quick start

**Desktop app (no Python needed):** download the installer for your OS from the
[latest release](https://github.com/phindagijimana/BIDSHub/releases/latest) —
`BIDSHub.dmg` (macOS) or `BIDSHub-Setup.exe` (Windows) — and open it. Your data
lives in a per-user folder (`~/Library/Application Support/BIDSHub` on macOS,
`%APPDATA%\BIDSHub` on Windows).

> Until the app is code-signed, the OS shows an "unidentified developer" warning
> on first launch. macOS: right-click the app → **Open** → **Open**. Windows:
> **More info** → **Run anyway**.

**Native (recommended for developers):** Python on the host; one database under `./data` (not containerized in this path).

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

## License

MIT — see [LICENSE](LICENSE).

## Support

**Issues:** [GitHub Issues](https://github.com/phindagijimana/BIDSHub/issues)

**Version 3.1.1**
