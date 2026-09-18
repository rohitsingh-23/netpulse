"""Comprehensive unit tests for NetPulse notification subsystem."""

from datetime import datetime, timezone
import pytest

from netpulse.config.models import AppPreferences
from netpulse.config.preferences import PreferencesManager
from netpulse.core.interface_identity import InterfaceIdentity
from netpulse.core.network_context import NetworkContext
from netpulse.core.network_identity import NetworkIdentity
from netpulse.core.network_sample import NetworkSample
from netpulse.notifications.backend import MockNotificationBackend
from netpulse.notifications.engine import NotificationEngine
from netpulse.notifications.models import NotificationEvent, NotificationType
from netpulse.notifications.policy import NotificationPolicy



@pytest.fixture
def prefs_manager(tmp_path) -> PreferencesManager:
    """Fixture providing isolated PreferencesManager."""
    mgr = PreferencesManager(path=tmp_path / "test_prefs.json")
    mgr.load()
    return mgr


@pytest.fixture
def mock_backend() -> MockNotificationBackend:
    """Fixture providing MockNotificationBackend."""
    return MockNotificationBackend()


@pytest.fixture
def engine(prefs_manager, mock_backend) -> NotificationEngine:
    """Fixture providing NotificationEngine with mocked backend and short cooldowns."""
    cooldowns = {t: 0.1 for t in NotificationType}
    policy = NotificationPolicy(prefs_manager, cooldowns=cooldowns)
    return NotificationEngine(prefs_manager=prefs_manager, policy=policy, backend=mock_backend)


def make_wifi_context(
    ssid: str,
    interface: str = "en0",
    rssi: int = -60,
    connected: bool = True,
    permission_restricted: bool = False,
) -> NetworkContext:
    iface = InterfaceIdentity.create(
        bsd_name=interface,
        display_name="Wi-Fi",
        interface_type="wifi",
        is_primary=True,
    )
    ident = NetworkIdentity.create_wifi(
        ssid=ssid if not permission_restricted else None,
        interface_id=iface.interface_id,
        permission_restricted=permission_restricted,
    )
    return NetworkContext(
        timestamp=datetime.now(timezone.utc),
        interface=iface,
        network=ident,
        is_connected=connected,
        rssi=rssi,
        permission_restricted=permission_restricted,
    )


def make_ethernet_context(interface: str = "en1", connected: bool = True) -> NetworkContext:
    iface = InterfaceIdentity.create(
        bsd_name=interface,
        display_name="Ethernet",
        interface_type="ethernet",
        is_primary=True,
    )
    ident = NetworkIdentity.create_ethernet(interface_id=iface.interface_id)
    return NetworkContext(
        timestamp=datetime.now(timezone.utc),
        interface=iface,
        network=ident,
        is_connected=connected,
    )


# ----------------------------------------------------------------------
# 1. Network Connected Event
# ----------------------------------------------------------------------
def test_network_connected_event(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    ctx1 = NetworkContext.disconnected()
    ctx2 = make_wifi_context(ssid="Rohit-Home")

    engine.on_context_updated(ctx1)
    assert len(mock_backend.delivered_events) == 0

    engine.on_context_updated(ctx2)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.NETWORK_CONNECTED
    assert "Rohit-Home" in ev.body


# ----------------------------------------------------------------------
# 2. Network Disconnected Event
# ----------------------------------------------------------------------
def test_network_disconnected_event(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    ctx1 = make_wifi_context(ssid="Rohit-Home")
    ctx2 = NetworkContext.disconnected()

    engine.on_context_updated(ctx1)
    mock_backend.clear()

    engine.on_context_updated(ctx2)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.NETWORK_DISCONNECTED
    assert "Rohit-Home" in ev.body


# ----------------------------------------------------------------------
# 3. Network Changed Event
# ----------------------------------------------------------------------
def test_network_changed_event(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    ctx_home = make_wifi_context(ssid="Rohit-Home")
    ctx_office = make_wifi_context(ssid="Office-WiFi")

    engine.on_context_updated(ctx_home)
    mock_backend.clear()

    engine.on_context_updated(ctx_office)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.NETWORK_CHANGED
    assert "Rohit-Home → Office-WiFi" in ev.body


# ----------------------------------------------------------------------
# 4. No Duplicate Event During Unchanged State
# ----------------------------------------------------------------------
def test_no_duplicate_event_during_unchanged_state(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    ctx = make_wifi_context(ssid="Rohit-Home")
    engine.on_context_updated(ctx)
    assert len(mock_backend.delivered_events) == 1

    # Identical update
    engine.on_context_updated(ctx)
    assert len(mock_backend.delivered_events) == 1


# ----------------------------------------------------------------------
# 5. Connection Restoration
# ----------------------------------------------------------------------
def test_connection_restored_event(
    engine: NotificationEngine,
    prefs_manager: PreferencesManager,
    mock_backend: MockNotificationBackend,
):
    prefs_manager.update(notify_connection_restored=True)

    ctx_conn = make_wifi_context(ssid="Rohit-Home")
    ctx_disc = NetworkContext.disconnected()

    engine.on_context_updated(ctx_conn)
    mock_backend.clear()

    engine.on_context_updated(ctx_disc)
    mock_backend.clear()

    # Reconnect to Rohit-Home
    engine.on_context_updated(ctx_conn)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.CONNECTION_RESTORED
    assert "Reconnected to Rohit-Home" in ev.body


# ----------------------------------------------------------------------
# 6 & 7. Weak RSSI Threshold and Hysteresis
# ----------------------------------------------------------------------
def test_weak_signal_rssi_threshold_and_hysteresis(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    # Initial good signal (-60 dBm)
    ctx1 = make_wifi_context(ssid="Rohit-Home", rssi=-60)
    engine.on_context_updated(ctx1)
    mock_backend.clear()

    # Drop to -76 dBm (crosses threshold <= -75 dBm)
    ctx2 = make_wifi_context(ssid="Rohit-Home", rssi=-76)
    engine.on_context_updated(ctx2)
    assert len(mock_backend.delivered_events) == 1
    assert mock_backend.delivered_events[0].event_type == NotificationType.WEAK_SIGNAL
    assert "-76 dBm" in mock_backend.delivered_events[0].body

    # Signal oscillates slightly around -74 dBm (does not hit recovery >= -70 dBm)
    mock_backend.clear()
    ctx3 = make_wifi_context(ssid="Rohit-Home", rssi=-74)
    engine.on_context_updated(ctx3)
    assert len(mock_backend.delivered_events) == 0

    # Dips further to -80 dBm -> Still in weak state, no spam
    ctx4 = make_wifi_context(ssid="Rohit-Home", rssi=-80)
    engine.on_context_updated(ctx4)
    assert len(mock_backend.delivered_events) == 0

    # Recovers to -68 dBm (>= -70 dBm) -> Resets weak state, but does not notify on recovery
    ctx5 = make_wifi_context(ssid="Rohit-Home", rssi=-68)
    engine.on_context_updated(ctx5)
    assert len(mock_backend.delivered_events) == 0

    # Drops again to -77 dBm -> Re-armed! Should trigger alert again
    import time
    time.sleep(0.15)  # satisfy cooldown
    ctx6 = make_wifi_context(ssid="Rohit-Home", rssi=-77)
    engine.on_context_updated(ctx6)
    assert len(mock_backend.delivered_events) == 1
    assert mock_backend.delivered_events[0].event_type == NotificationType.WEAK_SIGNAL


# ----------------------------------------------------------------------
# 8, 9, 10. High Speed Thresholds & Re-arm
# ----------------------------------------------------------------------
def test_high_speed_threshold_crossing_and_rearm(
    engine: NotificationEngine,
    prefs_manager: PreferencesManager,
    mock_backend: MockNotificationBackend,
):
    prefs_manager.update(
        notify_high_download_speed=True,
        notify_high_upload_speed=True,
        download_speed_threshold_mbps=100.0,
        upload_speed_threshold_mbps=50.0,
    )

    t0 = datetime.now(timezone.utc)

    # 1. Normal speed sample (10 MB/s download, 5 MB/s upload)
    s1 = NetworkSample(t0, 10_000_000, 5_000_000, 100, 50, "en0", "wifi:home")
    engine.on_sample_received(s1)
    assert len(mock_backend.delivered_events) == 0

    # 2. Exceed download speed: 120 MB/s
    s2 = NetworkSample(t0, 120_000_000, 5_000_000, 220, 50, "en0", "wifi:home")
    engine.on_sample_received(s2)
    assert len(mock_backend.delivered_events) == 1
    ev_dl = mock_backend.delivered_events[0]
    assert ev_dl.event_type == NotificationType.HIGH_DOWNLOAD_SPEED
    assert "Download speed exceeded 100 MB/s" in ev_dl.body

    # 3. Next sample stays high at 130 MB/s -> No spam
    mock_backend.clear()
    s3 = NetworkSample(t0, 130_000_000, 5_000_000, 350, 50, "en0", "wifi:home")
    engine.on_sample_received(s3)
    assert len(mock_backend.delivered_events) == 0

    # 4. Falls below 80% (e.g. 70 MB/s) -> Re-arms
    s4 = NetworkSample(t0, 70_000_000, 5_000_000, 420, 50, "en0", "wifi:home")
    engine.on_sample_received(s4)
    assert len(mock_backend.delivered_events) == 0

    # 5. Exceed upload speed: 60 MB/s (> 50 MB/s)
    import time
    time.sleep(0.15)
    s5 = NetworkSample(t0, 10_000_000, 60_000_000, 430, 110, "en0", "wifi:home")
    engine.on_sample_received(s5)
    assert len(mock_backend.delivered_events) == 1
    ev_ul = mock_backend.delivered_events[0]
    assert ev_ul.event_type == NotificationType.HIGH_UPLOAD_SPEED
    assert "Upload speed exceeded 50 MB/s" in ev_ul.body


# ----------------------------------------------------------------------
# 11. Data Usage Threshold Crossing
# ----------------------------------------------------------------------
def test_data_usage_threshold_crossing(
    engine: NotificationEngine,
    prefs_manager: PreferencesManager,
    mock_backend: MockNotificationBackend,
):
    # Set threshold low for test (0.01 GB ~ 10.7 MB)
    prefs_manager.update(
        notify_high_data_usage=True,
        data_usage_threshold_gb=0.01,
    )

    t0 = datetime.now(timezone.utc)
    # 5 MB traffic
    s1 = NetworkSample(t0, 5_000_000, 0, 5_000_000, 0, "en0", "wifi:home")
    engine.on_sample_received(s1)
    assert len(mock_backend.delivered_events) == 0

    # Cross 10.7 MB with another 7 MB -> Total 12 MB
    s2 = NetworkSample(t0, 7_000_000, 0, 12_000_000, 0, "en0", "wifi:home")
    engine.on_sample_received(s2)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.HIGH_DATA_USAGE

    # Further traffic does not repeat alert
    mock_backend.clear()
    s3 = NetworkSample(t0, 10_000_000, 0, 22_000_000, 0, "en0", "wifi:home")
    engine.on_sample_received(s3)
    assert len(mock_backend.delivered_events) == 0


# ----------------------------------------------------------------------
# 12 & 13. Cooldown & Duplicate Suppression
# ----------------------------------------------------------------------
def test_notification_cooldown_and_duplicate_suppression(
    prefs_manager: PreferencesManager,
    mock_backend: MockNotificationBackend,
):
    # Enforce 10s cooldown
    cooldowns = {NotificationType.NETWORK_CONNECTED: 10.0}
    policy = NotificationPolicy(prefs_manager, cooldowns=cooldowns)
    eng = NotificationEngine(prefs_manager, policy=policy, backend=mock_backend)

    ctx1 = make_wifi_context(ssid="Rohit-Home")
    ctx_disc = NetworkContext.disconnected()

    eng.on_context_updated(ctx1)
    assert len(mock_backend.delivered_events) == 1

    # Disconnect and immediately reconnect within 10s
    eng.on_context_updated(ctx_disc)
    eng.on_context_updated(ctx1)

    # Reconnected event suppressed by 10s cooldown
    # Only connected + disconnected should exist
    assert len(mock_backend.delivered_events) == 2  # CONNECTED + DISCONNECTED


# ----------------------------------------------------------------------
# 14. Preferences Persistence
# ----------------------------------------------------------------------
def test_preferences_persistence(tmp_path):
    path = tmp_path / "notif_prefs.json"
    mgr1 = PreferencesManager(path=path)
    mgr1.load()
    mgr1.update(
        notifications_enabled=False,
        notify_weak_signal=False,
        weak_signal_rssi_threshold=-80,
        download_speed_threshold_mbps=250.0,
    )

    mgr2 = PreferencesManager(path=path)
    p = mgr2.load()
    assert p.notifications_enabled is False
    assert p.notify_weak_signal is False
    assert p.weak_signal_rssi_threshold == -80
    assert p.download_speed_threshold_mbps == 250.0


# ----------------------------------------------------------------------
# 15. Disabled Notification Categories
# ----------------------------------------------------------------------
def test_disabled_notification_categories(
    engine: NotificationEngine,
    prefs_manager: PreferencesManager,
    mock_backend: MockNotificationBackend,
):
    # Disable connected and disconnected notifications
    prefs_manager.update(
        notify_network_connected=False,
        notify_network_disconnected=False,
    )

    ctx = make_wifi_context(ssid="Rohit-Home")
    engine.on_context_updated(ctx)
    assert len(mock_backend.delivered_events) == 0

    engine.on_context_updated(NetworkContext.disconnected())
    assert len(mock_backend.delivered_events) == 0


# ----------------------------------------------------------------------
# 16. Location Permission Fallback
# ----------------------------------------------------------------------
def test_location_permission_fallback(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    # Restricted SSID
    ctx_unpermitted = make_wifi_context(ssid="", permission_restricted=True)
    engine.on_context_updated(NetworkContext.disconnected())
    mock_backend.clear()

    engine.on_context_updated(ctx_unpermitted)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.NETWORK_CONNECTED
    assert "Wi-Fi Network" in ev.body
    # Ensure no BSSID or internal unpermitted tag leaked into title/body
    assert "bssid" not in ev.body.lower()
    assert "wifi-unpermitted" not in ev.body


# ----------------------------------------------------------------------
# 17. Wi-Fi to Ethernet Switching
# ----------------------------------------------------------------------
def test_wifi_to_ethernet_event(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    ctx_wifi = make_wifi_context(ssid="Rohit-Home")
    ctx_eth = make_ethernet_context()

    engine.on_context_updated(ctx_wifi)
    mock_backend.clear()

    engine.on_context_updated(ctx_eth)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.NETWORK_CHANGED
    assert "Rohit-Home → Ethernet" in ev.body


# ----------------------------------------------------------------------
# 18. No Notification Generated on Regular Speed Samples
# ----------------------------------------------------------------------
def test_no_notification_on_every_speed_sample(
    engine: NotificationEngine,
    prefs_manager: PreferencesManager,
    mock_backend: MockNotificationBackend,
):
    prefs_manager.update(
        notify_high_download_speed=True,
        download_speed_threshold_mbps=100.0,
    )

    assert len(mock_backend.delivered_events) == 0


# ----------------------------------------------------------------------
# 19. Wi-Fi to Wi-Fi Switching
# ----------------------------------------------------------------------
def test_wifi_to_wifi_switching(engine: NotificationEngine, mock_backend: MockNotificationBackend):
    ctx_a = make_wifi_context(ssid="Wi-Fi-A")
    ctx_b = make_wifi_context(ssid="Wi-Fi-B")

    engine.on_context_updated(ctx_a)
    mock_backend.clear()

    engine.on_context_updated(ctx_b)
    assert len(mock_backend.delivered_events) == 1
    ev = mock_backend.delivered_events[0]
    assert ev.event_type == NotificationType.NETWORK_CHANGED
    assert "Wi-Fi-A → Wi-Fi-B" in ev.body


# ----------------------------------------------------------------------
# 20. Application Restart Notification State
# ----------------------------------------------------------------------
def test_application_restart_notification_state(tmp_path):
    path = tmp_path / "restart_prefs.json"
    mgr1 = PreferencesManager(path=path)
    mgr1.load()
    mgr1.update(
        notifications_enabled=True,
        notify_high_download_speed=True,
        download_speed_threshold_mbps=150.0,
    )

    backend1 = MockNotificationBackend()
    eng1 = NotificationEngine(mgr1, backend=backend1)
    ctx = make_wifi_context(ssid="Rohit-Home")
    eng1.on_context_updated(ctx)
    assert len(backend1.delivered_events) == 1

    # Simulate restart with fresh engine reading saved preferences
    mgr2 = PreferencesManager(path=path)
    mgr2.load()
    assert mgr2.preferences.download_speed_threshold_mbps == 150.0
    backend2 = MockNotificationBackend()
    eng2 = NotificationEngine(mgr2, backend=backend2)
    # Starts cleanly without false alerts
    assert len(backend2.delivered_events) == 0


# ----------------------------------------------------------------------
# 21. MacOS Notification Backend Modern API Verification
# ----------------------------------------------------------------------
def test_macos_notification_backend_initialization_and_mock():
    from netpulse.notifications.backend import MacOSNotificationBackend, MockNotificationBackend

    # Test MockBackend contract
    mock_b = MockNotificationBackend()
    ev = NotificationEvent(
        event_type=NotificationType.NETWORK_CONNECTED,
        title="Test Title",
        body="Test Body",
    )
    assert mock_b.send(ev) is True
    assert len(mock_b.delivered_events) == 1
    mock_b.clear()
    assert len(mock_b.delivered_events) == 0

    # Test MacOSNotificationBackend instantiates safely without error
    mac_b = MacOSNotificationBackend()
    assert hasattr(mac_b, "_available")
    assert hasattr(mac_b, "_auth_requested")
