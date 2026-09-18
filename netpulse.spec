# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for NetPulse macOS application bundle.

Builds a standalone NetPulse.app bundle with native macOS integrations:
- UserNotifications.framework
- CoreWLAN.framework
- CoreLocation.framework
- SystemConfiguration.framework
- PySide6 & PyQtGraph UI
- rumps status-bar item

Usage:
    pyinstaller netpulse.spec --clean -y
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect hidden imports for dynamic imports in PyObjC, PySide6, and netpulse
hidden_imports = [
    # Netpulse packages
    "netpulse",
    "netpulse.app",
    "netpulse.config",
    "netpulse.config.models",
    "netpulse.config.preferences",
    "netpulse.core",
    "netpulse.core.data_buffer",
    "netpulse.core.interface_identity",
    "netpulse.core.network_context",
    "netpulse.core.network_identity",
    "netpulse.core.network_monitor",
    "netpulse.core.network_sample",
    "netpulse.core.reset_coordinator",
    "netpulse.core.speed_calculator",
    "netpulse.hardware",
    "netpulse.hardware.context_manager",
    "netpulse.hardware.discovery",
    "netpulse.hardware.wifi",
    "netpulse.menubar",
    "netpulse.menubar.controller",
    "netpulse.menubar.display",
    "netpulse.notifications",
    "netpulse.notifications.backend",
    "netpulse.notifications.engine",
    "netpulse.notifications.models",
    "netpulse.notifications.policy",
    "netpulse.storage",
    "netpulse.storage.aggregator",
    "netpulse.storage.database",
    "netpulse.storage.models",
    "netpulse.storage.repository",
    "netpulse.speedtest",
    "netpulse.speedtest.engine",
    "netpulse.speedtest.models",
    "netpulse.platform",
    "netpulse.platform.login_item",
    "netpulse.ui",
    "netpulse.ui.bridge",
    "netpulse.ui.dashboard",
    "netpulse.ui.help",
    "netpulse.ui.live",
    "netpulse.ui.mascot",
    "netpulse.ui.networks",
    "netpulse.ui.overview",
    "netpulse.ui.popover",
    "netpulse.ui.session",
    "netpulse.ui.settings",
    "netpulse.ui.speedtest",
    "netpulse.ui.updates",
    "netpulse.updates",
    "netpulse.updates.models",
    "netpulse.updates.service",
    "netpulse.ui.theme",
    "netpulse.ui.widgets",
    "netpulse.utils",
    "netpulse.utils.constants",
    "netpulse.utils.formatters",
    "netpulse.utils.log",
    # Third party & PyObjC frameworks
    "psutil",
    "rumps",
    "pyqtgraph",
    "objc",
    "Foundation",
    "AppKit",
    "ServiceManagement",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

# Collect any pyqtgraph or PySide6 data files if needed
datas = []
if os.path.exists("resources/NetPulse.icns"):
    datas.append(("resources/NetPulse.icns", "resources"))
if os.path.exists("resources/mascot"):
    datas.append(("resources/mascot", "resources/mascot"))
if os.path.exists("resources/icons"):
    datas.append(("resources/icons", "resources/icons"))

a = Analysis(
    ["netpulse/app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NetPulse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NetPulse",
)

info_plist = {
    "CFBundleName": "NetPulse",
    "CFBundleDisplayName": "NetPulse",
    "CFBundleIdentifier": "com.netpulse.app",
    "CFBundleVersion": "0.7.0",
    "CFBundleShortVersionString": "0.7.0",
    "CFBundlePackageType": "APPL",
    "CFBundleSignature": "????",
    "CFBundleExecutable": "NetPulse",
    "CFBundleIconFile": "NetPulse.icns",
    "LSMinimumSystemVersion": "12.0",
    "LSUIElement": True,  # Menu bar-only application
    "NSHighResolutionCapable": True,
    "NSSupportsAutomaticGraphicsSwitching": True,
    "NSRequiresAquaSystemAppearance": False,
    "NSLocationWhenInUseUsageDescription": (
        "NetPulse uses your location permission to identify the Wi-Fi network your Mac "
        "is connected to. Network data remains entirely on your Mac."
    ),
    "NSLocationUsageDescription": (
        "NetPulse uses your location permission to identify the Wi-Fi network your Mac "
        "is connected to. Network data remains entirely on your Mac."
    ),
    "NSHumanReadableCopyright": "Copyright © 2026 NetPulse Contributors. All rights reserved.",
}

app = BUNDLE(
    coll,
    name="NetPulse.app",
    icon="resources/NetPulse.icns",
    bundle_identifier="com.netpulse.app",
    info_plist=info_plist,
)
