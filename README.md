# NetPulse

A lightweight, privacy-first network monitoring application that lives in the macOS menu bar.

## Features (v0.7.0)

- **Native macOS Notifications (`UserNotifications.framework`)** — modern, proactive alerts for connection lifecycle (connected, disconnected, changed, restored), weak Wi-Fi signal, speed spikes, and data usage thresholds using `UNUserNotificationCenter`
- **Rate-Limiting & Anti-Spam Architecture** — per-event cooldowns, payload deduplication, and dual-boundary hysteresis (e.g. weak signal trigger $\le -75$ dBm, recovery $\ge -70$ dBm)
- **User-Configurable Alerts** — granular toggles and thresholds in the Settings dashboard tab and quick toggle in the menu bar

- **Network & Interface Intelligence** — tracks which physical network and adapter is carrying your traffic
- **CoreWLAN Wi-Fi Telemetry** — exposes signal strength (RSSI), noise, channel number, frequency band (2.4/5/6 GHz), channel width (20–160 MHz), PHY protocol (Wi-Fi 6 / 802.11ax), transmit link rate, and security (WPA2/WPA3)
- **Networks Dashboard Tab** — dedicated dashboard page featuring an active connection card, RF status, IP addresses, and known historical networks
- **Logical SSID Grouping** — roams seamlessly across multiple Access Points (BSSIDs) while grouping history under the single logical Wi-Fi network
- **Network-Aware Historical Persistence** — SQLite schema v2 maintains network-specific hourly, daily, and monthly rollups (`network_hourly_stats`, `network_daily_stats`, `network_monthly_stats`)
- **Zero Byte Contamination on Switching** — detects network transitions (e.g. Wi-Fi A → Wi-Fi B, Wi-Fi → Ethernet) and immediately flushes the outgoing network's staged traffic before initializing the new baseline
- **Dual-Scope Accounting (Zero Double Counting)** — cleanly distinguishes per-interface counters from system-wide aggregates
- **Atomic Database Migration** — upgrades v1 databases automatically on startup, safely placing pre-Phase 6 records into a dedicated `__SYSTEM_LEGACY__` ("System Total (Legacy)") network without rewriting history
- **macOS Location Services Privacy Compliance** — if Location permission is not granted, gracefully displays `"Wi-Fi Network"` in UI and notifications while keeping all RF physics, interface stats, and live bandwidth operational
- **100% Offline & Zero ISP Guessing** — offline ISP detection is not supported on macOS. NetPulse never performs external lookups, geolocations, or heuristic guesses for ISPs
- **Interactive Popover & Menu-Bar Display** — live speeds, graph previews, and configuration menus directly in macOS status bar
- **Dark, Light & System Appearance** — native macOS look and feel across dashboard and popover


## Privacy

NetPulse is **100% local and offline**.
- No external network requests
- No telemetry, analytics, or tracking
- No accounts, cloud sync, or remote dependencies
- Raw BSSIDs (hardware AP MAC addresses) are never displayed in the UI and are stored only as salted cryptographic hashes
- NetPulse respects macOS Location Services privacy and never attempts to bypass permission controls

## Architecture

```
PreferencesManager (JSON, ~/Library/Application Support/NetPulse/)
         │
         ↓
NetworkMonitor (background thread, psutil)
    │ subscribe/callback (UIBridge)
    ↓
SpeedCalculator (pure calculations)
    ↓
NetworkSample (immutable dataclass, UTC timestamp)
    ↓
DataBuffer (thread-safe rolling buffer, 1 hour max)
    ↓
MenuBarController (rumps)  <--->  NetworkPopover (PySide6)
    │ uses                             │
    ↓                                  ↓
format_menubar_title()           BandwidthGraph (PyQtGraph)
```

### Module Structure

```
netpulse/
├── app.py                    # Entry point, Qt application, wiring
├── __main__.py               # python -m netpulse support
├── config/
│   ├── models.py             # DisplayMode, UnitMode, AppPreferences
│   └── preferences.py        # JSON persistence manager
├── core/
│   ├── interface_identity.py # Stable adapter identity model
│   ├── network_identity.py   # Logical network & SSID identity
│   ├── network_context.py    # Connection snapshot & RF metadata
│   ├── network_sample.py     # Lightweight immutable sample dataclass
│   ├── speed_calculator.py   # Pure speed computation
│   ├── data_buffer.py        # Thread-safe rolling buffer
│   └── network_monitor.py    # Background pernic engine + session stats
├── hardware/
│   ├── discovery.py          # SystemConfiguration interface discovery
│   ├── wifi.py               # CoreWLAN Wi-Fi telemetry inspector
│   └── context_manager.py    # Network context coordinator & publisher
├── storage/
│   ├── database.py           # SQLite connection & v2 schema migration
│   ├── models.py             # Hourly, Daily, Monthly & Network records
│   ├── aggregator.py         # Network-aware staged rollup aggregator
│   └── repository.py         # Read queries for historical network analytics
├── menubar/
│   ├── controller.py         # rumps menu-bar app with config menus
│   └── display.py            # Menu-bar title formatting (5 modes)
├── ui/
│   ├── bridge.py             # Qt Signal routing from background thread
│   ├── dashboard.py          # Desktop Analytics Dashboard
│   ├── graph.py              # PyQtGraph BandwidthGraph
│   ├── graph_data_provider.py# Live & historical graph data providers
│   ├── networks.py           # Networks page (active RF + known networks)
│   ├── live.py               # Live speeds page
│   ├── overview.py           # Overview summary page
│   ├── session.py            # Session metrics page
│   ├── settings.py           # Settings configuration page
│   └── popover.py            # PySide6 NetworkPopover
└── utils/
    ├── constants.py          # App-wide constants (v0.6.0)
    ├── formatters.py         # Speed/byte formatting
    └── log.py                # Logging configuration
```

## Requirements

- macOS
- Python ≥ 3.9

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd net-plus

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest
```

## Run from Source

```bash
python -m netpulse.app
```

The app appears in the macOS menu bar showing live download/upload speeds. Click the menu bar item to:

- View current speeds
- Change display mode (Download + Upload, Download Only, Upload Only, Compact, Smart)
- Change speed units (Automatic, KB/s, MB/s, GB/s)
- Change refresh interval (0.5s, 1s, 2s, 5s)
- Toggle native notifications
- View session download/upload totals
- Open the Network Analytics Dashboard

Settings are saved automatically and persist between launches in `~/Library/Application Support/NetPulse/`.

## Data Management & Reset

NetPulse provides user-controlled data management within **Dashboard → Settings → Data & Storage**:
- **Reset Statistics & History**: Permanently deletes SQLite historical tables, network history, and session metrics while keeping preferences intact.
- **Reset All NetPulse Data**: Restores NetPulse to clean first-run factory state, resetting both database history and preferences.
- All reset operations enforce confirmation dialogs and reset internal counters to prevent artificial bandwidth spikes.

See [DATA_MANAGEMENT.md](DATA_MANAGEMENT.md) for full storage architecture and safety details.

## Build Local Application (.app & .dmg)

To build a standalone macOS application bundle and drag-and-drop installer disk image:

```bash
./scripts/build_app.sh
```

Outputs:
- **Application Bundle**: `dist/NetPulse.app`
- **Disk Image**: `dist/NetPulse-0.7.0.dmg`

See [PACKAGING.md](PACKAGING.md) for full packaging specifications and Location Services configuration.

## Run Tests

```bash
pytest tests/
```

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Core network engine + clean architecture | ✅ |
| 2 | Menu-bar controller + configuration | ✅ |
| 3 | PySide6 popover + live graph | ✅ |
| 4 | Full network analytics dashboard | ✅ |
| 5 | SQLite persistence & multi-tier aggregation | ✅ |
| 6 | Network & interface intelligence (CoreWLAN + Location fallback) | ✅ |
| 7 | Notifications & event engine (UserNotifications.framework) | ✅ |
| 8 | Packaging, standalone .app bundle & local DMG distribution | ✅ |
| **8.1** | **Data Management & Safe Reset Architecture** | **✅** |
| 9 | Developer ID signing, Apple notarization & release distribution | Planned |

## License

[MIT](LICENSE)
