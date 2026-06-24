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
- Logs: `<data_dir>/logs/desktop.log` (windowed builds have no console).
- Bundle size is ~500 MB+ (scientific stack: numpy/pandas/nibabel/pybids/...).
