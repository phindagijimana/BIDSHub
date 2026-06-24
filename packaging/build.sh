#!/usr/bin/env bash
# Build the BIDSHub desktop bundle with PyInstaller.
# Run from the repo root (uses the active venv's pyinstaller).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Cleaning previous build"
rm -rf build dist

echo "==> Building (this is slow; the bundle is large)"
pyinstaller packaging/bidshub.spec --noconfirm --clean

echo "==> Done. Output:"
ls -la dist/
if [ -d dist/BIDSHub.app ]; then echo "macOS app: dist/BIDSHub.app"; fi
echo "Launch (onedir): ./dist/BIDSHub/BIDSHub"
