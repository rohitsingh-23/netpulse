# NetPulse Notifications & Network Events Specification

NetPulse v0.7.0 introduces a native macOS notification subsystem designed to proactively inform users about critical network events while maintaining a quiet, non-intrusive default profile.

## 1. Architecture

```
[ NetworkMonitor / NetworkContextManager ]
                   │
                   ▼ (Context / Sample callbacks)
       [ NotificationEngine ]
                   │
                   ▼ (Evaluate policies & filters)
       [ NotificationPolicy ]
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
[ MacOSNotificationBackend ] [ MockNotificationBackend ] (for tests)
         │
         ▼
[ macOS Notification Center ]
```

- **Thread-Safety**: Network monitoring runs on background threads. Event evaluation occurs without locking or blocking the high-frequency speed measurement loop.
- **UI Decoupling**: The notification engine does not depend directly on PySide6 or rumps. Events are marshaled to the UI through the `UIBridge` Qt Signal mechanism.

---

## 2. Event Types & Semantics

| Event Type | Trigger Condition | Default State |
| :--- | :--- | :--- |
| `NETWORK_CONNECTED` | Connection established after launch, disconnect, or no-network state | **Enabled** |
| `NETWORK_DISCONNECTED` | Active primary network route drops or interface goes down | **Enabled** |
| `NETWORK_CHANGED` | Direct transition between two networks (e.g. Wi-Fi A → Wi-Fi B or Wi-Fi → Ethernet) | **Enabled** |
| `CONNECTION_RESTORED` | Reconnected to the exact same network after a disconnect in the same session | Disabled |
| `WEAK_SIGNAL` | Wi-Fi RSSI drops below threshold (default: $\le -75$ dBm) with hysteresis | **Enabled** |
| `HIGH_DOWNLOAD_SPEED` | Download speed exceeds user-configured threshold (default: $100$ MB/s) | Disabled |
| `HIGH_UPLOAD_SPEED` | Upload speed exceeds user-configured threshold (default: $50$ MB/s) | Disabled |
| `HIGH_DATA_USAGE` | Total cumulative data used on active network crosses threshold (default: $5.0$ GB) | Disabled |

### Disconnect vs. Restore Semantics
When transitioning from `Disconnected` to `Connected`:
- If reconnecting to the same network and `notify_connection_restored` is enabled, NetPulse emits `CONNECTION_RESTORED` ("Reconnected to {network}").
- If `notify_connection_restored` is disabled, NetPulse emits standard `NETWORK_CONNECTED`.
- **Never sends both** `NETWORK_CONNECTED` and `CONNECTION_RESTORED` for the same event.

---

## 3. Rate-Limiting, Deduplication & Hysteresis

To avoid notification fatigue, NetPulse implements multiple layers of filtering in `NotificationPolicy`:

### A. Cooldown Windows
Each event category has a mandatory minimum cooldown between notifications:
- Network Lifecycle (`CONNECTED`, `DISCONNECTED`, `CHANGED`, `RESTORED`): $5$ seconds
- Weak Wi-Fi Signal: $60$ seconds
- Speed Alerts (`DOWNLOAD`, `UPLOAD`): $45$ seconds
- Data Usage Alert: $300$ seconds ($5$ minutes)

### B. Payload Deduplication
Identical message text is suppressed if dispatched within double the cooldown window.

### C. Metric State Hysteresis
Continuous signals such as RSSI and instantaneous throughput oscillate rapidly near boundaries. NetPulse uses dual-threshold state machines to prevent flapping:

1. **Weak Wi-Fi Signal**:
   - **Weak trigger**: $\text{RSSI} \le -75\text{ dBm}$
   - **Recovery threshold**: $\text{RSSI} \ge -70\text{ dBm}$ (5 dBm recovery gap)
   - Notifications fire only on the transition from *Normal* $\to$ *Weak*. It remains silent while weak, and will only re-arm once signal strength returns to $\ge -70$ dBm.

2. **Speed Thresholds**:
   - **Trigger**: $\text{Speed} \ge \text{Threshold}$ (e.g. $100$ MB/s)
   - **Recovery / Re-arm**: $\text{Speed} < \text{Threshold} \times 0.8$ (e.g. $80$ MB/s)

3. **Data Usage Threshold**:
   - Fires once when cumulative network session bytes cross the configured threshold ($5.0$ GB default).
   - Re-arms automatically when switching to a new network or starting a new session.

---

## 4. Privacy & Location Services

- **Zero PII Leaks**: NetPulse notifications never expose hardware MAC addresses, BSSIDs, router IPs, or passwords.
- **Location Services Fallback**: When running without Location Services authorization, macOS redacts the Wi-Fi SSID. NetPulse gracefully labels the network `"Wi-Fi Network"` in all notification titles and bodies.
- **Offline / Local**: 100% of notification logic executes locally using native macOS APIs. No telemetry, third-party push services, or cloud daemons are used.

---

## 5. Modern UserNotifications.framework & Authorization

NetPulse v0.7.0+ uses Apple's modern `UserNotifications.framework` (`UNUserNotificationCenter`, `UNMutableNotificationContent`, `UNNotificationRequest`, and `UNNotificationSound`), completely replacing deprecated `NSUserNotificationCenter` APIs.

### Authorization Workflow
Upon startup, `MacOSNotificationBackend` queries `UNUserNotificationCenter.currentNotificationCenter()` and asynchronously requests alert and sound authorization via `requestAuthorizationWithOptions_completionHandler_`:
- **Options Requested**: `UNAuthorizationOptionAlert` (4) | `UNAuthorizationOptionSound` (2).
- **System Settings**: Once prompted or registered, notifications appear in **System Settings → Notifications → NetPulse** (or Terminal/Python in dev mode).
- **Focus & DND**: Delivery strictly honors user Focus, Do Not Disturb, and Notification Center scheduling rules set at the macOS system level.

### Development Mode (Running from source / Python)
- When executed as `python -m netpulse.app`, `UNUserNotificationCenter` operates under the context of the host Python/Terminal executable bundle.
- Authorization requests are granted based on the host process's notification permissions.
- In headless/non-interactive terminal contexts, macOS may queue notifications silently in Notification Center without displaying alert banners.

### Packaged Mode (Phase 8 `.app` Bundle)
- In the final packaged `.app` bundle, the application holds its dedicated `CFBundleIdentifier` (`com.netpulse.app`) and app icon.
- macOS displays the native authorization dialog for NetPulse on first launch and routes notifications through NetPulse's dedicated Notification Center entry.
