"""Unit tests for metrics calculation service."""

from datetime import datetime, timezone, timedelta
import pytest

from netpulse.core.network_sample import NetworkSample
from netpulse.ui.metrics import (
    calculate_session_metrics,
    calculate_window_metrics,
    filter_samples_by_range,
    format_duration,
)


class MockMonitor:
    """Mock monitor providing session stats for testing."""

    def __init__(
        self,
        session_downloaded: int = 1000,
        session_uploaded: int = 500,
        session_start_time: datetime = None,
        session_peak_download: float = 200.0,
        session_peak_upload: float = 100.0,
    ) -> None:
        self.session_downloaded = session_downloaded
        self.session_uploaded = session_uploaded
        self.session_start_time = session_start_time or (
            datetime.now(timezone.utc) - timedelta(seconds=90)
        )
        self.session_peak_download = session_peak_download
        self.session_peak_upload = session_peak_upload


def test_calculate_window_metrics_empty() -> None:
    """Empty sample list returns zeros."""
    m = calculate_window_metrics([])
    assert m.current_download_bps == 0.0
    assert m.current_upload_bps == 0.0
    assert m.average_download_bps == 0.0
    assert m.average_upload_bps == 0.0
    assert m.peak_download_bps == 0.0
    assert m.peak_upload_bps == 0.0
    assert m.sample_count == 0


def test_calculate_window_metrics_single() -> None:
    """Single sample calculations."""
    now = datetime.now(timezone.utc)
    s = NetworkSample(
        timestamp=now,
        download_bps=1000.0,
        upload_bps=500.0,
        total_download_bytes=1000,
        total_upload_bytes=500,
    )
    m = calculate_window_metrics([s])
    assert m.current_download_bps == 1000.0
    assert m.current_upload_bps == 500.0
    assert m.average_download_bps == 1000.0
    assert m.average_upload_bps == 500.0
    assert m.peak_download_bps == 1000.0
    assert m.peak_upload_bps == 500.0
    assert m.sample_count == 1


def test_calculate_window_metrics_multi() -> None:
    """Multi-sample averages and peaks."""
    now = datetime.now(timezone.utc)
    s1 = NetworkSample(
        timestamp=now - timedelta(seconds=2),
        download_bps=100.0,
        upload_bps=50.0,
        total_download_bytes=100,
        total_upload_bytes=50,
    )
    s2 = NetworkSample(
        timestamp=now - timedelta(seconds=1),
        download_bps=300.0,
        upload_bps=150.0,
        total_download_bytes=400,
        total_upload_bytes=200,
    )
    s3 = NetworkSample(
        timestamp=now,
        download_bps=200.0,
        upload_bps=100.0,
        total_download_bytes=600,
        total_upload_bytes=300,
    )
    m = calculate_window_metrics([s1, s2, s3])
    assert m.current_download_bps == 200.0
    assert m.current_upload_bps == 100.0
    assert m.average_download_bps == 200.0  # (100+300+200)/3
    assert m.average_upload_bps == 100.0   # (50+150+100)/3
    assert m.peak_download_bps == 300.0
    assert m.peak_upload_bps == 150.0
    assert m.sample_count == 3


def test_filter_samples_by_range() -> None:
    """Filter samples based on range cutoff."""
    now = datetime.now(timezone.utc)
    s_old = NetworkSample(
        timestamp=now - timedelta(seconds=400),
        download_bps=10.0,
        upload_bps=10.0,
        total_download_bytes=10,
        total_upload_bytes=10,
    )
    s_recent = NetworkSample(
        timestamp=now - timedelta(seconds=60),
        download_bps=20.0,
        upload_bps=20.0,
        total_download_bytes=30,
        total_upload_bytes=30,
    )
    samples = [s_old, s_recent]

    # 5 minutes = 300 seconds
    filtered = filter_samples_by_range(samples, 300, now=now)
    assert len(filtered) == 1
    assert filtered[0] == s_recent

    # 10 minutes = 600 seconds
    filtered_all = filter_samples_by_range(samples, 600, now=now)
    assert len(filtered_all) == 2


def test_calculate_session_metrics() -> None:
    """Compute session totals and peaks."""
    start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 1, 1, 12, 1, 30, tzinfo=timezone.utc)  # 90s later
    mon = MockMonitor(
        session_downloaded=1024,
        session_uploaded=512,
        session_start_time=start,
        session_peak_download=500.0,
        session_peak_upload=250.0,
    )
    cur = NetworkSample(
        timestamp=now,
        download_bps=600.0,  # exceeds peak
        upload_bps=100.0,
        total_download_bytes=1624,
        total_upload_bytes=612,
    )
    m = calculate_session_metrics(mon, current_sample=cur, now=now)
    assert m.downloaded_bytes == 1024
    assert m.uploaded_bytes == 512
    assert m.total_bytes == 1536
    assert m.elapsed_seconds == 90.0
    assert m.current_download_bps == 600.0
    assert m.current_upload_bps == 100.0
    assert m.peak_download_bps == 600.0
    assert m.peak_upload_bps == 250.0


def test_format_duration() -> None:
    """Format duration strings."""
    assert format_duration(45) == "45s"
    assert format_duration(125) == "2m 05s"
    assert format_duration(3665) == "1h 01m 05s"
    assert format_duration(0) == "0s"
