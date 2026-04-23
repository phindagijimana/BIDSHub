# Release policy (Phase 0)

This document fixes what “production ready” means for **distribution** of BIDSHub.

## Supported stack

- **Python:** 3.10+ (see CI in `.github/workflows/ci.yml`).
- **Primary production path:** **native** — clone the repository, run **`./hub install`** and **`./hub start`** using the **pinned** `requirements.txt` (see [NATIVE_PRODUCTION.md](NATIVE_PRODUCTION.md)).
- **Optional:** run from the **Dockerfile** / `docker-compose.yml` (container/lab use).

## Release channel (default)

1. **Git tags** — e.g. `v3.1.1` matching `src/bidshub_version.py` and `pyproject.toml`.
2. **Changelog** — update `CHANGELOG.md` for each tagged release.
3. **GitHub Releases** (or your host) — optional but recommended: attach release notes from the changelog.

**PyPI / `pip install bidshub`** is **not** the default channel today. The project is run from a checkout or a container; see `RELEASING.md` if you later publish a wheel.

## Beta integrations

- **XNAT** is documented as **beta** in the main README (Supported Platforms). Expect rough edges; export BIDS to a local tree when in doubt.
- Other platforms are “production” only in the sense of being supported for the intended workflows—always validate on your data.

## Exit criteria (Phase 0)

- [x] Supported environment documented in README.
- [x] Release channel and beta status documented (this file + README + TROUBLESHOOTING for XNAT where relevant).
- [x] No contradictory install story (native + optional Docker; no “Docker recommended” without an in-repo image).
