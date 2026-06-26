#!/usr/bin/env bash
# Package dist/BIDSHub (PyInstaller onedir) into a portable .AppImage.
# Linux only. Run after `pyinstaller packaging/bidshub.spec`.
# Output: dist/BIDSHub-x86_64.AppImage
#
# An AppImage is the Linux equivalent of the macOS .dmg / Windows installer:
# a single self-contained, double-clickable file. We wrap PyInstaller's onedir
# bundle in an AppDir (AppRun + .desktop + icon) and seal it with appimagetool.
set -euo pipefail
cd "$(dirname "$0")/.."

ONEDIR="dist/BIDSHub"
APPDIR="dist/BIDSHub.AppDir"
OUT="dist/BIDSHub-x86_64.AppImage"
ICON_SRC="packaging/icons/icon_1024.png"

[ -d "$ONEDIR" ] || { echo "ERROR: $ONEDIR not found — run pyinstaller first"; exit 1; }

echo "==> Building AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -r "$ONEDIR"/. "$APPDIR/usr/bin/"

# AppRun: entry point AppImage executes on launch.
cat > "$APPDIR/AppRun" <<'SH'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/BIDSHub" "$@"
SH
chmod +x "$APPDIR/AppRun"

# .desktop entry (required; Icon= must match the icon file's basename).
cat > "$APPDIR/BIDSHub.desktop" <<'SH'
[Desktop Entry]
Type=Application
Name=BIDSHub
Comment=Multi-platform neuroimaging dataset management
Exec=BIDSHub
Icon=BIDSHub
Categories=Science;MedicalSoftware;Utility;
Terminal=false
SH

# Icon at AppDir root (appimagetool requires one).
if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$APPDIR/BIDSHub.png"
else
  echo "WARNING: $ICON_SRC missing — run packaging/make_icons.py first"
fi

echo "==> Fetching appimagetool"
if [ ! -x ./appimagetool ]; then
  curl -sSL -o appimagetool \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x appimagetool
fi

echo "==> Sealing $OUT"
rm -f "$OUT"
# --appimage-extract-and-run avoids needing FUSE on the CI runner.
ARCH=x86_64 ./appimagetool --appimage-extract-and-run "$APPDIR" "$OUT"
rm -rf "$APPDIR"

echo "==> Done: $OUT ($(du -h "$OUT" | cut -f1))"
