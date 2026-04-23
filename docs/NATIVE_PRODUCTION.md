# Native production deployment (`./hub`)

**Recommended path** for BIDSHub in production: run from a **git checkout** on a workstation or small server, using the **`./hub` CLI** (symlink to `bin/explorer`). For a **single-container** deployment with a similar CLI, use **`./hub-docker`** (`install` / `start` / `stop` / `logs` / `checks`) — see the main [README.md](../README.md) Docker section. This page is for **Python venv + Streamlit** on the host.

## What you get

| Piece | Location / behavior |
|--------|----------------------|
| Code | Cloned repository; use a **release tag** when you want a frozen baseline (`git checkout vX.Y.Z`). |
| Python env | `venv/` at the project root, created by `./hub install` |
| Dependencies | Pinned in `requirements.txt` |
| App process | `streamlit run app.py` started by `./hub start` (listens on **localhost** on an available port from **8501** through **8501+50**, or set `BIDSHUB_DEFAULT_PORT`) |
| State | SQLite under `data/`, usually `data/*.db` |
| Env / secrets | `.env` (from `.env.example`); not committed to git |
| Control | `./hub` commands (see [README.md](../README.md#cli-commands)) |

## First-time install (production)

1. **Python 3.10+** on the path (`python3 --version`).
2. Clone the repo and **check out a tag** (or a known good commit) if you want a reproducible build.
3. From the project root: **`./hub install`**  
   - Creates `venv/`, installs `requirements.txt`, copies **`.env.example` → `.env`** if `.env` does not already exist (your existing file is never overwritten), runs non-interactive DB init (`BIDSHUB_NONINTERACTIVE=1` via `scripts/init_db.py`).  
4. **Optional before first cloud use:** edit `.env` for API keys, `BIDS_ROOT`, download paths, or leave placeholders and set credentials / paths in the app UI.  
5. **`./hub start`** — open the printed `http://localhost:<port>`.
6. Confirm the app sidebar shows the expected **BIDSHub version** (`src/bidshub_version.py`).

## Day-2 operations

- **Status:** `./hub status` (PID, port, venv, DB file presence).
- **Stop / restart:** `./hub stop`, `./hub start`, or `./hub restart`.
- **Logs:** `./hub logs` (tails Streamlit logs under the default Streamlit log directory) or `logs/` in the repo if you add app-level logging.
- **Tests (optional):** `./hub test` (installs `requirements-dev.txt` in the venv, then `pytest`).

## Upgrades

- **In place:** with the app stopped, `git pull` (or `git fetch` + checkout tag), then re-run **`./hub install`** so `pip` refreshes the venv from the locked `requirements.txt`, then **`./hub start`**.  
- **`./hub update`** is a convenience that runs `git pull origin main` and `pip install -r requirements.txt`. Use it only if **your** production branch is `main` and the default remote/branch is correct; otherwise use explicit `git` + `./hub install`.

**Always back up** `data/*.db` before major upgrades or schema changes.

## Optional: start on boot (systemd, Linux)

Many labs use **`./hub start` manually** (or after SSH) for a long-lived session. The script **backgrounds** Streamlit, which is a poor fit for `systemd` as-is. For unattended service-style runs, a typical pattern is to run **Streamlit in the foreground** from the venv after `./hub install` (adjust paths, user, and port; ensure the port is free):

```ini
[Unit]
Description=BIDSHub (Streamlit)
After=network.target

[Service]
Type=simple
User=bidshub
WorkingDirectory=/opt/BIDSHUB
Environment=BIDSHUB_NONINTERACTIVE=1
# Load secrets from a file the service user can read, not from git
EnvironmentFile=-/opt/BIDSHUB/.env
ExecStart=/opt/BIDSHUB/venv/bin/streamlit run /opt/BIDSHUB/app.py --server.port 8501 --server.headless true
Restart=on-failure

[Install]
WantedBy=default.target
```

Hardening (bind address, reverse proxy) belongs in your ops layer—see [SECURITY.md](../SECURITY.md). Many sites prefer **SSH port forwarding** to localhost instead of a network-facing Streamlit port.

## Network and access

- **Default:** the **`./hub start`** path does **not** set `--server.address=0.0.0.0`, so Streamlit’s default binding is appropriate for a **local** browser on the same machine.  
- **Remote use:** use **SSH port forwarding** (e.g. `ssh -L 8501:127.0.0.1:8501 user@host`) to the port printed by `./hub status`, or place a **reverse proxy with authentication and TLS** in front of a deliberately exposed bind—see [SECURITY.md](../SECURITY.md).

## Related

- [PRODUCTION_GO_LIVE.md](PRODUCTION_GO_LIVE.md) — checklist  
- [RELEASE_POLICY.md](RELEASE_POLICY.md) — supported stack and release channel  
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) — install, venv, pip, logs  
