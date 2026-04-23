# BIDSHub User Guide

BIDS neuroimaging — browse, filter, and download from multiple sources. **Version 3.1.1** (April 2026)

This is one of three top-level guides; see also **[README.md](README.md)** and **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

---

## Contents

1. [What it is, BIDS, and install](#what-it-is-bids-and-install)
2. [First run and sample data](#first-run-and-sample-data)
3. [Platforms (short)](#platforms-short)
4. [Core workflows](#core-workflows)
5. [Tips](#tips)
6. [Security, development, and releases](#security-development-and-releases)
7. [Glossary](#glossary)

---

## What it is, BIDS, and install

BIDSHub is a **desktop** app: connect Pennsieve, OpenNeuro, DANDI, XNAT, local disk, HPC, remote servers, etc. Aggregate up to **20** BIDS datasets. **Not** a multi-tenant web service or a processing pipeline (use fMRIPrep, FreeSurfer, etc., for that).

### BIDS (required)

Only **[BIDS](https://bids.neuroimaging.io/)** datasets; validation runs on add.

| Platform | Note |
|----------|------|
| **OpenNeuro** | BIDS out of the box |
| **DANDI** | NWB + BIDS — use MRI / BIDS datasets |
| **Pennsieve** | Data must be organized as BIDS on the platform |
| **XNAT** | Often DICOM in archive — **beta**; export to BIDS when possible |
| **Local** | BIDS on disk |
| **HPC / Remote** | BIDS over SSH |

**Tools:** [bids-validator](https://bids-standard.github.io/bids-validator/); DICOM → [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/), [heudiconv](https://heudiconv.readthedocs.io/), [BIDScoin](https://bidscoin.readthedocs.io/).

**Minimum layout:** `dataset_description.json`, `sub-*` folders, BIDS file names; recommend `participants.tsv` and a study `README`.

### Requirements

- **Python 3.10+**; **OS:** macOS, Linux, Windows (`bin\explorer.bat` or WSL for `hub-docker` bash).
- **Version:** `src/bidshub_version.py` and app sidebar; match `pyproject.toml` when releasing.
- **Secrets:** [`.env.example`](.env.example); never commit real keys.

### Native and Docker (CLI)

| | **Native** | **Docker** (Compose v2) |
|---|------------|-------------------------|
| **Run** | `./hub install && ./hub start` | `./hub-docker install && ./hub-docker start` |
| **Help** | `./hub help` | `./hub-docker help` |
| **Other** | `status` · `logs` · `stop` · `restart` · `clean` | `checks` · `logs` · `stop` · `restart`; **`pull`** with `docker-compose.image.yml` + `BIDSHUB_IMAGE` |

- First run can create **`.env`** from **`.env.example`**. **URL:** `http://localhost:8501` or next free port in **8501–8551** (`BIDSHUB_DEFAULT_PORT` / `BIDSHUB_HOST_PORT` in `.env` for Docker publish).
- **Docker:** one container; Streamlit; SQLite in `/app/data`; user **uid 1000**; host **`./data`** mounted. On Linux, `chown -R 1000:1000 data` if DB permission errors. Do not expose a port to the public internet without **TLS** and a **reverse proxy**.

**Pre-built image:**

```bash
export BIDSHUB_DOCKER_FILE=docker-compose.image.yml
export BIDSHUB_IMAGE=ghcr.io/YOUR_ORG/bidshub:3.1.1
./hub-docker pull && ./hub-docker start
```

**`.env` example keys:** `BIDS_ROOT`, `PENNSIEVE_API_KEY` / `SECRET` / `PENNSIEVE_DATASET_NAME` — or set in the app.

---

## First run and sample data

1. **Native:** `./hub install` then `./hub start` (or `python -m streamlit run app.py`). Browser opens the app.
2. Use **Setup** or **Manage Datasets** to add a cloud or local BIDS dataset; run **Sync** for cloud sources to load subjects.
3. **Optional samples** (no API keys): run `python scripts/add_sample_datasets.py add`, then open **Manage Datasets** and **Sync** a sample. Includes OpenNeuro **ds005115**, **ds000114**; DANDI **000026**, **000058** (DANDI allows more file-level / streaming access; OpenNeuro often needs downloads for full NIfTI paths).

**Further help:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Platforms (short)

| Platform | You need | Typical use |
|----------|----------|---------------|
| **Pennsieve** | API key + secret + dataset name | Private institutional data (must be BIDS on Pennsieve) |
| **OpenNeuro** | Dataset ID e.g. `ds00…` (token optional) | Public BIDS |
| **DANDI** | 6-digit dandiset id | BIDS MRI (filter mixed NWB) |
| **XNAT** | Project + URL + creds; often export to BIDS | institutional archive (**beta** in BIDSHub) |
| **HCP** | AWS-style creds (per HCP) | HCP S3 data |
| **LORIS / FITBIR** | Server + user creds (FITBIR restricted) | Longitudinal / federal TBI |
| **Local** | Path to BIDS root on disk | Already local data |
| **HPC / Remote** | SSH + path | Data on cluster / server |

Use the in-app **Setup** forms for the exact fields; credentials can also go in **`.env`**.

---

## Core workflows

### Browse and filter subjects

**Subjects** (and related pages): pick dataset(s), **Sync** if needed, filter by age/sex/diagnosis/modality, search, paginate. Cross-dataset when multiple datasets are active.

### MRI viewer

Built-in NIfTI viewing when files are on disk (or stub metadata for some cloud paths). Modes follow what the app exposes for the selected scan (e.g. file path vs needs download first).

### Downloads

**Download manager:** queue subjects/scans, batch work, **Pause** / **Resume** where available. For cloud-only, you may get stub files until a full file is downloaded; check platform limits and disk space.

### Quality control (QC)

**QC** page: (1) **Manual** — subject/scan status (`pending` / `pass` / `fail` / `needs_review`), notes, reviewer, flags. (2) **Automated** — file-exists, stub vs real file, size/sidecar checks, recommended-modality warnings. (3) **Pennsieve / CSV** — import/export **scan-level** QC CSV for your lab workflow. Dashboard shows QC counts; filter Subjects by QC.

### Multiple datasets

**Manage Datasets:** add up to **20**; activate/deactivate, sync per dataset, per-dataset credentials.

### Data transfer

Move data between **Local** and supported platforms (Pennsieve, HPC, XNAT, remote) where the app offers transfer; follow on-screen steps and [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if a transfer errors.

---

## Tips

- Start with **one** dataset; add more after flows feel familiar.
- **Sync** after adding a cloud dataset before expecting subjects in lists.
- **BIDS validate** on disk before adding local datasets: `bids-validator /path`
- For **DANDI** vs **OpenNeuro** access patterns, see sample notes above; pick workflow that matches download vs stream.
- **Back up** `data/*.db` before big upgrades; check **sidebar version** after updates.
- **HPC/SSH:** key-based auth; use paths the remote user can read.
- If something fails: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first, then file an issue with version, OS, and redacted logs.

---

## Security, development, and releases

### Vulnerability reporting

Report **this repo’s** issues privately to maintainers (e.g. private security advisory or repository owner), not in public issues with exploit details, until fixed.

### Credentials, data, and network

Do not commit **`.env`** or real DB copies with sensitive metadata. Rotate keys in provider consoles if exposed. Prefer **localhost**; for **Docker** on shared networks, use firewall, VPN, or **reverse proxy + TLS + auth**. Third parties’ terms apply to cloud APIs.

### For developers: setup and tests

```bash
./hub install
pip install -r requirements-dev.txt
# Tests:  python -m pytest tests/ -q   (see pytest.ini; dandi pytest plugin off in CI)
```

`BIDSHUB_NONINTERACTIVE=1` is set on `./hub install` for `init_db`. **Regenerate `requirements.txt`:** pin `numpy` / `protobuf` / `urllib3`, then `pip install --use-deprecated=legacy-resolver -r requirements.in` and `pip freeze`; restore the header in `requirements.txt`. CI: `.github/workflows/ci.yml` (3.10 / 3.12, Ubuntu + macOS).

### Versioning and release channel

1. Set **`__version__`** in **`src/bidshub_version.py`** and **`version`** in **`pyproject.toml`**.
2. Align **`Dockerfile` `ARG BIDSHUB_VERSION`** and compose `${…:-x.y.z}` for releases.
3. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
4. **Default channel** is **git + tags** and optional **Docker** images, not **PyPI** (would need a proper `pyproject` build).

**XNAT** remains **beta** in the app.

### Docker image (maintainers)

```bash
V="$(python3 scripts/print_bidshub_version.py)"
docker build -t "bidshub:${V}" --build-arg "BIDSHUB_VERSION=${V}" .
# or: ./hub-docker install
```

Document registry URL for users. Pre-pulled: `BIDSHUB_DOCKER_FILE=docker-compose.image.yml` + `BIDSHUB_IMAGE=…`, `./hub-docker pull && start`.

### Native production (summary)

| | |
|---|---|
| Code | `git` checkout; tag for frozen baseline |
| Env | `venv` + `requirements.txt` from `./hub install` |
| App | `streamlit run app.py` via `./hub start`; port **8501+** on localhost |
| Data | `data/*.db` (SQLite) |
| Upgrade | Stop app; **backup DB**; `git pull` (or tag); `./hub install`; `./hub start` |

**Remote use:** **SSH -L** port forward to the printed port, or a hardened reverse proxy (not raw Streamlit on the internet).

### Go-live (single user / lab)

- Pinned deps; CI green; version consistent; no secrets in git. Smoke-test one real path. Backup DB before major upgrades.

### Recent changes

- **3.1.1:** Pinned requirements, CI, DB/QC and test hardening, `BIDSHUB_NONINTERACTIVE` for `init_db`.
- **Ongoing / unreleased (summary):** `hub-docker` polish, port selection, docker-smoke in CI.

---

## Glossary

| Term | Meaning |
|------|--------|
| **BIDS** | Standard layout for neuroimaging datasets |
| **Subject** | Participant (`sub-…`) |
| **Session** | Timepoint (e.g. `ses-01` or `2WK`) |
| **Modality / suffix** | e.g. `anat` + `T1w` |
| **Stub** | Cloud placeholder; not full NIfTI yet |
| **QC** | Manual / automated review status for subjects or scans |
| **Dataset root** | Folder with `dataset_description.json` |

---

**Need fixes?** See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.
