# NetPulse Data Management & Reset Architecture

This document details NetPulse data persistence locations, reset tiers, internal accounting safety, and privacy boundaries.

---

## 1. Storage Locations

NetPulse stores all persistent user data outside the application bundle in standard macOS Application Support directories:

```text
~/Library/Application Support/NetPulse/
├── netpulse.db          # SQLite v2 historical database (WAL mode)
├── netpulse.db-wal      # SQLite write-ahead log
├── netpulse.db-shm      # SQLite shared memory index
└── preferences.json     # User preferences and notification configuration
```

- **Application Bundle Isolation**: NetPulse never embeds writable database or preferences files inside `NetPulse.app`.
- **Upgrade Resilience**: Application updates, bundle rebuilds, and local reinstalls preserve historical data and settings automatically.
- **Privacy Boundary**: NetPulse operations strictly access `~/Library/Application Support/NetPulse/`. NetPulse never modifies external files or sends telemetry outside the local Mac.

---

## 2. Reset Operations

NetPulse provides two distinct, user-initiated reset operations accessible via **Dashboard → Settings → Data & Storage**.

### A. Reset Statistics & History

- **Action Label**: `Reset Statistics & History`
- **Purpose**: Clears all network traffic history, session metrics, and known network identities while keeping user configurations intact.
- **What is Permanently Deleted**:
  - `hourly_stats`
  - `daily_stats`
  - `monthly_stats`
  - `network_hourly_stats`
  - `network_daily_stats`
  - `network_monthly_stats`
  - `networks` (known network catalog)
  - `interfaces` (historical interfaces)
  - Session counters (`session_downloaded`, `session_uploaded`, peaks)
  - In-memory rolling sample buffer (`DataBuffer`)
  - Staged aggregator buffers (`_staged_dl_bytes`, `_staged_ul_bytes`)
- **What is Preserved**:
  - User preferences (`preferences.json`)
  - Menu bar display mode and units
  - Notification enable states and thresholds
  - Appearance theme
  - Sampling interval configuration
  - `NetPulse.app` application bundle
- **Post-Reset State**:
  - Active network connection remains functional and is re-registered with `0 B` usage.
  - Live speed monitoring continues uninterrupted without restarting the app.

---

### B. Reset All NetPulse Data

- **Action Label**: `Reset All NetPulse Data`
- **Purpose**: Returns NetPulse to a clean first-run data state.
- **What is Permanently Deleted**:
  - All items deleted by *Reset Statistics & History*
  - `preferences.json` (re-initialized with factory default settings)
  - Notification cooldown records and hysteresis states
- **What is Preserved**:
  - SQLite schema structure and indexes (`PRAGMA user_version = 2`)
  - `NetPulse.app` bundle and runtime binaries
- **Post-Reset State**:
  - Factory default preferences applied (Auto units, standard appearance, default notification thresholds).
  - Active network connection rediscovered cleanly.
  - Live monitoring continues with factory defaults.

---

## 3. Destructive Deletion & Safety Dialogs

Both reset operations are permanent and cannot be undone. NetPulse does not retain shadow backups of deleted records.

Every reset action enforces a native modal confirmation dialog:
- **Reset Statistics & History**: Requires clicking `Reset History` or `Cancel`.
- **Reset All NetPulse Data**: Requires clicking `Reset Everything` or `Cancel`.

---

## 4. Accounting Safety & Spike Prevention

To prevent artificial multi-gigabyte delta spikes when resetting cumulative byte counters:
1. **Aggregator Purge**: In-memory staged byte buckets are discarded immediately before database deletion.
2. **Baseline Reset**: `NetworkMonitor._previous` snapshot is cleared to `None`.
3. **Fresh Baseline Acquisition**: The first sample following a reset sets a new baseline snapshot without computing a delta against prior or post-reset counters.
4. **Clean Delta Continuation**: Only the second post-reset sample computes a valid elapsed delta, ensuring accurate, spike-free accounting.
