# NetPulse Packaging, macOS Bundle & Distribution Guide

Phase 8 establishes a reproducible build pipeline to package NetPulse into a standalone macOS Application Bundle (`NetPulse.app`) and a distributable disk image (`NetPulse-0.7.0.dmg`).

---

## 1. Prerequisites & Environment

- **Operating System**: macOS 12.0+ (Universal / Apple Silicon arm64)
- **Python**: 3.9+ (tested on Python 3.9.6)
- **Packaging Engine**: PyInstaller 6.22.3 (`pyinstaller`)
- **Disk Image Utility**: Native macOS `hdiutil`
- **Icon Utility**: Native macOS `iconutil`
- **PyObjC Frameworks**: `pyobjc-core`, `pyobjc-framework-Cocoa` (dynamic loading of `UserNotifications`, `CoreWLAN`, `CoreLocation`, `SystemConfiguration`)
- **GUI Engine**: PySide6 & PyQtGraph

---

## 2. Reproducible Build Commands

### Quick Build (App + DMG)
Run the automated build script:
```bash
./scripts/build_app.sh
```

This single command:
1. Validates and generates `resources/NetPulse.icns` if missing.
2. Cleans and executes PyInstaller via [`netpulse.spec`](netpulse.spec).
3. Produces `dist/NetPulse.app`.
4. Assembles a drag-and-drop disk image at `dist/NetPulse-0.7.0.dmg` with `/Applications` symlink.

### Manual Steps
If running steps individually:
```bash
# 1. Build .app bundle
pyinstaller netpulse.spec --clean -y

# 2. Build .dmg disk image
./scripts/create_dmg.sh
```

---

## 3. Application Bundle Structure

```text
dist/NetPulse.app/
└── Contents/
    ├── Frameworks/           # Bundled libraries & frameworks (Python3, Qt6, etc.)
    ├── Info.plist            # macOS application & privacy declarations
    ├── MacOS/
    │   └── NetPulse          # Standalone compiled entry binary
    └── Resources/
        ├── NetPulse.icns     # High-resolution Retina application icon
        ├── base_library.zip  # Frozen Python standard library
        └── PySide6/          # Qt platform plugins & graphics drivers
```

---

## 4. Info.plist Privacy & Permissions Configuration

To enable native macOS privacy dialogs and ensure Location Services and Notifications work seamlessly, [`netpulse.spec`](netpulse.spec) configures the following keys in `Info.plist`:

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `CFBundleIdentifier` | `com.netpulse.app` | Unique bundle identity for permissions & settings |
| `CFBundleName` | `NetPulse` | Menu & system display name |
| `CFBundleShortVersionString`| `0.7.0` | Semantic release version |
| `CFBundleIconFile` | `NetPulse.icns` | Retina icon association |
| `LSMinimumSystemVersion` | `12.0` | Minimum supported macOS version |
| `NSLocationWhenInUseUsageDescription` | Human-readable explanation | Triggers native Location Services dialog for Wi-Fi SSID |
| `NSLocationUsageDescription` | Human-readable explanation | Fallback location prompt |
| `NSHighResolutionCapable` | `True` | Sharp text & graphs on Retina displays |

---

## 5. Location Services & Privacy Compliance

In previous development passes, running unbundled `python -m netpulse.app` meant the process ran under the Python interpreter, which lacks location usage descriptions in its bundle `Info.plist`.

With `dist/NetPulse.app`:
1. **Permission Owner**: macOS identifies `NetPulse` as the requesting application.
2. **System Settings**: NetPulse appears under **System Settings → Privacy & Security → Location Services**.
3. **If Granted**: `CoreWLAN` fetches and displays the active Wi-Fi SSID (e.g., `"Rohit-Home"`).
4. **If Denied / Restricted**: NetPulse gracefully falls back to `"Wi-Fi Network"`, maintaining full RF telemetry (RSSI, channel, band, PHY mode) and speed monitoring without crashing or leaking BSSIDs.

---

## 6. Notifications Integration

Packaged `NetPulse.app` integrates with macOS `UserNotifications.framework`:
- **Identity**: Notifications are dispatched by `UNUserNotificationCenter` under `com.netpulse.app`.
- **System Settings**: NetPulse registers under **System Settings → Notifications → NetPulse**.
- **Delivery**: Notifications display with the custom `NetPulse.icns` icon and respect user Focus and Do Not Disturb settings.

---

## 7. User Data Isolation & Persistence

Packaging does **not** store databases or configuration inside the application bundle:
- **Preferences**: Saved to `~/Library/Application Support/NetPulse/preferences.json`
- **Database**: Saved to `~/Library/Application Support/NetPulse/netpulse.db`

All historical SQLite data and user preferences survive app bundle upgrades and process restarts.

---

## 8. Unsigned Status & Transition to Phase 9

> [!IMPORTANT]
> **Phase 8 builds are unsigned development artifacts.**
> - Gatekeeper will treat newly downloaded or unquarantined unsigned DMGs according to local macOS security policy.
> - To test locally on macOS:
>   ```bash
>   xattr -cr dist/NetPulse.app
>   open dist/NetPulse.app
>   ```
> - **Phase 9 Scope**: Developer ID Application signing, Developer ID Installer signing, Apple Notarization (`notarytool`), Stapling, and Homebrew formula release.
