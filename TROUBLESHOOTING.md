# BIDSHub Troubleshooting

Short answers for common problems. Pair with **[USER_GUIDE.md](USER_GUIDE.md)**. **Last updated:** April 2026.

---

## Before you report

1. **Version** from the app sidebar; **OS**; `python3 --version` (native).
2. **Logs:** `./hub logs` or files under `logs/` — **redact** keys, tokens, paths.
3. **Repro:** what you clicked, dataset id, exact error text.
4. CI / non-interactive: `BIDSHUB_NONINTERACTIVE=1` is set by `./hub install` for `init_db`.

---

## Install, pip, venv, Docker

| Problem | What to do |
|---------|------------|
| **`resolution-too-deep`** | Install from committed **`requirements.txt`**. To regenerate: pin `numpy`, `protobuf`, `urllib3`, then `pip install --use-deprecated=legacy-resolver -r requirements.in` and `pip freeze` → see [USER_GUIDE — Security, development, and releases](USER_GUIDE.md#security-development-and-releases). |
| **Broken venv** (moved repo) | Delete `venv/`, run `./hub install` again. |
| **`ModuleNotFoundError`** | `pip install -r requirements.txt`; for tests: `pip install -r requirements-dev.txt`. |
| **Docker** | Prefer **`./hub-docker help`**. Needs host **`.env`** (use `./hub-docker install` or copy `.env.example`). **Port:** host **8501–8551** (`BIDSHUB_DEFAULT_PORT` / `BIDSHUB_HOST_PORT`). **Data:** `./data` → container; Linux: `chown -R 1000:1000 data` if DB errors. **Health:** `docker compose logs`; URL `http://127.0.0.1:8501/_stcore/health`. **Network:** do not publish to untrusted LANs without firewall / reverse proxy — [USER_GUIDE](USER_GUIDE.md#security-development-and-releases). |
| **XNAT + Docker** | XNAT is **beta**; prefer BIDS export and native path when things get odd. |

---

## Security and networking

- Default is **localhost**. Do not bind Streamlit to `0.0.0.0` on a public host without **proxy + TLS + auth**.
- **`.env`** for secrets; never commit. Rotate keys if leaked.
- **`data/*.db`** may hold study metadata — treat like sensitive files.

---

## Quick diagnostics

```bash
./hub status
./hub logs
./hub clean && ./hub install   # last resort for a bad local DB state (back up data/*.db first if you care)
```

---

## BIDS and validation

- **Missing / bad BIDS:** require `dataset_description.json`, `sub-*` dirs, valid names — run `bids-validator /path`.
- **DICOM:** convert with [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/) / heudiconv / BIDScoin; then re-add.
- **Spec:** [bids.neuroimaging.io](https://bids.neuroimaging.io/)

---

## Connection and data access

| Area | Checks |
|------|--------|
| **Pennsieve** | Keys in app.pennsieve.io; **dataset name** exact case; `ping`/reachability; test with `pennsieve2` in a venv if needed. |
| **OpenNeuro** | ID like **`ds000246`**, not uppercase or missing `ds`. |
| **DANDI** | 6-digit id; pick BIDS MRI sets when NWB is mixed. |
| **XNAT** | `https://` URL, project access, credentials; export BIDS for best results (**beta**). |
| **HPC / Remote** | SSH keys, VPN, correct **absolute** BIDS path, read permissions. |
| **No subjects after add (cloud)** | **Sync Subjects** on the Subjects page; wait; refresh. |
| **Local empty** | Fix BIDS layout/permissions; **Manage Datasets** → re-index. |
| **Filters empty table** | Clear filters; widen QC/session filters. |

---

## Downloads and disk

- **Timeouts / retries:** check network, disk space (`df -h`), platform status pages; retry smaller batches.
- **Space:** free space on download volume; change **local working directory** in dataset settings if needed.
- **Stuck queue:** pause, clear failed, retry after network stable.

---

## Viewer

- **No image:** file may be **stub** — download scan first for some platforms.
- **Path / permissions:** ensure NIfTI exists and is readable.
- **Large / slow:** prefer local copy on fast disk for huge files.

---

## Database

- **Corrupt / odd state:** back up `data/*.db`, then `./hub clean` + `./hub install` (destroys app DB — only if you accept reset).
- **Foreign key / integrity:** use in-app maintenance if available; re-sync affected datasets.

---

## QC and transfer

- **QC CSV (Pennsieve path):** match columns the app expects; import on the right **dataset id**.
- **Transfer fails:** verify both ends’ credentials and paths; check firewall for remote copy.

---

## UI and performance

- **Page slow:** narrow dataset filter, fewer concurrent datasets, smaller subject page size if offered.
- **Streamlit “rerun” loops:** one action per form submit; don’t double-click.
- **Cache weirdness:** hard refresh; restart `./hub` once.

---

## Platform-specific (short)

- **HCP / AWS:** keys and bucket policy; clock skew.
- **LORIS / FITBIR:** institution VPN and account restrictions.
- **DANDI API:** token in `.env` or app if private assets.

---

## Still stuck?

- Re-read [USER_GUIDE.md](USER_GUIDE.md) for your platform and **`.env` keys**.
- Open an issue with **version, OS, redacted log snippet**, and steps.
