"""Network speed calculation engine.

Pure, testable component that computes download/upload speeds from
sequential counter snapshots. Handles:

- Normal delta calculation
- Counter resets (negative deltas → return None, caller resets baseline)
- Sleep/wake detection (elapsed > max_measurement_gap → return None)
- Zero elapsed time (return None, avoids division by zero)

The caller (NetworkMonitor) is responsible for updating its baseline
when None is returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from netpulse.utils.constants import MAX_MEASUREMENT_GAP


@dataclass(frozen=True)
class CounterSnapshot:
    """Raw network counter reading from psutil.

    Attributes:
        monotonic_time: ``time.monotonic()`` when counters were read.
            Monotonic clock is used for elapsed-time calculations because
            it is immune to system clock adjustments.
        bytes_received: Cumulative bytes received since boot.
        bytes_sent: Cumulative bytes sent since boot.
    """

    monotonic_time: float
    bytes_received: int
    bytes_sent: int


@dataclass(frozen=True)
class SpeedResult:
    """Calculated network speeds for one measurement interval.

    Attributes:
        download_bps: Download speed in bytes per second.
        upload_bps: Upload speed in bytes per second.
        elapsed: Measurement interval in seconds.
    """

    download_bps: float
    upload_bps: float
    elapsed: float


class SpeedCalculator:
    """Computes network speed from two sequential counter snapshots.

    Args:
        max_measurement_gap: Maximum allowed seconds between measurements.
            Intervals exceeding this are treated as sleep/wake events and
            discarded to avoid computing a misleading average speed.
    """

    def __init__(self, max_measurement_gap: float = MAX_MEASUREMENT_GAP) -> None:
        self.max_measurement_gap = max_measurement_gap

    def calculate(
        self,
        previous: CounterSnapshot,
        current: CounterSnapshot,
    ) -> Optional[SpeedResult]:
        """Calculate speed between two counter snapshots.

        Returns ``None`` when the measurement should be discarded:
        - elapsed ≤ 0 (avoids division by zero)
        - elapsed > max_measurement_gap (sleep/wake)
        - either counter decreased (counter reset)

        Args:
            previous: Earlier counter reading.
            current: Later counter reading.

        Returns:
            SpeedResult with calculated speeds, or None.
        """
        elapsed = current.monotonic_time - previous.monotonic_time

        # Zero or negative elapsed — cannot calculate
        if elapsed <= 0:
            return None

        # Sleep/wake — gap too large for meaningful speed
        if elapsed > self.max_measurement_gap:
            return None

        dl_delta = current.bytes_received - previous.bytes_received
        ul_delta = current.bytes_sent - previous.bytes_sent

        # Counter reset — either counter went backwards
        if dl_delta < 0 or ul_delta < 0:
            return None

        return SpeedResult(
            download_bps=dl_delta / elapsed,
            upload_bps=ul_delta / elapsed,
            elapsed=elapsed,
        )
