#!/bin/bash
set -euo pipefail

# Build script for NetPulse.app and DMG distribution
# Usage: ./scripts/build_app.sh

APP_NAME="NetPulse"
VERSION="0.7.0"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${PROJECT_DIR}"

echo "=================================================="
echo " Building ${APP_NAME} v${VERSION}"
echo "=================================================="

# Check virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Ensure PyInstaller is available
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller not found. Installing into environment..."
    pip install pyinstaller
fi

# Build icon if missing
if [ ! -f "resources/NetPulse.icns" ]; then
    echo "==> Generating resources/NetPulse.icns..."
    python -c "
from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient, QPen, QPainterPath
from PySide6.QtCore import Qt, QPointF, QRectF
import os, subprocess

icon_sizes = [16, 32, 64, 128, 256, 512, 1024]
iconset_dir = 'resources/NetPulse.iconset'
os.makedirs(iconset_dir, exist_ok=True)

def render_icon(size):
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    margin = size * 0.08
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    radius = size * 0.22
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor('#0f172a'))
    gradient.setColorAt(1.0, QColor('#1e293b'))
    p.setBrush(gradient)
    p.setPen(QPen(QColor('#38bdf8'), size * 0.03))
    p.drawRoundedRect(rect, radius, radius)
    path = QPainterPath()
    w = size
    h = size
    path.moveTo(w * 0.18, h * 0.52)
    path.lineTo(w * 0.32, h * 0.52)
    path.lineTo(w * 0.40, h * 0.32)
    path.lineTo(w * 0.48, h * 0.72)
    path.lineTo(w * 0.56, h * 0.22)
    path.lineTo(w * 0.64, h * 0.62)
    path.lineTo(w * 0.70, h * 0.52)
    path.lineTo(w * 0.82, h * 0.52)
    pen = QPen(QColor('#38bdf8'), size * 0.07, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setBrush(Qt.NoBrush)
    p.setPen(pen)
    p.drawPath(path)
    p.setBrush(QColor('#38bdf8'))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(w * 0.56, h * 0.22), size * 0.04, size * 0.04)
    p.end()
    return img

for sz in [16, 32, 128, 256, 512]:
    img = render_icon(sz)
    img.save(f'{iconset_dir}/icon_{sz}x{sz}.png')
    img2x = render_icon(sz * 2)
    img2x.save(f'{iconset_dir}/icon_{sz}x{sz}@2x.png')

subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', 'resources/NetPulse.icns'], check=True)
"
fi

echo "==> Running PyInstaller build..."
pyinstaller netpulse.spec --clean -y

echo "==> Creating distributable DMG..."
./scripts/create_dmg.sh

echo "=================================================="
echo " Build Complete!"
echo " App: dist/${APP_NAME}.app"
echo " DMG: dist/${APP_NAME}-${VERSION}.dmg"
echo "=================================================="
