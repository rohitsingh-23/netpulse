"""Tests for StatsRepository network queries and mutations."""

import pytest

from netpulse.storage.database import Database
from netpulse.storage.repository import StatsRepository


@pytest.fixture
def repo() -> StatsRepository:
    db = Database(":memory:")
    return StatsRepository(db)


def test_upsert_and_query_known_networks(repo: StatsRepository) -> None:
    repo.upsert_network(
        network_id="wifi:home",
        connection_type="wifi",
        ssid="Rohit-Home",
        display_name="Rohit-Home",
        interface_id="iface:en0",
        bssid_hash="abc12345",
    )

    networks = repo.get_known_networks()
    # At least __SYSTEM_LEGACY__ and wifi:home
    net_ids = [n.network_id for n in networks]
    assert "wifi:home" in net_ids
    home_net = next(n for n in networks if n.network_id == "wifi:home")
    assert home_net.display_name == "Rohit-Home"
    assert home_net.connection_type == "wifi"
    assert home_net.ssid == "Rohit-Home"
    assert home_net.interface_id == "iface:en0"


def test_network_hourly_and_daily_records(repo: StatsRepository) -> None:
    repo.upsert_network(
        network_id="eth:en1",
        connection_type="ethernet",
        ssid=None,
        display_name="Ethernet",
        interface_id="iface:en1",
    )

    with repo._db.transaction() as conn:
        conn.executescript("""
            INSERT INTO network_hourly_stats VALUES ('eth:en1', '2026-09-18T08:00:00Z', 100, 50, 10.0, 5.0);
            INSERT INTO network_hourly_stats VALUES ('eth:en1', '2026-09-18T09:00:00Z', 200, 100, 20.0, 10.0);
            INSERT INTO network_daily_stats VALUES ('eth:en1', '2026-09-18', 300, 150, 20.0, 10.0);
        """)

    hourly = repo.get_network_hourly_records("eth:en1", limit=10)
    assert len(hourly) == 2
    assert hourly[0].hour_timestamp == "2026-09-18T08:00:00Z"
    assert hourly[1].hour_timestamp == "2026-09-18T09:00:00Z"

    daily = repo.get_network_daily_records("eth:en1", limit=10)
    assert len(daily) == 1
    assert daily[0].download_bytes == 300
    assert daily[0].upload_bytes == 150
