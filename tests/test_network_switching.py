"""Tests for network transition detection and byte isolation during network switching."""

from datetime import datetime, timezone
import pytest

from netpulse.core.network_sample import NetworkSample
from netpulse.storage.aggregator import SampleAggregator
from netpulse.storage.database import Database
from netpulse.storage.repository import StatsRepository


@pytest.fixture
def memory_db() -> Database:
    return Database(":memory:")


def test_wifi_a_to_wifi_b_transition_zero_contamination(memory_db: Database) -> None:
    """Traffic from Network A must never contaminate Network B when switching networks."""
    aggregator = SampleAggregator(memory_db, flush_interval=3600.0)
    repo = StatsRepository(memory_db)

    # 1. Network A sends traffic
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 5, tzinfo=timezone.utc)

    # Baseline on Network A
    aggregator.on_sample(
        NetworkSample(
            timestamp=t0,
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=1000,
            total_upload_bytes=500,
            interface="en0",
            network_id="wifi:home",
        )
    )

    # 5 seconds of traffic on Network A (delta: +1000 DL, +500 UL)
    aggregator.on_sample(
        NetworkSample(
            timestamp=t1,
            download_bps=200.0,
            upload_bps=100.0,
            total_download_bytes=2000,
            total_upload_bytes=1000,
            interface="en0",
            network_id="wifi:home",
        )
    )

    # Verify staged bytes
    assert aggregator.staged_download_bytes == 1000
    assert aggregator.staged_upload_bytes == 500

    # 2. Switch to Network B at t2
    # When switching networks, cumulative counters may reset or change completely
    t2 = datetime(2026, 9, 18, 10, 0, 10, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 18, 10, 0, 15, tzinfo=timezone.utc)

    # Incoming sample on Network B immediately causes Network A's staged data to be flushed
    # and establishes a fresh baseline on Network B!
    aggregator.on_sample(
        NetworkSample(
            timestamp=t2,
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=50000,  # Network B new interface baseline
            total_upload_bytes=20000,
            interface="en0",
            network_id="wifi:office",
        )
    )

    # Verify Network A was flushed to database immediately upon switch
    home_records = repo.get_network_hourly_records("wifi:home")
    assert len(home_records) == 1
    assert home_records[0].download_bytes == 1000
    assert home_records[0].upload_bytes == 500

    # 3. Traffic continues on Network B (delta: +2500 DL, +1000 UL)
    aggregator.on_sample(
        NetworkSample(
            timestamp=t3,
            download_bps=500.0,
            upload_bps=200.0,
            total_download_bytes=52500,
            total_upload_bytes=21000,
            interface="en0",
            network_id="wifi:office",
        )
    )

    aggregator.flush()

    # Verify Network B received exactly its own delta, zero contamination from Network A!
    office_records = repo.get_network_hourly_records("wifi:office")
    assert len(office_records) == 1
    assert office_records[0].download_bytes == 2500
    assert office_records[0].upload_bytes == 1000

    # Network A remains untouched
    home_records_after = repo.get_network_hourly_records("wifi:home")
    assert home_records_after[0].download_bytes == 1000


def test_wifi_to_ethernet_transition(memory_db: Database) -> None:
    """Switching from Wi-Fi (en0) to Ethernet (en1) isolates accounting across interfaces."""
    aggregator = SampleAggregator(memory_db, flush_interval=3600.0)
    repo = StatsRepository(memory_db)

    t0 = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 12, 0, 5, tzinfo=timezone.utc)

    # Wi-Fi sample
    aggregator.on_sample(
        NetworkSample(
            timestamp=t0,
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=10000,
            total_upload_bytes=5000,
            interface="en0",
            network_id="wifi:home",
        )
    )
    aggregator.on_sample(
        NetworkSample(
            timestamp=t1,
            download_bps=1000.0,
            upload_bps=500.0,
            total_download_bytes=15000,
            total_upload_bytes=7500,
            interface="en0",
            network_id="wifi:home",
        )
    )

    # Plug in Ethernet (en1) -> network switch
    t2 = datetime(2026, 9, 18, 12, 0, 10, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 18, 12, 0, 15, tzinfo=timezone.utc)

    aggregator.on_sample(
        NetworkSample(
            timestamp=t2,
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=100,  # Ethernet starting counters
            total_upload_bytes=50,
            interface="en1",
            network_id="eth:iface:en1",
        )
    )
    aggregator.on_sample(
        NetworkSample(
            timestamp=t3,
            download_bps=2000.0,
            upload_bps=1000.0,
            total_download_bytes=10100,
            total_upload_bytes=5050,
            interface="en1",
            network_id="eth:iface:en1",
        )
    )

    aggregator.flush()

    home_stats = repo.get_network_hourly_records("wifi:home")
    eth_stats = repo.get_network_hourly_records("eth:iface:en1")

    assert home_stats[0].download_bytes == 5000
    assert home_stats[0].upload_bytes == 2500

    assert eth_stats[0].download_bytes == 10000
    assert eth_stats[0].upload_bytes == 5000
