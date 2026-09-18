"""Pure calculation functions and data structures for Network Analytics Dashboard.

Provides testable aggregations (window averages, peaks, session totals,
and time filtering) decoupled from GUI widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.core.network_sample import NetworkSample


@dataclass(frozen=True)
class WindowMetrics:
    """Aggregated network speeds for a specific time window."""

    current_download_bps: float
    current_upload_bps: float
    average_download_bps: float
    average_upload_bps: float
    peak_download_bps: float
    peak_upload_bps: float
    sample_count: int


@dataclass(frozen=True)
class SessionMetrics:
    """Aggregated session statistics for the active monitoring session."""

    downloaded_bytes: int
    uploaded_bytes: int
    total_bytes: int
    session_start: datetime
    elapsed_seconds: float
    current_download_bps: float
    current_upload_bps: float
    peak_download_bps: float
    peak_upload_bps: float


def filter_samples_by_range(
    samples: List[NetworkSample],
    range_seconds: float,
    now: Optional[datetime] = None,
) -> List[NetworkSample]:
    """Filter samples to those within the last `range_seconds`.

    Args:
        samples: Sequence of NetworkSample objects.
        range_seconds: Number of seconds in the past to include.
        now: Optional current timestamp (defaults to datetime.now(timezone.utc)).

    Returns:
        List of samples with timestamps >= (now - range_seconds).
    """
    if not samples or range_seconds <= 0:
        return []

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    cutoff_ts = now.timestamp() - range_seconds
    return [s for s in samples if s.timestamp.timestamp() >= cutoff_ts]


def calculate_window_metrics(samples: List[NetworkSample]) -> WindowMetrics:
    """Compute current, average, and peak speeds for a collection of samples.

    Args:
        samples: Sequence of NetworkSample objects (assumed chronological).

    Returns:
        WindowMetrics populated with calculations. If empty, all values are 0.0.
    """
    if not samples:
        return WindowMetrics(
            current_download_bps=0.0,
            current_upload_bps=0.0,
            average_download_bps=0.0,
            average_upload_bps=0.0,
            peak_download_bps=0.0,
            peak_upload_bps=0.0,
            sample_count=0,
        )

    count = len(samples)
    latest = samples[-1]

    total_dl = 0.0
    total_ul = 0.0
    max_dl = 0.0
    max_ul = 0.0

    for s in samples:
        dl = s.download_bps
        ul = s.upload_bps
        total_dl += dl
        total_ul += ul
        if dl > max_dl:
            max_dl = dl
        if ul > max_ul:
            max_ul = ul

    return WindowMetrics(
        current_download_bps=latest.download_bps,
        current_upload_bps=latest.upload_bps,
        average_download_bps=total_dl / count,
        average_upload_bps=total_ul / count,
        peak_download_bps=max_dl,
        peak_upload_bps=max_ul,
        sample_count=count,
    )


def calculate_session_metrics(
    monitor: NetworkMonitor,
    current_sample: Optional[NetworkSample] = None,
    now: Optional[datetime] = None,
) -> SessionMetrics:
    """Extract session totals, duration, and peak speeds from monitor and samples.

    Args:
        monitor: The active NetworkMonitor instance.
        current_sample: Most recent NetworkSample received, if any.
        now: Optional current timestamp (defaults to datetime.now(timezone.utc)).

    Returns:
        SessionMetrics representation of the active session.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    start = monitor.session_start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    elapsed = max(0.0, (now - start).total_seconds())

    dl_bytes = monitor.session_downloaded
    ul_bytes = monitor.session_uploaded

    cur_dl = current_sample.download_bps if current_sample else 0.0
    cur_ul = current_sample.upload_bps if current_sample else 0.0

    peak_dl = monitor.session_peak_download
    peak_ul = monitor.session_peak_upload
    if cur_dl > peak_dl:
        peak_dl = cur_dl
    if cur_ul > peak_ul:
        peak_ul = cur_ul

    return SessionMetrics(
        downloaded_bytes=dl_bytes,
        uploaded_bytes=ul_bytes,
        total_bytes=dl_bytes + ul_bytes,
        session_start=start,
        elapsed_seconds=elapsed,
        current_download_bps=cur_dl,
        current_upload_bps=cur_ul,
        peak_download_bps=peak_dl,
        peak_upload_bps=peak_ul,
    )


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a human-readable string.

    Examples:
        45 -> "45s"
        125 -> "2m 05s"
        3665 -> "1h 01m 05s"
    """
    total_sec = max(0, int(seconds))
    hours, remainder = divmod(total_sec, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
