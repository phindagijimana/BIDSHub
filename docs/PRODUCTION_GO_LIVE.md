# Production go-live checklist

Use this before calling a deployment “production ready” for your **lab or single-user** setup. BIDSHub is not a hosted SaaS; this checklist is about **repeatable installs, safety, and supportability**.

**Primary path:** [native install + `./hub` CLI](NATIVE_PRODUCTION.md) (venv, pinned `requirements.txt`, `./hub install` / `./hub start`). Docker is an optional alternative.

## Preconditions (all phases)

| Item | Reference |
|------|-----------|
| Pinned Python deps | `requirements.txt`, `requirements.in` |
| Tests + CI green | `.github/workflows/ci.yml` |
| Version in one place | `src/bidshub_version.py`, `pyproject.toml`, `CHANGELOG.md` |
| Secrets not in git | `.gitignore` for `.env`; use `.env.example` as template |
| Security expectations | `SECURITY.md`, README “Security (local use)” |
| Docker optional | `Dockerfile`, `docker-compose.yml`, CI `docker-smoke` job |

## Before you deploy (your side)

1. **Backup** any existing `data/*.db` before upgrades.
2. **Rotate** API keys if they were ever in a shared branch or log.
3. **Network:** prefer localhost; if using Docker on a server, firewall the host and use VPN or reverse proxy + auth.
4. **Verify** a clean install: **`./hub install`** for native (preferred for production) or `docker compose build` if you use containers.

## After deploy

1. Open the app and confirm the **version** in the sidebar matches the tag or build you expect.
2. Run one **smoke path** you care about (e.g. open a local BIDS dataset, list subjects).
3. File issues with logs (redacted) per `TROUBLESHOOTING.md` if something fails.

## Publishing a public release (maintainers)

See `RELEASING.md` and `docs/RELEASE_POLICY.md`.
