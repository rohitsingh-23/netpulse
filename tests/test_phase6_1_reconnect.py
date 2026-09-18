"""Tests validating network identity persistence, reconnect behavior, and fallback identity."""

from datetime import datetime, timezone
import pytest

from netpulse.core.network_identity import NetworkIdentity
from netpulse.core.network_sample import NetworkSample
from netpulse.storage.aggregator import SampleAggregator
from netpulse.storage.database import Database
from netpulse.storage.repository import StatsRepository


@pytest.fixture
def memory_db() -> Database:
    return Database(":memory:")


def test_reconnect_same_ssid_identity(memory_db: Database) -> None:
    """Verify that reconnecting to the same SSID resolves to the same network_id."""
    id1 = NetworkIdentity.create_wifi(ssid="Rohit-Home", interface_id="iface:en0")
    id2 = NetworkIdentity.create_wifi(ssid="Rohit-Home", interface_id="iface:en0")
    # Even if interface changes, SSID grouping takes precedence for Wi-Fi logically (though our create_wifi uses it)
    id3 = NetworkIdentity.create_wifi(ssid="Rohit-Home", interface_id="iface:en1")

    assert id1.network_id == "wifi:rohit-home"
    assert id2.network_id == "wifi:rohit-home"
    assert id3.network_id == "wifi:rohit-home"
    assert id1.network_id == id2.network_id == id3.network_id


def test_fallback_identity_is_safe() -> None:
    """Verify the fallback identity behavior when SSID permission is restricted.

    This explicitly documents that if macOS restricts SSID access, we fallback
    to interface-level identity. This means different hidden Wi-Fi networks on
    the same interface will be grouped as 'wifi-unpermitted:iface:en0'.
    We do NOT attempt to bypass this with hidden BSSIDs.
    """
    id_restricted = NetworkIdentity.create_wifi(
        ssid=None, interface_id="iface:en0", permission_restricted=True
    )
    assert id_restricted.network_id == "wifi-unpermitted:iface:en0"
    assert id_restricted.ssid is None
    assert id_restricted.display_name == "Wi-Fi Network"


def test_reconnect_accumulates_under_same_record_and_resets_baseline(memory_db: Database) -> None:
    """Verify that disconnecting and reconnecting to the same network:
    1. Does not create duplicate network entries.
    2. Accumulates usage under the same record.
    3. Resets the byte-counter baseline correctly.
    """
    aggregator = SampleAggregator(memory_db, flush_interval=3600.0)
    repo = StatsRepository(memory_db)

    # 1. Wi-Fi A connected, baseline established
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 5, tzinfo=timezone.utc)

    aggregator.on_sample(
        NetworkSample(
            timestamp=t0,
            download_bps=0.0, upload_bps=0.0,
            total_download_bytes=1000, total_upload_bytes=500,
            interface="en0", network_id="wifi:network-a"
        )
    )
    # 5 seconds of traffic (100 MB down, 50 MB up)
    aggregator.on_sample(
        NetworkSample(
            timestamp=t1,
            download_bps=20000000.0, upload_bps=10000000.0,
            total_download_bytes=1000 + 100_000_000, total_upload_bytes=500 + 50_000_000,
            interface="en0", network_id="wifi:network-a"
        )
    )

    # Disconnect happens (psutil counters keep running, maybe for local traffic, or stay static)
    # We flush what we have
    aggregator.flush()

    # Verify we have 100 MB for network-a
    records = repo.get_network_hourly_records("wifi:network-a")
    assert len(records) == 1
    assert records[0].download_bytes == 100_000_000

    networks = repo.get_known_networks()
    # __SYSTEM_LEGACY__ + wifi:network-a
    assert len(networks) == 2

    # 2. Reconnect to Wi-Fi A (new baseline required because psutil counters may be completely different or huge)
    t2 = datetime(2026, 9, 18, 10, 5, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 18, 10, 5, 5, tzinfo=timezone.utc)

    aggregator.on_sample(
        NetworkSample(
            timestamp=t2,
            download_bps=0.0, upload_bps=0.0,
            total_download_bytes=500_000_000, total_upload_bytes=200_000_000,
            interface="en0", network_id="wifi:network-a"
        )
    )

    # 5 seconds of traffic (50 MB down, 25 MB up)
    aggregator.on_sample(
        NetworkSample(
            timestamp=t3,
            download_bps=10000000.0, upload_bps=5000000.0,
            total_download_bytes=500_000_000 + 50_000_000, total_upload_bytes=200_000_000 + 25_000_000,
            interface="en0", network_id="wifi:network-a"
        )
    )

    aggregator.flush()

    # 3. Verify accumulation and baseline reset
    records = repo.get_network_hourly_records("wifi:network-a")
    assert len(records) == 1
    # Total must be 150 MB (100 MB from first session + 50 MB from second)
    assert records[0].download_bytes == 150_000_000
    assert records[0].upload_bytes == 75_000_000

    networks = repo.get_known_networks()
    assert len(networks) == 2  # __SYSTEM_LEGACY__ + wifi:network-a (no duplicate)


def test_wifi_a_to_b_to_a_switching(memory_db: Database) -> None:
    """Verify Wi-Fi A -> Wi-Fi B -> Wi-Fi A results in zero cross-network contamination."""
    aggregator = SampleAggregator(memory_db, flush_interval=3600.0)
    repo = StatsRepository(memory_db)

    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 5, tzinfo=timezone.utc)

    # Wi-Fi A Baseline & Traffic (10 MB down)
    aggregator.on_sample(NetworkSample(t0, 0, 0, 0, 0, "en0", "wifi:a"))
    aggregator.on_sample(NetworkSample(t1, 0, 0, 10_000_000, 0, "en0", "wifi:a"))

    # Switch to Wi-Fi B at t2
    t2 = datetime(2026, 9, 18, 10, 1, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 18, 10, 1, 5, tzinfo=timezone.utc)

    # Wi-Fi B Baseline & Traffic (20 MB down)
    aggregator.on_sample(NetworkSample(t2, 0, 0, 10_000_000, 0, "en0", "wifi:b"))
    aggregator.on_sample(NetworkSample(t3, 0, 0, 30_000_000, 0, "en0", "wifi:b"))

    # Switch back to Wi-Fi A at t4
    t4 = datetime(2026, 9, 18, 10, 2, 0, tzinfo=timezone.utc)
    t5 = datetime(2026, 9, 18, 10, 2, 5, tzinfo=timezone.utc)

    # Wi-Fi A Baseline & Traffic (15 MB down)
    aggregator.on_sample(NetworkSample(t4, 0, 0, 50_000_000, 0, "en0", "wifi:a"))
    aggregator.on_sample(NetworkSample(t5, 0, 0, 65_000_000, 0, "en0", "wifi:a"))

    aggregator.flush()

    # Verify Wi-Fi A has 25 MB (10 + 15)
    records_a = repo.get_network_hourly_records("wifi:a")
    assert records_a[0].download_bytes == 25_000_000

    # Verify Wi-Fi B has 20 MB
    records_b = repo.get_network_hourly_records("wifi:b")
    assert records_b[0].download_bytes == 20_000_000


def test_app_restart_preserves_identity(tmp_path) -> None:
    """Verify that restarting the application preserves identity and accumulates usage."""
    db_path = tmp_path / "test.db"

    # Session 1
    db1 = Database(str(db_path))
    aggregator1 = SampleAggregator(db1, flush_interval=0.0)  # Flush immediately

    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 5, tzinfo=timezone.utc)

    aggregator1.on_sample(NetworkSample(t0, 0, 0, 0, 0, "en0", "wifi:my-network"))
    aggregator1.on_sample(NetworkSample(t1, 0, 0, 5000, 0, "en0", "wifi:my-network"))

    # Close app
    db1.close()

    # Session 2
    db2 = Database(str(db_path))
    repo2 = StatsRepository(db2)
    aggregator2 = SampleAggregator(db2, flush_interval=0.0)

    t2 = datetime(2026, 9, 18, 11, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 18, 11, 0, 5, tzinfo=timezone.utc)

    # New baseline on Session 2
    aggregator2.on_sample(NetworkSample(t2, 0, 0, 100000, 0, "en0", "wifi:my-network"))
    aggregator2.on_sample(NetworkSample(t3, 0, 0, 103000, 0, "en0", "wifi:my-network"))

    db2.close()

    # Verify aggregation from both sessions
    db3 = Database(str(db_path))
    repo3 = StatsRepository(db3)

    records = repo3.get_network_hourly_records("wifi:my-network", limit=24)
    # Total should be 5000 + 3000 = 8000
    total_dl = sum(r.download_bytes for r in records)
    assert total_dl == 8000

    networks = repo3.get_known_networks()
    assert len(networks) == 2  # __SYSTEM_LEGACY__ + wifi:my-network

    db3.close()
