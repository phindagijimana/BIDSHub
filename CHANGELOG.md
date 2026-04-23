# Changelog

All notable changes to BIDSHub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

- **`scripts/print_bidshub_version.py`**: single version string for Docker / CI; `./hub-docker` exports `BIDSHUB_VERSION` and default `BIDSHUB_IMAGE=bidshub:<ver>`; `docker-compose.yml` uses `${BIDSHUB_VERSION}` for build args and image tag; CI `docker-smoke` passes version from the script
- **Port selection:** default **8501** through **default+50** (native `./hub` / `bin/explorer`, `hub-docker` host publish, `bin/launch.*`); `BIDSHUB_DEFAULT_PORT` and Docker `BIDSHUB_HOST_PORT` in `.env` supported
- **Docker image:** OCI `LABEL`s + `BIDSHUB_VERSION` build-arg, non-root uid 1000, `HOME=/app`; `docker-compose.image.yml` for pre-pulled images; `hub-docker` supports `BIDSHUB_DOCKER_FILE`, `BIDSHUB_IMAGE`, and `pull` (bump compose fallbacks + Dockerfile `ARG` default on release per `RELEASING.md`)
- `./hub-docker` (symlink to `bin/hub-docker`): `install` / `pull` / `start` / `stop` / `restart` / `logs` / `checks` for the single `docker compose` service; `docker-compose.yml` uses `env_file: .env`
- `./hub install` / `explorer.bat install` creates `.env` from `.env.example` when missing (never overwrites)
- `docs/NATIVE_PRODUCTION.md` — native (venv + `./hub`) as the primary production path; `bin/explorer` messages use `./hub` for consistency
- Phase 0: `docs/RELEASE_POLICY.md`, `RELEASING.md`; README and TROUBLESHOOTING alignment on XNAT (beta) and release channel
- Phase 5: `Dockerfile`, `docker-compose.yml`, `.dockerignore`; GitHub Actions `docker-smoke` job; `docs/PRODUCTION_GO_LIVE.md`
- `SECURITY.md` and README updates for local vs Docker network exposure
- Maintenance: Phases 3–4 of production readiness (version source, ops/security notes)

## [3.1.1] - 2026-04-22

### Added
- Pinned `requirements.txt` (full lock), `requirements.in` for high-level deps, `requirements-dev.txt` for tests/CI
- `pytest.ini`, GitHub Actions CI, `CONTRIBUTING.md`
- `subject_sessions` and scan QC columns in default `init_db` schema where applicable
- `BIDSHUB_NONINTERACTIVE` for `scripts/init_db.py` to skip recreate prompt

### Fixed
- `Database.add_scan` resolves `subjects.id` for FK; scan lists and integrity checks aligned
- BIDS tests aligned with `validate_local_bids` API
- `get_scans_by_subject` / `run_integrity_maintenance(dry_run=...)` and related tests

### Notes
- Regenerate `requirements.txt` with `pip freeze` after `legacy-resolver` install if resolution-too-deep; see `CONTRIBUTING.md`

<!-- Add compare/release links when publishing tags on your host (e.g. GitHub). -->
