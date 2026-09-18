"""Data models for historical network statistics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HourlyRecord:
    """Aggregated network statistics for a single UTC hour."""

    hour_timestamp: str  # ISO-8601, e.g. "2026-09-18T00:00:00Z"
    download_bytes: int
    upload_bytes: int
    peak_download_bps: float
    peak_upload_bps: float


@dataclass(frozen=True)
class DailyRecord:
    """Aggregated network statistics for a single UTC day."""

    date: str  # YYYY-MM-DD, e.g. "2026-09-18"
    download_bytes: int
    upload_bytes: int
    peak_download_bps: float
    peak_upload_bps: float


@dataclass(frozen=True)
class MonthlyRecord:
    """Aggregated network statistics for a single UTC month."""

    year_month: str  # YYYY-MM, e.g. "2026-09"
    download_bytes: int
    upload_bytes: int
    peak_download_bps: float
    peak_upload_bps: float


@dataclass(frozen=True)
class HistoricalSummary:
    """Overall summary statistics across a queried historical period."""

    total_download_bytes: int
    total_upload_bytes: int
    peak_download_bps: float
    peak_upload_bps: float
    record_count: int


@dataclass(frozen=True)
class NetworkSummary:
    """Summary of a known network connection and its lifetime usage."""

    network_id: str
    connection_type: str
    ssid: Optional[str]
    display_name: str
    interface_id: str
    total_download_bytes: int
    total_upload_bytes: int
    peak_download_bps: float
    peak_upload_bps: float
    first_seen: str
    last_seen: str
