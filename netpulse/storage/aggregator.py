"""Aggregator that stages NetworkSample streams and updates SQLite rollups.

Accumulates live high-frequency samples into in-memory hour buckets,
then updates hourly, daily, and monthly database records atomically.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import threading
import time
from typing import TYPE_CHECKING, Optional

from netpulse.utils.constants import MAX_MEASUREMENT_GAP, STORAGE_FLUSH_INTERVAL
from netpulse.utils.log import get_logger

if TYPE_CHECKING:
    from netpulse.core.network_sample import NetworkSample
    from netpulse.storage.database import Database

logger = get_logger("aggregator")


class SampleAggregator:
    """Consumes NetworkSample streams and persists aggregated rollups.

    Args:
        database: Database instance to persist to.
        flush_interval: Minimum seconds between automatic database flushes.
        max_measurement_gap: Maximum allowed gap in seconds between samples before
            considering it a sleep/wake or stall event (default 10.0s).
    """

    def __init__(
        self,
        database: Database,
        flush_interval: float = STORAGE_FLUSH_INTERVAL,
        max_measurement_gap: float = MAX_MEASUREMENT_GAP,
    ) -> None:
        self._db = database
        self._flush_interval = flush_interval
        self._max_measurement_gap = max_measurement_gap

        self._lock = threading.Lock()
        self._last_sample: Optional[NetworkSample] = None
        self._last_flush_time: float = time.monotonic()

        # In-memory staging bucket
        self._staged_network_id: Optional[str] = None
        self._staged_hour: Optional[str] = None
        self._staged_dl_bytes: int = 0
        self._staged_ul_bytes: int = 0
        self._staged_peak_dl: float = 0.0
        self._staged_peak_ul: float = 0.0

    @property
    def staged_network_id(self) -> Optional[str]:
        """Currently active network ID for staged samples."""
        with self._lock:
            return self._staged_network_id

    @property
    def staged_download_bytes(self) -> int:
        """Currently staged but unflushed download bytes."""
        with self._lock:
            return self._staged_dl_bytes

    @property
    def staged_upload_bytes(self) -> int:
        """Currently staged but unflushed upload bytes."""
        with self._lock:
            return self._staged_ul_bytes

    def on_sample(self, sample: NetworkSample) -> None:
        """Process an incoming NetworkSample from NetworkMonitor."""
        with self._lock:
            # Handle network switching
            incoming_net_id = sample.network_id or "__SYSTEM_LEGACY__"
            if self._staged_network_id is not None and self._staged_network_id != incoming_net_id:
                logger.info(
                    "Network switch detected from %s to %s, flushing staged usage and resetting baseline",
                    self._staged_network_id, incoming_net_id
                )
                self._flush_locked()
                self._last_sample = None

            self._staged_network_id = incoming_net_id

            ts = sample.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)

            hour_str = ts.strftime("%Y-%m-%dT%H:00:00Z")

            if self._last_sample is not None:
                prev_ts = self._last_sample.timestamp
                if prev_ts.tzinfo is None:
                    prev_ts = prev_ts.replace(tzinfo=timezone.utc)
                else:
                    prev_ts = prev_ts.astimezone(timezone.utc)

                elapsed = (ts - prev_ts).total_seconds()
                dl_delta = sample.total_download_bytes - self._last_sample.total_download_bytes
                ul_delta = sample.total_upload_bytes - self._last_sample.total_upload_bytes

                # 1. Reject counter resets (reboot or interface reset)
                if dl_delta < 0 or ul_delta < 0:
                    logger.warning(
                        "Counter reset detected (RX delta=%d, TX delta=%d), establishing new baseline",
                        dl_delta, ul_delta
                    )
                    self._last_sample = sample
                    return

                # 2. Reject large gaps / sleep-wake stalls
                if elapsed > self._max_measurement_gap or elapsed <= 0:
                    logger.info(
                        "Measurement gap (%.1fs > %.1fs) or non-positive elapsed, resetting baseline without accumulating",
                        elapsed, self._max_measurement_gap
                    )
                    self._last_sample = sample
                    return

                # 3. Accumulate delta, splitting proportionally across hour boundaries if needed
                self._accumulate_interval_locked(
                    prev_ts, ts, dl_delta, ul_delta, sample.download_bps, sample.upload_bps
                )
            else:
                # First sample establishes baseline
                if self._staged_hour is None:
                    self._staged_hour = hour_str
                if sample.download_bps > self._staged_peak_dl:
                    self._staged_peak_dl = sample.download_bps
                if sample.upload_bps > self._staged_peak_ul:
                    self._staged_peak_ul = sample.upload_bps

            self._last_sample = sample

            # Check periodic flush threshold
            now_mono = time.monotonic()
            if (now_mono - self._last_flush_time) >= self._flush_interval:
                self._flush_locked()

    def _accumulate_interval_locked(
        self,
        t_start: datetime,
        t_end: datetime,
        dl_delta: int,
        ul_delta: int,
        peak_dl: float,
        peak_ul: float,
    ) -> None:
        """Slice an interval across hour boundaries and allocate proportional bytes."""
        total_duration = (t_end - t_start).total_seconds()
        if total_duration <= 0:
            return

        cur_t = t_start
        allocated_dl = 0
        allocated_ul = 0

        while cur_t < t_end:
            next_boundary = cur_t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            slice_end = min(t_end, next_boundary)
            slice_duration = (slice_end - cur_t).total_seconds()
            fraction = slice_duration / total_duration

            if slice_end == t_end:
                slice_dl = dl_delta - allocated_dl
                slice_ul = ul_delta - allocated_ul
            else:
                slice_dl = int(round(dl_delta * fraction))
                slice_ul = int(round(ul_delta * fraction))
                allocated_dl += slice_dl
                allocated_ul += slice_ul

            hour_str = cur_t.strftime("%Y-%m-%dT%H:00:00Z")

            if self._staged_hour is not None and self._staged_hour != hour_str:
                self._flush_locked()

            if self._staged_hour is None:
                self._staged_hour = hour_str

            self._staged_dl_bytes += slice_dl
            self._staged_ul_bytes += slice_ul

            if peak_dl > self._staged_peak_dl:
                self._staged_peak_dl = peak_dl
            if peak_ul > self._staged_peak_ul:
                self._staged_peak_ul = peak_ul

            # If slice reached the boundary, flush that hour
            if slice_end == next_boundary and slice_end < t_end:
                self._flush_locked()

            cur_t = slice_end

    def flush(self) -> None:
        """Flush staged metrics to SQLite database immediately."""
        with self._lock:
            self._flush_locked()

    def reset(self) -> None:
        """Intentionally discard in-memory staged metrics and clear baseline.

        Ensures no unflushed records leak into a reset database and next
        sample re-establishes a fresh baseline without computing deltas.
        """
        with self._lock:
            self._last_sample = None
            self._staged_network_id = None
            self._staged_hour = None
            self._staged_dl_bytes = 0
            self._staged_ul_bytes = 0
            self._staged_peak_dl = 0.0
            self._staged_peak_ul = 0.0
            self._last_flush_time = time.monotonic()
        logger.info("SampleAggregator reset: staged metrics discarded and baseline cleared")

    def _flush_locked(self) -> None:
        """Write staged metrics to SQLite within active lock."""
        if self._staged_hour is None:
            self._last_flush_time = time.monotonic()
            return

        hour_ts = self._staged_hour
        date_str = hour_ts[:10]  # YYYY-MM-DD
        month_str = hour_ts[:7]  # YYYY-MM

        dl_bytes = self._staged_dl_bytes
        ul_bytes = self._staged_ul_bytes
        peak_dl = self._staged_peak_dl
        peak_ul = self._staged_peak_ul
        net_id = self._staged_network_id or "__SYSTEM_LEGACY__"

        try:
            with self._db.transaction() as conn:
                # 1. Update legacy hourly_stats
                conn.execute(
                    """
                    INSERT INTO hourly_stats (
                        hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(hour_timestamp) DO UPDATE SET
                        download_bytes = download_bytes + excluded.download_bytes,
                        upload_bytes = upload_bytes + excluded.upload_bytes,
                        peak_download_bps = MAX(peak_download_bps, excluded.peak_download_bps),
                        peak_upload_bps = MAX(peak_upload_bps, excluded.peak_upload_bps);
                    """,
                    (hour_ts, dl_bytes, ul_bytes, peak_dl, peak_ul),
                )

                # 2. Update legacy daily_stats
                conn.execute(
                    """
                    INSERT INTO daily_stats (
                        date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        download_bytes = download_bytes + excluded.download_bytes,
                        upload_bytes = upload_bytes + excluded.upload_bytes,
                        peak_download_bps = MAX(peak_download_bps, excluded.peak_download_bps),
                        peak_upload_bps = MAX(peak_upload_bps, excluded.peak_upload_bps);
                    """,
                    (date_str, dl_bytes, ul_bytes, peak_dl, peak_ul),
                )

                # 3. Update legacy monthly_stats
                conn.execute(
                    """
                    INSERT INTO monthly_stats (
                        year_month, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(year_month) DO UPDATE SET
                        download_bytes = download_bytes + excluded.download_bytes,
                        upload_bytes = upload_bytes + excluded.upload_bytes,
                        peak_download_bps = MAX(peak_download_bps, excluded.peak_download_bps),
                        peak_upload_bps = MAX(peak_upload_bps, excluded.peak_upload_bps);
                    """,
                    (month_str, dl_bytes, ul_bytes, peak_dl, peak_ul),
                )

                # 4. Ensure network record exists
                conn.execute(
                    """
                    INSERT INTO networks (
                        network_id, connection_type, ssid, display_name, interface_id, first_seen, last_seen
                    ) VALUES (?, 'unknown', NULL, ?, 'iface:unknown', datetime('now'), datetime('now'))
                    ON CONFLICT(network_id) DO UPDATE SET
                        last_seen = datetime('now');
                    """,
                    (net_id, net_id),
                )

                # 5. Update network_hourly_stats
                conn.execute(
                    """
                    INSERT INTO network_hourly_stats (
                        network_id, hour_timestamp, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(network_id, hour_timestamp) DO UPDATE SET
                        download_bytes = download_bytes + excluded.download_bytes,
                        upload_bytes = upload_bytes + excluded.upload_bytes,
                        peak_download_bps = MAX(peak_download_bps, excluded.peak_download_bps),
                        peak_upload_bps = MAX(peak_upload_bps, excluded.peak_upload_bps);
                    """,
                    (net_id, hour_ts, dl_bytes, ul_bytes, peak_dl, peak_ul),
                )

                # 6. Update network_daily_stats
                conn.execute(
                    """
                    INSERT INTO network_daily_stats (
                        network_id, date, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(network_id, date) DO UPDATE SET
                        download_bytes = download_bytes + excluded.download_bytes,
                        upload_bytes = upload_bytes + excluded.upload_bytes,
                        peak_download_bps = MAX(peak_download_bps, excluded.peak_download_bps),
                        peak_upload_bps = MAX(peak_upload_bps, excluded.peak_upload_bps);
                    """,
                    (net_id, date_str, dl_bytes, ul_bytes, peak_dl, peak_ul),
                )

                # 7. Update network_monthly_stats
                conn.execute(
                    """
                    INSERT INTO network_monthly_stats (
                        network_id, year_month, download_bytes, upload_bytes, peak_download_bps, peak_upload_bps
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(network_id, year_month) DO UPDATE SET
                        download_bytes = download_bytes + excluded.download_bytes,
                        upload_bytes = upload_bytes + excluded.upload_bytes,
                        peak_download_bps = MAX(peak_download_bps, excluded.peak_download_bps),
                        peak_upload_bps = MAX(peak_upload_bps, excluded.peak_upload_bps);
                    """,
                    (net_id, month_str, dl_bytes, ul_bytes, peak_dl, peak_ul),
                )

            logger.debug(
                "Flushed network stats (net=%s): hour=%s dl=%d ul=%d peak_dl=%.1f peak_ul=%.1f",
                net_id, hour_ts, dl_bytes, ul_bytes, peak_dl, peak_ul
            )

            # Reset staging counters and bucket
            self._staged_hour = None
            self._staged_dl_bytes = 0
            self._staged_ul_bytes = 0
            self._staged_peak_dl = 0.0
            self._staged_peak_ul = 0.0
            self._last_flush_time = time.monotonic()

        except Exception:
            logger.exception("Failed to flush aggregated network samples to database")
