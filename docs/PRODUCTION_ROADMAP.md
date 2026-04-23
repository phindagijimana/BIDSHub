# BIDSHub production readiness (phased plan)

This document turns known gaps into **ordered phases** with clear exit criteria. Scope stays aligned with the product: **single-user, local** hub—not multi-tenant hosting or in-app heavy compute (e.g. MRIQC execution).

**References:** In-repo test notes (`TEST_RESULTS.md`), `pytest` failures from FK/fixture drift, and install failures from **pip `resolution-too-deep`** and **transitive version conflicts** (e.g. `pennsieve` vs `numpy` / `protobuf` / `urllib3`).

---

## Phase 0 — Baseline and definitions

**Status (done in repo):** README **Supported environment**; [docs/RELEASE_POLICY.md](RELEASE_POLICY.md) (stack, release channel, PyPI as non-default); XNAT **beta** in the platform table; TROUBLESHOOTING **Docker** subsection cross-links XNAT beta; [RELEASING.md](../RELEASING.md) for tags and optional PyPI.

**Goal:** Agree what “production” means for this repo and record it in one place.

| Task | Outcome |
|------|---------|
| Define supported **Python** minor versions (e.g. 3.10–3.12) | Documented in README and CI |
| Define **release channel** (git tags only vs PyPI vs installers later) | Documented here + README “Installation” |
| Mark **XNAT** and any other beta integrations explicitly | README table + TROUBLESHOOTING if needed |

**Exit:** README has a short “Supported environment” section; no contradictory claims. **Done.**

---

## Phase 1 — Reproducible installs and dependency health

**Status (done in repo):** Full **pip freeze** lock in `requirements.txt`; high-level deps in `requirements.in`; `requirements-dev.txt` for pytest / `pip-tools`; `./hub install` uses non-interactive DB init via `BIDSHUB_NONINTERACTIVE` and `scripts/init_db.py`.

**Goal:** `./hub install` (or documented equivalent) **succeeds reliably** and dependency conflicts are **visible and controlled**, not accidentally ignored.

| Task | Outcome |
|------|---------|
| Fix pip **`resolution-too-deep`** | Either: tighter bounds in `requirements.txt`, a **lock file** (e.g. `uv pip compile` / `pip-tools`), or a **documented** resolver strategy in `./hub` (see legacy resolver caveat below) |
| Reconcile **Pennsieve** and stack pins | Resolve warnings such as `pennsieve` vs `numpy` / `protobuf` / `botocore`+`urllib3` (test Pennsieve Agent flows after changes) |
| Optional split | `requirements.txt` (app) vs `requirements-dev.txt` (pytest, cov) to shrink production install surface |
| Test install | Clean venv: install from docs path; **no** 30+ minute dead ends |

**Exit:** Fresh venv install completes in reasonable time; known pins documented; no silent “legacy resolver” dependency conflicts in production without a recorded decision.

**Note:** Regenerating `requirements.txt` may still use `pip install --use-deprecated=legacy-resolver -r requirements.in` then `pip freeze` (see `CONTRIBUTING.md`). Some transitive warnings (e.g. grpcio vs protobuf) may appear; adjust pins if a runtime breaks.

---

## Phase 2 — Test suite and CI

**Status (done in repo):** `.github/workflows/ci.yml` (Ubuntu + macOS, Python 3.10 + 3.12); `pytest.ini` with `-p no:dandi`; tests aligned with `Database` scan FK model, `get_scans_by_subject`, `run_integrity_maintenance(dry_run=...)`; `test_bids_validator` updated for `validate_local_bids`; three tests **skipped** where schema makes the scenario impossible (duplicate subject rows).

**Goal:** **Automated** feedback on every change; test failures match **product** bugs, not only fixture drift.

| Task | Outcome |
|------|---------|
| **CI** (e.g. GitHub Actions) on push/PR | matrix: supported Python versions |
| Stabilize **`pytest`** | Use `-p no:dandi` (or fix dandi/pytest plugin environment) in CI; document in `TEST_RESULTS.md` or `CONTRIBUTING` |
| Fix or **quarantine** failing tests | Address FK/fixture issues (`test_database_integrity`, integration tests), or mark skipped with a **ticket and reason**—no endless red without explanation |
| Align tests with public API | e.g. `get_scans_by_subject`, `run_integrity_maintenance` signature—tests or implementation, one source of truth |
| Set a **minimum bar** | e.g. “core” subset must pass for merge (even if full suite is allow-listed later) |

**Exit:** Green CI for the agreed “required” test set; failing tests are either fixed or explicitly tracked as known gaps.

---

## Phase 3 — Release engineering and version truth

**Status (done in repo):** `src/bidshub_version.py` + matching `version` in `pyproject.toml`; `CHANGELOG.md`; README with **Supported environment** and optional Docker; sidebar uses `__version__`; [CONTRIBUTING.md](CONTRIBUTING.md) documents release version bump. **Git tags** are manual when you publish.

**Goal:** One version string, clear releases, and **documentation that matches the repo**.

| Task | Outcome |
|------|---------|
| **Single version source** | e.g. `src/bidshub_version.py` or `importlib.metadata` from `pyproject`/`setup`—UI strings read from that |
| **Changelog** | `CHANGELOG.md` or release notes in tags |
| **Git tags** | e.g. `v3.1.2` aligned with the version source |
| **README accuracy** | Clone URL, product name, and **Docker instructions** in README + `Dockerfile` / `docker-compose.yml` |
| Optional | `pyproject.toml` with project metadata for packaging later |

**Exit:** User can answer “which version is installed?” in one place; README install steps are executable without dead links to missing Docker assets.

---

## Phase 4 — Operations, security, and support (local app)

**Status (done in repo):** README **Security (local use)**; extended **TROUBLESHOOTING.md** (before you report, install/pip/venv, security/networking, logs/redaction); **.env.example** comments on not committing secrets and optional `BIDSHUB_NONINTERACTIVE`.

**Goal:** Safer default assumptions for a **local** Streamlit app and clearer **support** path.

| Task | Outcome |
|------|---------|
| **Secrets** | `.env.example` without real keys; short doc: do not commit secrets; rotate Pennsieve keys if leaked |
| **Network exposure** | Document: bind to localhost; do not expose Streamlit to the public internet without reverse proxy + auth |
| **Logs** | `./hub` / app logs: location (`logs/`), what to redact, what to attach when reporting issues |
| **Troubleshooting** | Link or extend `TROUBLESHOOTING.md` for install failures (pip resolver, venv, Pennsieve Agent) |

**Exit:** A “**before you report an issue**” section exists; security guidance fits single-user local use.

---

## Phase 5 — Distribution (optional, product-dependent)

**Status (done in repo for OCI in-tree):** `Dockerfile`, `docker-compose.yml`, `.dockerignore`; **CI** `docker-smoke` in `.github/workflows/ci.yml` (build, run, probe `/_stcore/health`); README and [docs/PRODUCTION_GO_LIVE.md](PRODUCTION_GO_LIVE.md). **Not** in scope: automatic push to a public registry, PyPI package, or desktop bundle—see [RELEASING.md](../RELEASING.md).

**Goal:** **Optional** channels beyond `git clone` + `./hub install`—only if the team commits to maintaining them.

| Option | When it’s worth it |
|--------|---------------------|
| **Published Docker image** | After Phase 1–3; README matches reality (in-tree build + optional registry push) |
| **PyPI / `pip install bidshub`** | After `pyproject.toml`, version, and test bar; documented as future in [RELEASE_POLICY.md](RELEASE_POLICY.md) |
| **Desktop bundle** (PyInstaller, etc.) | High effort; often a separate milestone |

**Exit:** Each **chosen** channel has build instructions and a **smoke test** in CI or release checklist. **In-repo Docker + CI smoke: done.**

---

## Suggested order of work

1. **Phase 0** (quick)  
2. **Phase 1** (unblocks real installs)  
3. **Phase 2** (confidence for changes)  
4. **Phase 3** (release clarity)  
5. **Phase 4** (hardening + support)  
6. **Phase 5** (only as needed)

---

## Related in-repo files

- `TEST_RESULTS.md` — historical test summary; update when CI and tests stabilize
- `requirements.txt` / `requirements.in` — lock and pins (Phase 1)
- `hub` — `cmd_install` matches Phase 1 decisions
- `TROUBLESHOOTING.md` — install, security, optional Docker, platform issues (Phase 4+)
- `README.md` — install (native + Docker), supported environment, security
- `SECURITY.md` — reporting, network exposure, credentials
- `RELEASING.md`, `docs/RELEASE_POLICY.md`, `docs/PRODUCTION_GO_LIVE.md`, `docs/NATIVE_PRODUCTION.md` — go-live, releases, native `./hub` production
- `Dockerfile`, `docker-compose.yml`, `docker-compose.image.yml`, `.dockerignore`, `bin/hub-docker` — Phase 5
