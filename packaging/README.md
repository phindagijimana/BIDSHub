# Packaging BIDSHub as a desktop app

The desktop app bundles Python + Streamlit + all deps, starts the server
locally, and shows it in a native window. Mutable state (the SQLite DB,
downloads, cohorts, logs) lives in a per-user directory — see `src/app_paths.py`
and `desktop/bootstrap.py` — never inside the read-only bundle.

## One-time setup
```
pip install -r requirements.txt -r requirements-desktop.txt
python packaging/make_icons.py        # -> packaging/icons/BIDSHub.{icns,ico}
```

## Build (per OS, on that OS)
```
bash packaging/build.sh               # -> dist/BIDSHub/ (onedir) + dist/BIDSHub.app (macOS)
```

## macOS deliverable
```
bash packaging/make_dmg.sh            # -> dist/BIDSHub.dmg  (unsigned)
# Signed + notarized (needs an Apple Developer ID):
DEVELOPER_ID_APP="Developer ID Application: NAME (TEAMID)" \
NOTARY_PROFILE="bidshub-notary" \
  bash packaging/sign_macos.sh
```
Without signing, Gatekeeper blocks the app; first launch needs right-click ->
Open. Distribute signed + notarized for a clean launch.

## Windows deliverable
```
pyinstaller packaging\bidshub.spec    # dist\BIDSHub\
iscc packaging\windows_installer.iss  # dist\BIDSHub-Setup.exe  (needs Inno Setup)
```
Sign with `signtool` and an Authenticode certificate for SmartScreen trust.

## Notes
- The server runs as a child process (`--role=server`); the launcher opens the
  window. Port is pinned via `STREAMLIT_SERVER_PORT` so a stray
  `.streamlit/config.toml` can't override it.
- Single instance: a `<data_dir>/.desktop.lock` records the running port; a
  second launch focuses the existing instance instead of starting another.
- DB upgrades: `desktop/migrations.py` applies versioned, recorded migrations on
  every launch (append-only registry). Add future schema changes there.
- Logs: `<data_dir>/logs/desktop.log` (windowed builds have no console).
- Bundle size is ~500 MB+ (scientific stack: numpy/pandas/nibabel/pybids/...).

## Production readiness

Ready: per-user data dir + versioned migrations, deterministic server port,
single-instance guard, frozen-bundle smoke test, icons, .dmg/.exe packaging,
hardened-runtime entitlements, per-OS/arch build CI with a tagged release job.

Before public distribution you still need:
- **Signing/notarization** — set repo var `SIGN_RELEASES=true` and the Apple
  secrets (see `.github/workflows/desktop-build.yml`); unsigned apps are blocked
  by Gatekeeper / warned by SmartScreen.
- **A green CI run** — the workflow has not been executed yet; the first run on
  Windows / Intel macOS may surface PyInstaller hidden-import gaps.

Deferred (intentionally out of scope for v1):
- In-place auto-update (Sparkle/Squirrel) — current behaviour is notify-and-link.
- OS keychain storage for platform credentials (today: in-app entry / `.env`).
- Dependency-license aggregation and any data-handling/compliance review.
