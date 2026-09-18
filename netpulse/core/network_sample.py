"""Immutable network sample data model.

Design decisions:
- Frozen dataclass for immutability — samples are never modified after creation.
- Negative speeds are clamped to 0.0 as a defense-in-depth measure
  (SpeedCalculator already prevents them).
- Naive timestamps are promoted to UTC. All timestamps in NetPulse are
  timezone-aware UTC to avoid ambiguity across storage and display.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class NetworkSample:
    """An immutable snapshot of network speed and counters at a point in time.

    Attributes:
        timestamp: When the sample was taken (UTC, timezone-aware).
        download_bps: Download speed in bytes per second (≥ 0).
        upload_bps: Upload speed in bytes per second (≥ 0).
        total_download_bytes: Cumulative bytes received since boot.
        total_upload_bytes: Cumulative bytes sent since boot.
        interface: Network interface name, or None for system-wide.
    """

    timestamp: datetime
    download_bps: float
    upload_bps: float
    total_download_bytes: int
    total_upload_bytes: int
    interface: str | None = None
    network_id: str | None = None
    interface_id: str | None = None

    def __post_init__(self) -> None:
        # Clamp negative speeds
        if self.download_bps < 0:
            object.__setattr__(self, "download_bps", 0.0)
        if self.upload_bps < 0:
            object.__setattr__(self, "upload_bps", 0.0)
        # Ensure timezone-aware timestamp
        if self.timestamp.tzinfo is None:
            object.__setattr__(
                self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc)
            )
