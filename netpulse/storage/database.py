"""SQLite database manager for NetPulse historical data.

Configures connection pooling/locks, enables Write-Ahead Logging (WAL)
mode, and initializes the aggregation schema.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from typing import Generator, Optional, Union

from netpulse.utils.constants import APP_NAME, DB_NAME
from netpulse.utils.log import get_logger

logger = get_logger("database")


def default_db_path() -> Path:
    """macOS standard application data path."""
    return Path.home() / "Library" / "Application Support" / APP_NAME / DB_NAME


class Database:
    """SQLite connection and schema manager."""

    SCHEMA_VERSION = 2

    def __init__(self, db_path: Optional[Union[Path, str]] = None) -> None:
        if db_path is None:
            self._path = str(default_db_path())
        else:
            self._path = str(db_path)

        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

        self._ensure_parent_directory()
        self._initialize_database()

    @property
    def path(self) -> str:
        """Database file path or ':memory:'."""
        return self._path

    def _ensure_parent_directory(self) -> None:
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the SQLite connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._path,
                check_same_thread=False,
                timeout=10.0,
            )
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode and performance pragmas if on disk
            if self._path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.execute("PRAGMA synchronous = NORMAL;")
            self._conn.execute("PRAGMA busy_timeout = 5000;")
        return self._conn

    def _initialize_database(self) -> None:
        """Initialize database tables, indexes, and run migrations."""
        with self.transaction() as conn:
            # 1. Base legacy tables (Phase 5)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS hourly_stats (
                    hour_timestamp TEXT PRIMARY KEY,
                    download_bytes INTEGER NOT NULL DEFAULT 0,
                    upload_bytes INTEGER NOT NULL DEFAULT 0,
                    peak_download_bps REAL NOT NULL DEFAULT 0.0,
                    peak_upload_bps REAL NOT NULL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    download_bytes INTEGER NOT NULL DEFAULT 0,
                    upload_bytes INTEGER NOT NULL DEFAULT 0,
                    peak_download_bps REAL NOT NULL DEFAULT 0.0,
                    peak_upload_bps REAL NOT NULL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS monthly_stats (
                    year_month TEXT PRIMARY KEY,
                    download_bytes INTEGER NOT NULL DEFAULT 0,
                    upload_bytes INTEGER NOT NULL DEFAULT 0,
                    peak_download_bps REAL NOT NULL DEFAULT 0.0,
                    peak_upload_bps REAL NOT NULL DEFAULT 0.0
                );

                CREATE INDEX IF NOT EXISTS idx_hourly_ts ON hourly_stats (hour_timestamp);
                CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_stats (date);
                CREATE INDEX IF NOT EXISTS idx_monthly_ym ON monthly_stats (year_month);

                -- Phase 6: Interface and Network Intelligence
                CREATE TABLE IF NOT EXISTS interfaces (
                    bsd_name TEXT PRIMARY KEY,
                    interface_id TEXT NOT NULL,
                    mac_address TEXT,
                    display_name TEXT NOT NULL,
                    interface_type TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS networks (
                    network_id TEXT PRIMARY KEY,
                    connection_type TEXT NOT NULL,
                    ssid TEXT,
                    display_name TEXT NOT NULL,
                    interface_id TEXT NOT NULL,
                    bssid_hash TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS network_hourly_stats (
                    network_id TEXT NOT NULL,
                    hour_timestamp TEXT NOT NULL,
                    download_bytes INTEGER NOT NULL DEFAULT 0,
                    upload_bytes INTEGER NOT NULL DEFAULT 0,
                    peak_download_bps REAL NOT NULL DEFAULT 0.0,
                    peak_upload_bps REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (network_id, hour_timestamp),
                    FOREIGN KEY(network_id) REFERENCES networks(network_id)
                );

                CREATE TABLE IF NOT EXISTS network_daily_stats (
                    network_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    download_bytes INTEGER NOT NULL DEFAULT 0,
                    upload_bytes INTEGER NOT NULL DEFAULT 0,
                    peak_download_bps REAL NOT NULL DEFAULT 0.0,
                    peak_upload_bps REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (network_id, date),
                    FOREIGN KEY(network_id) REFERENCES networks(network_id)
                );

                CREATE TABLE IF NOT EXISTS network_monthly_stats (
                    network_id TEXT NOT NULL,
                    year_month TEXT NOT NULL,
                    download_bytes INTEGER NOT NULL DEFAULT 0,
                    upload_bytes INTEGER NOT NULL DEFAULT 0,
                    peak_download_bps REAL NOT NULL DEFAULT 0.0,
                    peak_upload_bps REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (network_id, year_month),
                    FOREIGN KEY(network_id) REFERENCES networks(network_id)
                );

                CREATE INDEX IF NOT EXISTS idx_net_hourly_ts ON network_hourly_stats (hour_timestamp);
                CREATE INDEX IF NOT EXISTS idx_net_daily_date ON network_daily_stats (date);
                CREATE INDEX IF NOT EXISTS idx_net_monthly_ym ON network_monthly_stats (year_month);
            """)

            # 2. Check and apply migration if needed
            cur = conn.cursor()
            cur.execute("PRAGMA user_version;")
            ver_row = cur.fetchone()
            current_ver = ver_row[0] if ver_row else 0

            if current_ver < 2:
                # Seed legacy sentinel network
                cur.execute("""
                    INSERT OR IGNORE INTO networks (
                        network_id, connection_type, ssid, display_name, interface_id, first_seen, last_seen
                    ) VALUES (
                        '__SYSTEM_LEGACY__', 'system', NULL, 'System Total (Legacy)', 'iface:all', datetime('now'), datetime('now')
                    );
                """)
                # Migrate historical rollups to __SYSTEM_LEGACY__
                cur.execute("""
                    INSERT OR IGNORE INTO network_hourly_stats (
                        network_id, hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    )
                    SELECT '__SYSTEM_LEGACY__', hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    FROM hourly_stats;
                """)
                cur.execute("""
                    INSERT OR IGNORE INTO network_daily_stats (
                        network_id, date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    )
                    SELECT '__SYSTEM_LEGACY__', date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    FROM daily_stats;
                """)
                cur.execute("""
                    INSERT OR IGNORE INTO network_monthly_stats (
                        network_id, year_month, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    )
                    SELECT '__SYSTEM_LEGACY__', year_month, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    FROM monthly_stats;
                """)
                cur.execute("PRAGMA user_version = 2;")
                logger.info("Database migrated to schema version 2 (legacy records tagged under __SYSTEM_LEGACY__)")
        logger.info("Database initialized at %s", self._path)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a transactional database connection under a thread lock."""
        with self._lock:
            conn = self._get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                logger.exception("Database transaction failed and rolled back")
                raise

    def get_storage_info(self) -> dict:
        """Return storage metadata including file location, size, and record counts."""
        import os

        size_bytes = 0
        if self._path != ":memory:" and os.path.exists(self._path):
            try:
                size_bytes = os.path.getsize(self._path)
            except OSError:
                size_bytes = 0

        networks_count = 0
        has_history = False
        daily_count = 0

        try:
            with self.transaction() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM networks;")
                row = cur.fetchone()
                if row:
                    networks_count = row[0]

                cur.execute("SELECT COUNT(*) FROM daily_stats;")
                row = cur.fetchone()
                legacy_daily = row[0] if row else 0

                cur.execute("SELECT COUNT(*) FROM network_daily_stats;")
                row = cur.fetchone()
                net_daily = row[0] if row else 0

                daily_count = legacy_daily + net_daily
                has_history = (daily_count > 0 or networks_count > 0)
        except Exception:
            logger.exception("Error querying database storage info")

        return {
            "path": self._path,
            "size_bytes": size_bytes,
            "has_history": has_history,
            "networks_count": networks_count,
            "daily_records_count": daily_count,
        }

    def reset_statistics(self) -> None:
        """Permanently clear all historical statistics and network records.

        Preserves database schema and PRAGMA user_version. Immediately
        ready for subsequent writes.
        """
        with self.transaction() as conn:
            conn.execute("DELETE FROM network_hourly_stats;")
            conn.execute("DELETE FROM network_daily_stats;")
            conn.execute("DELETE FROM network_monthly_stats;")
            conn.execute("DELETE FROM hourly_stats;")
            conn.execute("DELETE FROM daily_stats;")
            conn.execute("DELETE FROM monthly_stats;")
            conn.execute("DELETE FROM networks;")
            conn.execute("DELETE FROM interfaces;")

        # Run VACUUM outside explicit transaction block (SQLite requirement)
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("VACUUM;")
            except Exception:
                logger.warning("VACUUM failed during database reset", exc_info=True)

        logger.info("Database statistics and network history reset successfully")

    def reset_all(self) -> None:
        """Reset all tables in database while maintaining schema integrity."""
        self.reset_statistics()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    logger.exception("Error closing database")
                finally:
                    self._conn = None
