"""Graph data providers for BandwidthGraph.

Decouples data sourcing (live rolling buffer vs historical SQLite records)
from graph rendering logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import List, Protocol, Tuple

from netpulse.core.data_buffer import DataBuffer
from netpulse.storage.repository import StatsRepository


class IGraphDataProvider(Protocol):
    """Interface for feeding time-series series data to BandwidthGraph."""

    def get_series(
        self, duration_seconds: int
    ) -> Tuple[List[float], List[float], List[float]]:
        """Return (timestamps, download_values, upload_values)."""
        ...


class LiveBufferDataProvider:
    """Feeds live NetworkSample objects from an in-memory rolling DataBuffer."""

    def __init__(self, data_buffer: DataBuffer) -> None:
        self._buffer = data_buffer

    def get_series(
        self, duration_seconds: int
    ) -> Tuple[List[float], List[float], List[float]]:
        samples = self._buffer.get_samples()
        now_ts = time.time()
        cutoff_ts = now_ts - duration_seconds

        x_data: List[float] = []
        dl_data: List[float] = []
        ul_data: List[float] = []

        for s in samples:
            ts = s.timestamp.timestamp()
            if ts >= cutoff_ts:
                x_data.append(ts)
                dl_data.append(s.download_bps)
                ul_data.append(s.upload_bps)

        return x_data, dl_data, ul_data


class HistoricalNetworkDataProvider:
    """Feeds historical network statistics from SQLite via StatsRepository."""

    def __init__(self, repository: StatsRepository, network_id: str) -> None:
        self._repo = repository
        self._network_id = network_id

    def set_network_id(self, network_id: str) -> None:
        """Switch active target network ID."""
        self._network_id = network_id

    def get_series(
        self, duration_seconds: int
    ) -> Tuple[List[float], List[float], List[float]]:
        # Map duration to hours/days
        hours = max(1, duration_seconds // 3600)
        records = self._repo.get_network_hourly_records(self._network_id, limit=hours)

        x_data: List[float] = []
        dl_data: List[float] = []
        ul_data: List[float] = []

        for r in records:
            try:
                # ISO-8601 UTC string: "2026-09-18T00:00:00Z"
                dt = datetime.fromisoformat(r.hour_timestamp.replace("Z", "+00:00"))
                ts = dt.timestamp()
                x_data.append(ts)
                # Convert hourly bytes to average bps (bytes / 3600)
                dl_data.append(r.download_bytes / 3600.0)
                ul_data.append(r.upload_bytes / 3600.0)
            except Exception:
                continue

        return x_data, dl_data, ul_data
