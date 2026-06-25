#!/usr/bin/env bash
# Codesign + notarize dist/BIDSHub.app (macOS, requires an Apple Developer ID).
# Parameterized by environment — nothing secret is committed:
#   DEVELOPER_ID_APP   e.g. "Developer ID Application: Your Name (TEAMID)"
#   NOTARY_PROFILE     a `xcrun notarytool store-credentials` keychain profile
# Usage:  DEVELOPER_ID_APP=... NOTARY_PROFILE=... packaging/sign_macos.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DEVELOPER_ID_APP:?set DEVELOPER_ID_APP}"
: "${NOTARY_PROFILE:?set NOTARY_PROFILE (xcrun notarytool store-credentials)}"
APP="dist/BIDSHub.app"
DMG="dist/BIDSHub.dmg"
ENTITLEMENTS="$(cd "$(dirname "$0")" && pwd)/entitlements.plist"

echo "==> Codesigning (hardened runtime, deep, with entitlements)"
codesign --force --deep --options runtime --timestamp \
  --entitlements "$ENTITLEMENTS" \
  --sign "$DEVELOPER_ID_APP" "$APP"
codesign --verify --strict --verbose=2 "$APP"

echo "==> Building signed .dmg"
packaging/make_dmg.sh
codesign --force --timestamp --sign "$DEVELOPER_ID_APP" "$DMG"

echo "==> Notarizing (submit + wait)"
xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait

echo "==> Stapling"
xcrun stapler staple "$APP"
xcrun stapler staple "$DMG"
echo "==> Signed + notarized: $DMG"
