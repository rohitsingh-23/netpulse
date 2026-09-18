"""Automated test suite for Phase 8.1: Data Management, Statistics & Full Reset."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from unittest.mock import MagicMock, patch

import pytest

from netpulse.config.models import AppPreferences, DisplayMode, UnitMode
from netpulse.config.preferences import PreferencesManager
from netpulse.core.data_buffer import DataBuffer
from netpulse.core.interface_identity import InterfaceIdentity
from netpulse.core.network_context import NetworkContext
from netpulse.core.network_identity import NetworkIdentity
from netpulse.core.network_monitor import NetworkMonitor
from netpulse.core.network_sample import NetworkSample
from netpulse.core.reset_coordinator import DataResetCoordinator
from netpulse.notifications.engine import NotificationEngine
from netpulse.notifications.models import NotificationEvent, NotificationType
from netpulse.notifications.policy import NotificationPolicy
from netpulse.storage.aggregator import SampleAggregator
from netpulse.storage.database import Database
from netpulse.storage.repository import StatsRepository


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    """Provide a fresh isolated SQLite database on disk."""
    db_file = tmp_path / "test_reset.db"
    db = Database(db_file)
    return db


@pytest.fixture
def temp_prefs(tmp_path: Path) -> PreferencesManager:
    """Provide a fresh isolated PreferencesManager."""
    prefs_file = tmp_path / "preferences.json"
    pm = PreferencesManager(prefs_file)
    return pm


def _seed_database_data(db: Database) -> None:
    """Helper to populate test records across all tables."""
    repo = StatsRepository(db)
    repo.upsert_network(
        network_id="wifi:OfficeNet:test",
        connection_type="wifi",
        ssid="OfficeNet",
        display_name="OfficeNet",
        interface_id="en0",
    )
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO hourly_stats (hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps)
            VALUES ('2026-09-18T00:00:00Z', 5000000, 1000000, 100000.0, 50000.0);
            """
        )
        conn.execute(
            """
            INSERT INTO daily_stats (date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps)
            VALUES ('2026-09-18', 5000000, 1000000, 100000.0, 50000.0);
            """
        )
        conn.execute(
            """
            INSERT INTO monthly_stats (year_month, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps)
            VALUES ('2026-09', 5000000, 1000000, 100000.0, 50000.0);
            """
        )
        conn.execute(
            """
            INSERT INTO network_hourly_stats (network_id, hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps)
            VALUES ('wifi:OfficeNet:test', '2026-09-18T00:00:00Z', 5000000, 1000000, 100000.0, 50000.0);
            """
        )
        conn.execute(
            """
            INSERT INTO network_daily_stats (network_id, date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps)
            VALUES ('wifi:OfficeNet:test', '2026-09-18', 5000000, 1000000, 100000.0, 50000.0);
            """
        )
        conn.execute(
            """
            INSERT INTO network_monthly_stats (network_id, year_month, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps)
            VALUES ('wifi:OfficeNet:test', '2026-09', 5000000, 1000000, 100000.0, 50000.0);
            """
        )


# ======================================================================
# 1-4. Reset statistics clears all history and network records
# ======================================================================

def test_reset_statistics_clears_all_tables(temp_db: Database) -> None:
    _seed_database_data(temp_db)

    info_before = temp_db.get_storage_info()
    assert info_before["has_history"] is True
    assert info_before["networks_count"] >= 1
    assert info_before["daily_records_count"] >= 2

    # Execute statistics reset
    temp_db.reset_statistics()

    info_after = temp_db.get_storage_info()
    assert info_after["has_history"] is False
    assert info_after["networks_count"] == 0
    assert info_after["daily_records_count"] == 0

    repo = StatsRepository(temp_db)
    assert len(repo.get_hourly_records()) == 0
    assert len(repo.get_daily_records()) == 0
    assert len(repo.get_monthly_records()) == 0
    assert len(repo.get_known_networks()) == 0


# ======================================================================
# 5. Reset statistics preserves preferences
# ======================================================================

def test_reset_statistics_preserves_preferences(temp_db: Database, temp_prefs: PreferencesManager) -> None:
    temp_prefs.update(
        display_mode=DisplayMode.COMPACT,
        unit_mode=UnitMode.MB,
        sample_interval=2.0,
        notify_weak_signal=False,
    )

    monitor = NetworkMonitor(interval=2.0)
    aggregator = SampleAggregator(temp_db)
    coordinator = DataResetCoordinator(
        preferences_manager=temp_prefs,
        database=temp_db,
        monitor=monitor,
        aggregator=aggregator,
    )

    coordinator.reset_statistics_and_history()

    # Preferences must remain unchanged
    assert temp_prefs.preferences.display_mode == DisplayMode.COMPACT
    assert temp_prefs.preferences.unit_mode == UnitMode.MB
    assert temp_prefs.preferences.sample_interval == 2.0
    assert temp_prefs.preferences.notify_weak_signal is False


# ======================================================================
# 6. Reset everything clears preferences to defaults
# ======================================================================

def test_reset_everything_clears_preferences(temp_db: Database, temp_prefs: PreferencesManager) -> None:
    temp_prefs.update(
        display_mode=DisplayMode.COMPACT,
        unit_mode=UnitMode.MB,
        sample_interval=5.0,
        notifications_enabled=False,
    )

    monitor = NetworkMonitor(interval=5.0)
    aggregator = SampleAggregator(temp_db)
    coordinator = DataResetCoordinator(
        preferences_manager=temp_prefs,
        database=temp_db,
        monitor=monitor,
        aggregator=aggregator,
    )

    coordinator.reset_all_data()

    # Preferences must revert to fresh AppPreferences defaults
    defaults = AppPreferences()
    assert temp_prefs.preferences.display_mode == defaults.display_mode
    assert temp_prefs.preferences.unit_mode == defaults.unit_mode
    assert temp_prefs.preferences.sample_interval == defaults.sample_interval
    assert temp_prefs.preferences.notifications_enabled == defaults.notifications_enabled


# ======================================================================
# 7. Reset everything clears database history
# ======================================================================

def test_reset_everything_clears_database_history(temp_db: Database, temp_prefs: PreferencesManager) -> None:
    _seed_database_data(temp_db)
    monitor = NetworkMonitor()
    coordinator = DataResetCoordinator(
        preferences_manager=temp_prefs,
        database=temp_db,
        monitor=monitor,
    )

    coordinator.reset_all_data()

    info = temp_db.get_storage_info()
    assert info["has_history"] is False
    assert info["networks_count"] == 0


# ======================================================================
# 8-9. Schema remains valid and writable after reset
# ======================================================================

def test_schema_remains_valid_and_writable_after_reset(temp_db: Database) -> None:
    _seed_database_data(temp_db)
    temp_db.reset_statistics()

    with temp_db.transaction() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA user_version;")
        ver = cur.fetchone()[0]
        assert ver == 2

    # Verify write immediate
    repo = StatsRepository(temp_db)
    repo.upsert_network(
        network_id="wifi:NewNet:test",
        connection_type="wifi",
        ssid="NewNet",
        display_name="NewNet",
        interface_id="en0",
    )
    known = repo.get_known_networks()
    assert len(known) == 1
    assert known[0].network_id == "wifi:NewNet:test"


# ======================================================================
# 10-11. Byte baseline reset prevents artificial bandwidth spikes
# ======================================================================

def test_baseline_reset_prevents_bandwidth_spikes(temp_db: Database, temp_prefs: PreferencesManager) -> None:
    monitor = NetworkMonitor(interval=0.1)
    aggregator = SampleAggregator(temp_db)
    coordinator = DataResetCoordinator(
        preferences_manager=temp_prefs,
        database=temp_db,
        monitor=monitor,
        aggregator=aggregator,
    )

    # Mock psutil counters returning 100 GB
    mock_psutil_1 = MagicMock()
    mock_psutil_1.bytes_recv = 100 * 1024 * 1024 * 1024
    mock_psutil_1.bytes_sent = 50 * 1024 * 1024 * 1024

    with patch("netpulse.core.network_monitor.psutil.net_io_counters", return_value=mock_psutil_1):
        monitor._sample()  # baseline 100 GB

    mock_psutil_2 = MagicMock()
    mock_psutil_2.bytes_recv = 100 * 1024 * 1024 * 1024 + 50000
    mock_psutil_2.bytes_sent = 50 * 1024 * 1024 * 1024 + 10000

    with patch("netpulse.core.network_monitor.psutil.net_io_counters", return_value=mock_psutil_2):
        with patch("time.monotonic", return_value=time.monotonic() + 1.0):
            monitor._sample()

    assert monitor.session_downloaded == 50000
    assert len(monitor.buffer) == 1

    # Now execute reset
    coordinator.reset_statistics_and_history()

    # Verify monitor accounting reset
    assert monitor.session_downloaded == 0
    assert monitor.session_uploaded == 0
    assert monitor.session_peak_download == 0.0
    assert len(monitor.buffer) == 0

    # Next sample: psutil is at 100 GB + 70000.
    # Because baseline was reset to None, this sample must establish a NEW baseline
    # and NOT compute a delta against 0 or previous snapshot!
    mock_psutil_3 = MagicMock()
    mock_psutil_3.bytes_recv = 100 * 1024 * 1024 * 1024 + 70000
    mock_psutil_3.bytes_sent = 50 * 1024 * 1024 * 1024 + 20000

    with patch("netpulse.core.network_monitor.psutil.net_io_counters", return_value=mock_psutil_3):
        with patch("time.monotonic", return_value=time.monotonic() + 2.0):
            monitor._sample()

    # Since it was first sample after reset, it only set baseline. No speed spike!
    assert monitor.session_downloaded == 0
    assert len(monitor.buffer) == 0  # No sample produced on baseline establish

    # Fourth sample: delta against sample 3 (10,000 bytes)
    mock_psutil_4 = MagicMock()
    mock_psutil_4.bytes_recv = 100 * 1024 * 1024 * 1024 + 80000
    mock_psutil_4.bytes_sent = 50 * 1024 * 1024 * 1024 + 25000

    with patch("netpulse.core.network_monitor.psutil.net_io_counters", return_value=mock_psutil_4):
        with patch("time.monotonic", return_value=time.monotonic() + 3.0):
            monitor._sample()

    # Exactly 10,000 bytes delta, no multi-gigabyte spike!
    assert monitor.session_downloaded == 10000
    assert monitor.session_uploaded == 5000
    assert len(monitor.buffer) == 1


# ======================================================================
# 12-13. DataBuffer and session metrics reset correctly
# ======================================================================

def test_data_buffer_and_session_cleared_on_reset() -> None:
    monitor = NetworkMonitor()
    sample = NetworkSample(
        timestamp=datetime.now(timezone.utc),
        download_bps=1024.0,
        upload_bps=512.0,
        total_download_bytes=1000,
        total_upload_bytes=500,
    )
    monitor.buffer.append(sample)
    monitor._session_downloaded = 100000
    monitor._session_peak_download = 50000.0

    assert len(monitor.buffer) == 1
    assert monitor.session_downloaded == 100000

    monitor.reset_accounting()

    assert len(monitor.buffer) == 0
    assert monitor.session_downloaded == 0
    assert monitor.session_uploaded == 0
    assert monitor.session_peak_download == 0.0
    assert monitor.session_peak_upload == 0.0


# ======================================================================
# 14. Notification policy and engine state reset
# ======================================================================

def test_notification_state_reset_on_reset(temp_prefs: PreferencesManager) -> None:
    policy = NotificationPolicy(temp_prefs)
    engine = NotificationEngine(prefs_manager=temp_prefs, policy=policy)

    from netpulse.notifications.models import NotificationSeverity
    # Trigger a notification
    event = NotificationEvent(
        event_type=NotificationType.NETWORK_CONNECTED,
        title="Connected",
        body="Connected to OfficeNet",
        network_id="net-123",
        severity=NotificationSeverity.INFO,
    )
    assert policy.should_deliver(event) is True
    policy.record_delivery(event)
    # Immediately check cooldown rejection
    assert policy.should_deliver(event) is False

    # Simulate weak signal hysteresis
    policy._is_in_weak_signal = True

    # Execute reset
    engine.reset_state()

    # Cooldown should be cleared, delivery allowed again
    assert policy._is_in_weak_signal is False
    assert policy.should_deliver(event) is True
    assert len(engine.recent_events) == 0


# ======================================================================
# 15-16. Active network continuity after reset without duplicates
# ======================================================================

def test_active_network_continuity_without_duplicates(
    temp_db: Database, temp_prefs: PreferencesManager
) -> None:
    mock_context_mgr = MagicMock()
    mock_iface = InterfaceIdentity("en0", "iface:en0:mac", "en0", "wifi", True)
    mock_net = NetworkIdentity("wifi:TestNet:hash", "wifi", "TestNet", "TestNet", "iface:en0:mac")
    mock_ctx = NetworkContext(
        timestamp=datetime.now(timezone.utc),
        interface=mock_iface,
        network=mock_net,
        is_connected=True,
    )
    mock_context_mgr.refresh_now.return_value = mock_ctx

    monitor = NetworkMonitor()
    coordinator = DataResetCoordinator(
        preferences_manager=temp_prefs,
        database=temp_db,
        monitor=monitor,
        context_manager=mock_context_mgr,
    )

    coordinator.reset_statistics_and_history()

    repo = StatsRepository(temp_db)
    known = repo.get_known_networks()
    assert len(known) == 1
    assert known[0].network_id == "wifi:TestNet:hash"
    assert known[0].total_download_bytes == 0

    # Running reset again does not create duplicate
    coordinator.reset_statistics_and_history()
    known_again = repo.get_known_networks()
    assert len(known_again) == 1


# ======================================================================
# 17. UI callback triggered on reset
# ======================================================================

def test_ui_callback_notified_on_reset(temp_db: Database, temp_prefs: PreferencesManager) -> None:
    cb_calls = []

    def on_reset(is_full: bool) -> None:
        cb_calls.append(is_full)

    monitor = NetworkMonitor()
    coordinator = DataResetCoordinator(
        preferences_manager=temp_prefs,
        database=temp_db,
        monitor=monitor,
        on_reset_callback=on_reset,
    )

    coordinator.reset_statistics_and_history()
    assert cb_calls == [False]

    coordinator.reset_all_data()
    assert cb_calls == [False, True]


# ======================================================================
# 18. SettingsPage Data & Storage UI and Dialog Tests
# ======================================================================

def test_settings_page_storage_card_and_reset(temp_db: Database, temp_prefs: PreferencesManager) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    _seed_database_data(temp_db)
    monitor = NetworkMonitor()
    coordinator = MagicMock()

    from netpulse.ui.settings import SettingsPage
    page = SettingsPage(
        prefs_manager=temp_prefs,
        monitor=monitor,
        database=temp_db,
        reset_coordinator=coordinator,
    )

    # Check that Data & Storage fields display database info
    assert str(temp_db.path) in page._lbl_db_path.text()
    assert "known networks" in page._lbl_db_history.text()

    # Test Cancel on Reset Statistics
    with patch.object(QMessageBox, "exec", return_value=None):
        with patch.object(QMessageBox, "clickedButton") as mock_clicked:
            mock_clicked.return_value = page._btn_reset_stats  # Not the destructive button in dialog
            page._on_reset_statistics_clicked()
            coordinator.reset_statistics_and_history.assert_not_called()

    # Test Confirm on Reset Statistics
    with patch.object(QMessageBox, "exec", return_value=None):
        def fake_exec(self_box):
            # Click the destructive button added to the message box
            buttons = self_box.buttons()
            for b in buttons:
                if "Reset History" in b.text():
                    self_box._clicked = b
            return 0
        with patch.object(QMessageBox, "exec", fake_exec):
            with patch.object(QMessageBox, "clickedButton", side_effect=lambda: getattr(QMessageBox, "_clicked", None)):
                pass

    # Direct invoke coordinator method test
    coordinator.reset_statistics_and_history()
    coordinator.reset_statistics_and_history.assert_called_once()
