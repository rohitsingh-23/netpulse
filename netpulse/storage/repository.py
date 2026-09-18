"""Repository for querying historical network statistics from SQLite."""

from __future__ import annotations

from typing import List, Optional

from netpulse.storage.database import Database
from netpulse.storage.models import (
    DailyRecord,
    HistoricalSummary,
    HourlyRecord,
    MonthlyRecord,
    NetworkSummary,
)
from netpulse.utils.log import get_logger

logger = get_logger("repository")


class StatsRepository:
    """Read-only query repository for historical statistics."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def get_hourly_records(self, limit: int = 24) -> List[HourlyRecord]:
        """Fetch the most recent hourly records ordered chronologically."""
        query = """
            SELECT hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
            FROM (
                SELECT * FROM hourly_stats
                ORDER BY hour_timestamp DESC
                LIMIT ?
            )
            ORDER BY hour_timestamp ASC;
        """
        records: List[HourlyRecord] = []
        try:
            with self._db.transaction() as conn:
                cursor = conn.execute(query, (limit,))
                for row in cursor.fetchall():
                    records.append(
                        HourlyRecord(
                            hour_timestamp=row["hour_timestamp"],
                            download_bytes=row["download_bytes"],
                            upload_bytes=row["upload_bytes"],
                            peak_download_bps=row["peak_download_bps"],
                            peak_upload_bps=row["peak_upload_bps"],
                        )
                    )
        except Exception:
            logger.exception("Failed to query hourly records")
        return records

    def get_daily_records(self, limit: int = 30) -> List[DailyRecord]:
        """Fetch the most recent daily records ordered chronologically."""
        query = """
            SELECT date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
            FROM (
                SELECT * FROM daily_stats
                ORDER BY date DESC
                LIMIT ?
            )
            ORDER BY date ASC;
        """
        records: List[DailyRecord] = []
        try:
            with self._db.transaction() as conn:
                cursor = conn.execute(query, (limit,))
                for row in cursor.fetchall():
                    records.append(
                        DailyRecord(
                            date=row["date"],
                            download_bytes=row["download_bytes"],
                            upload_bytes=row["upload_bytes"],
                            peak_download_bps=row["peak_download_bps"],
                            peak_upload_bps=row["peak_upload_bps"],
                        )
                    )
        except Exception:
            logger.exception("Failed to query daily records")
        return records

    def get_monthly_records(self, limit: int = 12) -> List[MonthlyRecord]:
        """Fetch the most recent monthly records ordered chronologically."""
        query = """
            SELECT year_month, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
            FROM (
                SELECT * FROM monthly_stats
                ORDER BY year_month DESC
                LIMIT ?
            )
            ORDER BY year_month ASC;
        """
        records: List[MonthlyRecord] = []
        try:
            with self._db.transaction() as conn:
                cursor = conn.execute(query, (limit,))
                for row in cursor.fetchall():
                    records.append(
                        MonthlyRecord(
                            year_month=row["year_month"],
                            download_bytes=row["download_bytes"],
                            upload_bytes=row["upload_bytes"],
                            peak_download_bps=row["peak_download_bps"],
                            peak_upload_bps=row["peak_upload_bps"],
                        )
                    )
        except Exception:
            logger.exception("Failed to query monthly records")
        return records

    def get_summary(self, days: int = 30) -> HistoricalSummary:
        """Compute aggregate summary totals over the last `days` daily records."""
        query = """
            SELECT
                COALESCE(SUM(download_bytes), 0) AS total_dl,
                COALESCE(SUM(upload_bytes), 0) AS total_ul,
                COALESCE(MAX(peak_download_bps), 0.0) AS max_dl,
                COALESCE(MAX(peak_upload_bps), 0.0) AS max_ul,
                COUNT(*) AS cnt
            FROM (
                SELECT * FROM daily_stats
                ORDER BY date DESC
                LIMIT ?
            );
        """
        try:
            with self._db.transaction() as conn:
                row = conn.execute(query, (days,)).fetchone()
                if row:
                    return HistoricalSummary(
                        total_download_bytes=row["total_dl"],
                        total_upload_bytes=row["total_ul"],
                        peak_download_bps=row["max_dl"],
                        peak_upload_bps=row["max_ul"],
                        record_count=row["cnt"],
                    )
        except Exception:
            logger.exception("Failed to calculate historical summary")

        return HistoricalSummary(
            total_download_bytes=0,
            total_upload_bytes=0,
            peak_download_bps=0.0,
            peak_upload_bps=0.0,
            record_count=0,
        )

    def upsert_network(
        self,
        network_id: str,
        connection_type: str,
        ssid: Optional[str],
        display_name: str,
        interface_id: str,
        bssid_hash: Optional[str] = None,
    ) -> None:
        """Insert or update a network entry in the networks table."""
        query = """
            INSERT INTO networks (
                network_id, connection_type, ssid, display_name, interface_id, bssid_hash, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(network_id) DO UPDATE SET
                display_name = excluded.display_name,
                connection_type = excluded.connection_type,
                ssid = COALESCE(excluded.ssid, networks.ssid),
                interface_id = excluded.interface_id,
                bssid_hash = COALESCE(excluded.bssid_hash, networks.bssid_hash),
                last_seen = datetime('now');
        """
        try:
            with self._db.transaction() as conn:
                conn.execute(
                    query,
                    (network_id, connection_type, ssid, display_name, interface_id, bssid_hash),
                )
        except Exception:
            logger.exception("Failed to upsert network %s", network_id)

    def get_known_networks(self) -> List[NetworkSummary]:
        """Fetch all known networks with their aggregated lifetime usage."""
        query = """
            SELECT
                n.network_id,
                n.connection_type,
                n.ssid,
                n.display_name,
                n.interface_id,
                n.first_seen,
                n.last_seen,
                COALESCE(SUM(s.download_bytes), 0) AS total_dl,
                COALESCE(SUM(s.upload_bytes), 0) AS total_ul,
                COALESCE(MAX(s.peak_download_bps), 0.0) AS max_dl,
                COALESCE(MAX(s.peak_upload_bps), 0.0) AS max_ul
            FROM networks n
            LEFT JOIN network_daily_stats s ON n.network_id = s.network_id
            GROUP BY n.network_id
            ORDER BY n.last_seen DESC;
        """
        networks: List[NetworkSummary] = []
        try:
            with self._db.transaction() as conn:
                cursor = conn.execute(query)
                for row in cursor.fetchall():
                    networks.append(
                        NetworkSummary(
                            network_id=row["network_id"],
                            connection_type=row["connection_type"],
                            ssid=row["ssid"],
                            display_name=row["display_name"],
                            interface_id=row["interface_id"],
                            total_download_bytes=row["total_dl"],
                            total_upload_bytes=row["total_ul"],
                            peak_download_bps=row["max_dl"],
                            peak_upload_bps=row["max_ul"],
                            first_seen=row["first_seen"],
                            last_seen=row["last_seen"],
                        )
                    )
        except Exception:
            logger.exception("Failed to query known networks")
        return networks

    def get_network_hourly_records(
        self, network_id: str, limit: int = 24
    ) -> List[HourlyRecord]:
        """Fetch the most recent hourly records for a specific network ordered chronologically."""
        query = """
            SELECT hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
            FROM (
                SELECT * FROM network_hourly_stats
                WHERE network_id = ?
                ORDER BY hour_timestamp DESC
                LIMIT ?
            )
            ORDER BY hour_timestamp ASC;
        """
        records: List[HourlyRecord] = []
        try:
            with self._db.transaction() as conn:
                cursor = conn.execute(query, (network_id, limit))
                for row in cursor.fetchall():
                    records.append(
                        HourlyRecord(
                            hour_timestamp=row["hour_timestamp"],
                            download_bytes=row["download_bytes"],
                            upload_bytes=row["upload_bytes"],
                            peak_download_bps=row["peak_download_bps"],
                            peak_upload_bps=row["peak_upload_bps"],
                        )
                    )
        except Exception:
            logger.exception("Failed to query network hourly records for %s", network_id)
        return records

    def get_network_daily_records(
        self, network_id: str, limit: int = 30
    ) -> List[DailyRecord]:
        """Fetch the most recent daily records for a specific network ordered chronologically."""
        query = """
            SELECT date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
            FROM (
                SELECT * FROM network_daily_stats
                WHERE network_id = ?
                ORDER BY date DESC
                LIMIT ?
            )
            ORDER BY date ASC;
        """
        records: List[DailyRecord] = []
        try:
            with self._db.transaction() as conn:
                cursor = conn.execute(query, (network_id, limit))
                for row in cursor.fetchall():
                    records.append(
                        DailyRecord(
                            date=row["date"],
                            download_bytes=row["download_bytes"],
                            upload_bytes=row["upload_bytes"],
                            peak_download_bps=row["peak_download_bps"],
                            peak_upload_bps=row["peak_upload_bps"],
                        )
                    )
        except Exception:
            logger.exception("Failed to query network daily records for %s", network_id)
        return records
