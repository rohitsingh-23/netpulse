"""Unit tests for SQLite persistence, SampleAggregator, and StatsRepository."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
import pytest

from netpulse.core.network_sample import NetworkSample
from netpulse.storage.aggregator import SampleAggregator
from netpulse.storage.database import Database
from netpulse.storage.repository import StatsRepository


@pytest.fixture
def memory_db() -> Database:
    """In-memory SQLite database instance for isolated testing."""
    db = Database(":memory:")
    yield db
    db.close()


@pytest.fixture
def temp_disk_db(tmp_path: Path) -> Database:
    """Temporary on-disk SQLite database instance."""
    db_file = tmp_path / "test_netpulse.db"
    db = Database(db_file)
    yield db
    db.close()


def test_database_schema_initialization(memory_db: Database) -> None:
    """Tables and indexes are properly created."""
    with memory_db.transaction() as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        assert "hourly_stats" in tables
        assert "daily_stats" in tables
        assert "monthly_stats" in tables


def test_aggregator_accumulates_and_flushes(memory_db: Database) -> None:
    """Aggregator computes byte deltas and updates hourly, daily, monthly records."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0)
    repo = StatsRepository(memory_db)

    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 18, 10, 0, 2, tzinfo=timezone.utc)

    s0 = NetworkSample(
        timestamp=t0,
        download_bps=0.0,
        upload_bps=0.0,
        total_download_bytes=1000,
        total_upload_bytes=500,
    )
    s1 = NetworkSample(
        timestamp=t1,
        download_bps=200.0,
        upload_bps=100.0,
        total_download_bytes=1200,  # +200 bytes
        total_upload_bytes=600,   # +100 bytes
    )
    s2 = NetworkSample(
        timestamp=t2,
        download_bps=300.0,
        upload_bps=150.0,
        total_download_bytes=1500,  # +300 bytes
        total_upload_bytes=750,   # +150 bytes
    )

    aggregator.on_sample(s0)
    aggregator.on_sample(s1)
    aggregator.on_sample(s2)

    assert aggregator.staged_download_bytes == 500  # 200 + 300
    assert aggregator.staged_upload_bytes == 250    # 100 + 150

    # Flush staged metrics to database
    aggregator.flush()
    assert aggregator.staged_download_bytes == 0
    assert aggregator.staged_upload_bytes == 0

    # Check hourly stats
    hourly = repo.get_hourly_records(limit=10)
    assert len(hourly) == 1
    assert hourly[0].hour_timestamp == "2026-09-18T10:00:00Z"
    assert hourly[0].download_bytes == 500
    assert hourly[0].upload_bytes == 250
    assert hourly[0].peak_download_bps == 300.0
    assert hourly[0].peak_upload_bps == 150.0

    # Check daily stats
    daily = repo.get_daily_records(limit=10)
    assert len(daily) == 1
    assert daily[0].date == "2026-09-18"
    assert daily[0].download_bytes == 500
    assert daily[0].upload_bytes == 250

    # Check monthly stats
    monthly = repo.get_monthly_records(limit=10)
    assert len(monthly) == 1
    assert monthly[0].year_month == "2026-09"
    assert monthly[0].download_bytes == 500
    assert monthly[0].upload_bytes == 250


def test_boundary_crossing_proportional_split(memory_db: Database) -> None:
    """Traffic crossing an hour boundary is split proportionally by elapsed time."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0, max_measurement_gap=30.0)
    repo = StatsRepository(memory_db)

    # 10:59:50 -> 11:00:10 (20s duration: 10s in 10:00 hour, 10s in 11:00 hour)
    t0 = datetime(2026, 9, 18, 10, 59, 50, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 11, 0, 10, tzinfo=timezone.utc)

    total_delta = 100_000_000  # 100 MB

    aggregator.on_sample(NetworkSample(t0, 0.0, 0.0, 1_000_000, 1_000_000))
    aggregator.on_sample(NetworkSample(t1, 5_000_000.0, 5_000_000.0, 1_000_000 + total_delta, 1_000_000 + total_delta))
    aggregator.flush()

    hourly = repo.get_hourly_records(limit=10)
    assert len(hourly) == 2

    # Hour 10:00:00Z should have exactly 50% (50 MB)
    assert hourly[0].hour_timestamp == "2026-09-18T10:00:00Z"
    assert hourly[0].download_bytes == 50_000_000
    assert hourly[0].upload_bytes == 50_000_000

    # Hour 11:00:00Z should have exactly 50% (50 MB)
    assert hourly[1].hour_timestamp == "2026-09-18T11:00:00Z"
    assert hourly[1].download_bytes == 50_000_000
    assert hourly[1].upload_bytes == 50_000_000

    # Total preserved without byte loss
    assert hourly[0].download_bytes + hourly[1].download_bytes == total_delta


def test_midnight_boundary_crossing(memory_db: Database) -> None:
    """Traffic crossing midnight is split across the two consecutive days."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0, max_measurement_gap=30.0)
    repo = StatsRepository(memory_db)

    # 23:59:50 (Sept 18) -> 00:00:10 (Sept 19)
    t0 = datetime(2026, 9, 18, 23, 59, 50, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 19, 0, 0, 10, tzinfo=timezone.utc)

    total_delta = 100_000_000

    aggregator.on_sample(NetworkSample(t0, 0.0, 0.0, 10_000, 10_000))
    aggregator.on_sample(NetworkSample(t1, 5_000_000.0, 5_000_000.0, 10_000 + total_delta, 10_000 + total_delta))
    aggregator.flush()

    daily = repo.get_daily_records(limit=10)
    assert len(daily) == 2
    assert daily[0].date == "2026-09-18"
    assert daily[0].download_bytes == 50_000_000

    assert daily[1].date == "2026-09-19"
    assert daily[1].download_bytes == 50_000_000
    assert daily[0].download_bytes + daily[1].download_bytes == total_delta


def test_month_boundary_crossing(memory_db: Database) -> None:
    """Traffic crossing month boundary is split across the two consecutive months."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0, max_measurement_gap=30.0)
    repo = StatsRepository(memory_db)

    # Jan 31 23:59:50 -> Feb 1 00:00:10
    t0 = datetime(2026, 1, 31, 23, 59, 50, tzinfo=timezone.utc)
    t1 = datetime(2026, 2, 1, 0, 0, 10, tzinfo=timezone.utc)

    total_delta = 200_000_000

    aggregator.on_sample(NetworkSample(t0, 0.0, 0.0, 10_000, 10_000))
    aggregator.on_sample(NetworkSample(t1, 10_000_000.0, 10_000_000.0, 10_000 + total_delta, 10_000 + total_delta))
    aggregator.flush()

    monthly = repo.get_monthly_records(limit=10)
    assert len(monthly) == 2
    assert monthly[0].year_month == "2026-01"
    assert monthly[0].download_bytes == 100_000_000

    assert monthly[1].year_month == "2026-02"
    assert monthly[1].download_bytes == 100_000_000
    assert monthly[0].download_bytes + monthly[1].download_bytes == total_delta


def test_variable_sampling_intervals_produce_identical_totals(memory_db: Database) -> None:
    """Different sampling frequencies for identical traffic produce identical totals."""
    # Scenario: 100 MB transferred from 10:00:00 to 10:00:10 (counter 0 -> 100_000_000)
    start_t = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    total_bytes = 100_000_000

    # 1. Sampled every 1 second (10 steps of 10 MB)
    db1 = Database(":memory:")
    agg1 = SampleAggregator(db1, flush_interval=100.0)
    for i in range(11):
        t = start_t + timedelta(seconds=i)
        bytes_val = int(total_bytes * (i / 10))
        agg1.on_sample(NetworkSample(t, 10_000_000.0, 10_000_000.0, bytes_val, bytes_val))
    agg1.flush()
    total1 = StatsRepository(db1).get_hourly_records()[0].download_bytes
    db1.close()

    # 2. Sampled every 5 seconds (2 steps of 50 MB)
    db2 = Database(":memory:")
    agg2 = SampleAggregator(db2, flush_interval=100.0)
    for i in [0, 5, 10]:
        t = start_t + timedelta(seconds=i)
        bytes_val = int(total_bytes * (i / 10))
        agg2.on_sample(NetworkSample(t, 10_000_000.0, 10_000_000.0, bytes_val, bytes_val))
    agg2.flush()
    total2 = StatsRepository(db2).get_hourly_records()[0].download_bytes
    db2.close()

    # 3. Sampled every 0.5 seconds (20 steps of 5 MB)
    db3 = Database(":memory:")
    agg3 = SampleAggregator(db3, flush_interval=100.0)
    for step in range(21):
        sec = step * 0.5
        t = start_t + timedelta(seconds=sec)
        bytes_val = int(total_bytes * (sec / 10))
        agg3.on_sample(NetworkSample(t, 10_000_000.0, 10_000_000.0, bytes_val, bytes_val))
    agg3.flush()
    total3 = StatsRepository(db3).get_hourly_records()[0].download_bytes
    db3.close()

    # 4. Irregular sampling
    db4 = Database(":memory:")
    agg4 = SampleAggregator(db4, flush_interval=100.0)
    for sec in [0.0, 1.2, 2.7, 5.1, 8.3, 10.0]:
        t = start_t + timedelta(seconds=sec)
        bytes_val = int(total_bytes * (sec / 10))
        agg4.on_sample(NetworkSample(t, 10_000_000.0, 10_000_000.0, bytes_val, bytes_val))
    agg4.flush()
    total4 = StatsRepository(db4).get_hourly_records()[0].download_bytes
    db4.close()

    assert total1 == total_bytes
    assert total2 == total_bytes
    assert total3 == total_bytes
    assert total4 == total_bytes


def test_sleep_wake_large_gap_rejected(memory_db: Database) -> None:
    """Large gaps (e.g. system sleep for 2.5 hours) do not fabricate traffic."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0, max_measurement_gap=10.0)
    repo = StatsRepository(memory_db)

    t0 = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 12, 1, 0, tzinfo=timezone.utc)
    # 2.5 hours sleep until 14:31:00
    t2 = datetime(2026, 9, 18, 14, 31, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 18, 14, 31, 1, tzinfo=timezone.utc)

    # Initial monitoring
    aggregator.on_sample(NetworkSample(t0, 100.0, 50.0, 1000, 500))
    # 1-minute gap > 10.0s gap threshold -> rejected
    aggregator.on_sample(NetworkSample(t1, 100.0, 50.0, 2000, 1000))
    assert aggregator.staged_download_bytes == 0

    # Wakeup after 2.5 hours -> gap > 10.0s -> rejected
    aggregator.on_sample(NetworkSample(t2, 100.0, 50.0, 50_000_000, 25_000_000))
    assert aggregator.staged_download_bytes == 0

    # Normal 1s sample resumes accumulation from t2 baseline
    aggregator.on_sample(NetworkSample(t3, 500.0, 250.0, 50_000_500, 25_000_250))
    assert aggregator.staged_download_bytes == 500
    assert aggregator.staged_upload_bytes == 250

    aggregator.flush()
    records = repo.get_hourly_records(limit=10)
    assert len(records) == 2
    assert records[0].hour_timestamp == "2026-09-18T12:00:00Z"
    assert records[0].download_bytes == 0
    assert records[1].hour_timestamp == "2026-09-18T14:00:00Z"
    assert records[1].download_bytes == 500


def test_counter_reset_both_rx_and_tx(memory_db: Database) -> None:
    """Previous RX/TX > Current RX/TX sets new baseline and does not create negative traffic."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0)
    repo = StatsRepository(memory_db)

    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 18, 10, 0, 2, tzinfo=timezone.utc)

    # Before reset
    aggregator.on_sample(NetworkSample(t0, 1000.0, 500.0, 999_999_999, 888_888_888))

    # Reboot occurs: counters drop to small numbers
    aggregator.on_sample(NetworkSample(t1, 100.0, 50.0, 500, 200))
    assert aggregator.staged_download_bytes == 0
    assert aggregator.staged_upload_bytes == 0

    # Subsequent valid reading resumes normal delta accumulation
    aggregator.on_sample(NetworkSample(t2, 200.0, 100.0, 700, 300))
    assert aggregator.staged_download_bytes == 200
    assert aggregator.staged_upload_bytes == 100

    aggregator.flush()
    hourly = repo.get_hourly_records()
    assert len(hourly) == 1
    assert hourly[0].download_bytes == 200
    assert hourly[0].upload_bytes == 100


def test_zero_traffic(memory_db: Database) -> None:
    """Zero traffic intervals add 0 bytes without error."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0)
    repo = StatsRepository(memory_db)

    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 1, tzinfo=timezone.utc)

    aggregator.on_sample(NetworkSample(t0, 0.0, 0.0, 5000, 2000))
    aggregator.on_sample(NetworkSample(t1, 0.0, 0.0, 5000, 2000))

    assert aggregator.staged_download_bytes == 0
    assert aggregator.staged_upload_bytes == 0

    aggregator.flush()
    hourly = repo.get_hourly_records()
    assert len(hourly) == 1
    assert hourly[0].download_bytes == 0
    assert hourly[0].upload_bytes == 0


def test_daily_monthly_rollup_mathematical_consistency(memory_db: Database) -> None:
    """Sum of hourly stats equals daily stats, and sum of daily equals monthly."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0)
    repo = StatsRepository(memory_db)

    base_t = datetime(2026, 9, 18, 0, 0, 0, tzinfo=timezone.utc)
    counter = 0

    # 4 distinct hours in the day
    for h in range(4):
        t = base_t + timedelta(hours=h, seconds=10)
        counter += 1000
        aggregator.on_sample(NetworkSample(t, 100.0, 50.0, counter, counter))
        counter += 2000
        t_next = t + timedelta(seconds=1)
        aggregator.on_sample(NetworkSample(t_next, 200.0, 100.0, counter, counter))

    aggregator.flush()

    hourly = repo.get_hourly_records(limit=100)
    daily = repo.get_daily_records(limit=10)
    monthly = repo.get_monthly_records(limit=10)

    assert len(hourly) == 4
    assert len(daily) == 1
    assert len(monthly) == 1

    sum_hourly_dl = sum(h.download_bytes for h in hourly)
    sum_hourly_ul = sum(h.upload_bytes for h in hourly)

    assert sum_hourly_dl == daily[0].download_bytes
    assert sum_hourly_ul == daily[0].upload_bytes
    assert daily[0].download_bytes == monthly[0].download_bytes
    assert daily[0].upload_bytes == monthly[0].upload_bytes


def test_repeated_flushes_idempotent(memory_db: Database) -> None:
    """Repeated flushes do not duplicate traffic."""
    aggregator = SampleAggregator(memory_db, flush_interval=100.0)
    repo = StatsRepository(memory_db)

    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 1, tzinfo=timezone.utc)

    aggregator.on_sample(NetworkSample(t0, 0.0, 0.0, 1000, 1000))
    aggregator.on_sample(NetworkSample(t1, 500.0, 500.0, 1500, 1500))

    # First flush
    aggregator.flush()
    assert repo.get_hourly_records()[0].download_bytes == 500

    # Second flush immediately without new samples
    aggregator.flush()
    assert repo.get_hourly_records()[0].download_bytes == 500

    # Third flush after receiving new sample
    t2 = datetime(2026, 9, 18, 10, 0, 2, tzinfo=timezone.utc)
    aggregator.on_sample(NetworkSample(t2, 300.0, 300.0, 1800, 1800))
    aggregator.flush()
    assert repo.get_hourly_records()[0].download_bytes == 800  # 500 + 300


def test_application_restart_semantics(temp_disk_db: Database) -> None:
    """New aggregator instance establishes baseline without fabricating boot total."""
    repo = StatsRepository(temp_disk_db)

    # Session 1: Aggregator A runs
    agg_a = SampleAggregator(temp_disk_db, flush_interval=100.0)
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 1, tzinfo=timezone.utc)
    agg_a.on_sample(NetworkSample(t0, 100.0, 100.0, 1000, 1000))
    agg_a.on_sample(NetworkSample(t1, 200.0, 200.0, 1200, 1200))
    agg_a.flush()
    assert repo.get_hourly_records()[0].download_bytes == 200

    # Simulate application restart: Aggregator B created
    agg_b = SampleAggregator(temp_disk_db, flush_interval=100.0)

    # First sample after restart (cumulative counter is still 1200)
    t2 = datetime(2026, 9, 18, 10, 1, 0, tzinfo=timezone.utc)
    agg_b.on_sample(NetworkSample(t2, 0.0, 0.0, 1200, 1200))
    assert agg_b.staged_download_bytes == 0  # No fabricated delta

    # Second sample after restart
    t3 = datetime(2026, 9, 18, 10, 1, 1, tzinfo=timezone.utc)
    agg_b.on_sample(NetworkSample(t3, 300.0, 300.0, 1500, 1500))
    assert agg_b.staged_download_bytes == 300

    agg_b.flush()
    assert repo.get_hourly_records()[0].download_bytes == 500  # 200 + 300


def test_atomicity_and_rollback_on_failure(memory_db: Database) -> None:
    """Transaction failure rolls back all table updates atomically."""
    # Corrupt daily_stats schema to trigger an error on insert
    with memory_db.transaction() as conn:
        conn.execute("DROP TABLE daily_stats;")
        conn.execute("CREATE TABLE daily_stats (date TEXT PRIMARY KEY, download_bytes TEXT CHECK(0));")

    aggregator = SampleAggregator(memory_db)
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 18, 10, 0, 1, tzinfo=timezone.utc)

    aggregator.on_sample(NetworkSample(t0, 100.0, 100.0, 1000, 1000))
    aggregator.on_sample(NetworkSample(t1, 200.0, 200.0, 1200, 1200))

    # Flush should fail on daily_stats and rollback hourly_stats
    aggregator.flush()

    repo = StatsRepository(memory_db)
    # Hourly stats should remain empty due to rollback
    assert len(repo.get_hourly_records()) == 0
    # Staged bytes should remain in memory for future retry
    assert aggregator.staged_download_bytes == 200


def test_repository_empty_database_and_sorting(memory_db: Database) -> None:
    """Empty database returns empty lists; queried records are chronologically sorted."""
    repo = StatsRepository(memory_db)

    assert repo.get_hourly_records() == []
    assert repo.get_daily_records() == []
    assert repo.get_monthly_records() == []

    summary = repo.get_summary()
    assert summary.total_download_bytes == 0
    assert summary.total_upload_bytes == 0
    assert summary.record_count == 0

    # Insert out-of-order records
    with memory_db.transaction() as conn:
        conn.execute("INSERT INTO daily_stats VALUES ('2026-09-20', 300, 300, 0, 0);")
        conn.execute("INSERT INTO daily_stats VALUES ('2026-09-18', 100, 100, 0, 0);")
        conn.execute("INSERT INTO daily_stats VALUES ('2026-09-19', 200, 200, 0, 0);")

    daily = repo.get_daily_records()
    assert len(daily) == 3
    # Verify chronological ASC order
    assert daily[0].date == "2026-09-18"
    assert daily[1].date == "2026-09-19"
    assert daily[2].date == "2026-09-20"
