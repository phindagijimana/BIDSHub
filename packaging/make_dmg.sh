#!/usr/bin/env bash
# Package dist/BIDSHub.app into a compressed, drag-to-Applications .dmg.
# macOS only. Run after packaging/build.sh.   Output: dist/BIDSHub.dmg
set -euo pipefail
cd "$(dirname "$0")/.."

APP="dist/BIDSHub.app"
DMG="dist/BIDSHub.dmg"
VOL="BIDSHub"

[ -d "$APP" ] || { echo "ERROR: $APP not found — run packaging/build.sh first"; exit 1; }

echo "==> Staging .dmg contents"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"   # drag-to-install affordance

echo "==> Building $DMG"
rm -f "$DMG"
hdiutil create -volname "$VOL" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"

echo "==> Done: $DMG ($(du -h "$DMG" | cut -f1))"
