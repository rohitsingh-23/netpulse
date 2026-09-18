#!/bin/bash
set -euo pipefail

APP_NAME="NetPulse"
VERSION="0.7.0"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
DIST_DIR="dist"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
DMG_PATH="${DIST_DIR}/${DMG_NAME}"
STAGING_DIR="${DIST_DIR}/dmg_staging"

if [ ! -d "${APP_PATH}" ]; then
    echo "Error: ${APP_PATH} not found. Please build the .app first."
    exit 1
fi

echo "==> Preparing DMG staging directory..."
rm -rf "${STAGING_DIR}" "${DMG_PATH}"
mkdir -p "${STAGING_DIR}"

echo "==> Copying ${APP_NAME}.app to staging..."
cp -R "${APP_PATH}" "${STAGING_DIR}/"

echo "==> Creating /Applications symlink..."
ln -s /Applications "${STAGING_DIR}/Applications"

echo "==> Building ${DMG_NAME} using hdiutil..."
hdiutil create \
    -volname "${APP_NAME} ${VERSION}" \
    -srcfolder "${STAGING_DIR}" \
    -ov \
    -format UDZO \
    "${DMG_PATH}"

echo "==> Cleaning up staging..."
rm -rf "${STAGING_DIR}"

echo "==> DMG successfully created: ${DMG_PATH}"
ls -lh "${DMG_PATH}"
