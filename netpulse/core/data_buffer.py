"""Thread-safe rolling data buffer for live network samples.

Uses a deque internally. Eviction is timestamp-based — samples older
than ``max_duration`` seconds are removed on every append and read.
This keeps the buffer bounded without relying on a fixed item count.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from netpulse.core.network_sample import NetworkSample
from netpulse.utils.constants import DEFAULT_BUFFER_DURATION


class DataBuffer:
    """Thread-safe rolling buffer of ``NetworkSample`` objects.

    Args:
        max_duration: Maximum age of retained samples in seconds.
    """

    def __init__(self, max_duration: int = DEFAULT_BUFFER_DURATION) -> None:
        self._max_duration = max_duration
        self._samples: deque[NetworkSample] = deque()
        self._lock = threading.Lock()

    @property
    def max_duration(self) -> int:
        """Maximum sample age in seconds."""
        return self._max_duration

    def append(self, sample: NetworkSample) -> None:
        """Add a sample and evict expired entries."""
        with self._lock:
            self._samples.append(sample)
            self._evict()

    def get_samples(self) -> list[NetworkSample]:
        """Return a *copy* of all current samples (oldest first)."""
        with self._lock:
            self._evict()
            return list(self._samples)

    def latest(self) -> Optional[NetworkSample]:
        """Return the most recent sample, or ``None`` if empty."""
        with self._lock:
            return self._samples[-1] if self._samples else None

    def clear(self) -> None:
        """Remove all samples."""
        with self._lock:
            self._samples.clear()

    def __len__(self) -> int:
        """Current number of samples (after eviction on next access)."""
        with self._lock:
            return len(self._samples)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict(self) -> None:
        """Remove samples older than max_duration. Caller must hold lock."""
        if not self._samples:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._max_duration)
        while self._samples and self._samples[0].timestamp < cutoff:
            self._samples.popleft()
