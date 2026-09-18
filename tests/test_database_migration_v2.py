"""Tests for SQLite database schema v1 to v2 atomic migration."""

from pathlib import Path
import sqlite3
import tempfile

from netpulse.storage.database import Database
from netpulse.storage.repository import StatsRepository


def test_migration_v1_to_v2() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_migrate.db"

        # 1. Create a legacy v1 database
        conn = sqlite3.connect(str(db_file))
        conn.executescript("""
            PRAGMA user_version = 1;

            CREATE TABLE hourly_stats (
                hour_timestamp TEXT PRIMARY KEY,
                download_bytes INTEGER NOT NULL DEFAULT 0,
                upload_bytes INTEGER NOT NULL DEFAULT 0,
                peak_download_bps REAL NOT NULL DEFAULT 0.0,
                peak_upload_bps REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE daily_stats (
                date TEXT PRIMARY KEY,
                download_bytes INTEGER NOT NULL DEFAULT 0,
                upload_bytes INTEGER NOT NULL DEFAULT 0,
                peak_download_bps REAL NOT NULL DEFAULT 0.0,
                peak_upload_bps REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE monthly_stats (
                year_month TEXT PRIMARY KEY,
                download_bytes INTEGER NOT NULL DEFAULT 0,
                upload_bytes INTEGER NOT NULL DEFAULT 0,
                peak_download_bps REAL NOT NULL DEFAULT 0.0,
                peak_upload_bps REAL NOT NULL DEFAULT 0.0
            );

            INSERT INTO hourly_stats VALUES ('2026-09-17T10:00:00Z', 1048576, 524288, 102400.0, 51200.0);
            INSERT INTO daily_stats VALUES ('2026-09-17', 20971520, 10485760, 204800.0, 102400.0);
            INSERT INTO monthly_stats VALUES ('2026-09', 524288000, 262144000, 409600.0, 204800.0);
        """)
        conn.commit()
        conn.close()

        # 2. Open with NetPulse v2 Database manager
        db = Database(db_file)
        assert db.SCHEMA_VERSION == 2

        # Verify user_version bumped to 2
        with db.transaction() as cur:
            row = cur.execute("PRAGMA user_version;").fetchone()
            assert row[0] == 2

        # Verify legacy sentinel network created
        repo = StatsRepository(db)
        known = repo.get_known_networks()
        net_ids = [n.network_id for n in known]
        assert "__SYSTEM_LEGACY__" in net_ids

        # Verify rows migrated under __SYSTEM_LEGACY__
        hourly = repo.get_network_hourly_records("__SYSTEM_LEGACY__")
        assert len(hourly) == 1
        assert hourly[0].hour_timestamp == "2026-09-17T10:00:00Z"
        assert hourly[0].download_bytes == 1048576
        assert hourly[0].upload_bytes == 524288

        daily = repo.get_network_daily_records("__SYSTEM_LEGACY__")
        assert len(daily) == 1
        assert daily[0].date == "2026-09-17"
        assert daily[0].download_bytes == 20971520

        # Verify original tables are preserved
        orig_hourly = repo.get_hourly_records()
        assert len(orig_hourly) == 1
        assert orig_hourly[0].download_bytes == 1048576

        db.close()
