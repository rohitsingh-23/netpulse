"""Background network monitoring engine.

Samples psutil network counters on a background thread, computes speed
via SpeedCalculator, stores samples in a DataBuffer, and notifies
subscribers.

UI components subscribe to receive NetworkSample objects — they never
call psutil directly. Callback exceptions are caught and logged so a
misbehaving subscriber cannot crash the monitor loop.

Interface handling:
    Phase 1 uses system-wide counters (``psutil.net_io_counters()``).
    The architecture accepts an optional interface parameter so
    per-interface monitoring can be introduced in a later phase.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Optional

import psutil

from netpulse.core.data_buffer import DataBuffer
from netpulse.core.network_sample import NetworkSample
from netpulse.core.speed_calculator import CounterSnapshot, SpeedCalculator
from netpulse.utils.constants import (
    DEFAULT_BUFFER_DURATION,
    DEFAULT_SAMPLE_INTERVAL,
    MAX_MEASUREMENT_GAP,
)
from netpulse.utils.log import get_logger

if TYPE_CHECKING:
    from netpulse.hardware.context_manager import NetworkContextManager

logger = get_logger("network_monitor")

SampleCallback = Callable[[NetworkSample], None]


class NetworkMonitor:
    """Background network monitoring engine.

    Lifecycle::

        monitor = NetworkMonitor()
        monitor.subscribe(on_sample)
        monitor.start()
        ...
        monitor.stop()

    Args:
        interval: Seconds between samples.
        buffer_duration: Rolling buffer max age in seconds.
        max_measurement_gap: Seconds — discard measurement if gap exceeds this.
        context_manager: Optional NetworkContextManager for interface & network awareness.
    """

    def __init__(
        self,
        interval: float = DEFAULT_SAMPLE_INTERVAL,
        buffer_duration: int = DEFAULT_BUFFER_DURATION,
        max_measurement_gap: float = MAX_MEASUREMENT_GAP,
        context_manager: Optional[NetworkContextManager] = None,
    ) -> None:
        self._interval = interval
        self._max_measurement_gap = max_measurement_gap
        self._context_manager = context_manager
        self._calculator = SpeedCalculator(max_measurement_gap=max_measurement_gap)
        self._buffer = DataBuffer(max_duration=buffer_duration)

        self._subscribers: list[SampleCallback] = []
        self._subscribers_lock = threading.Lock()

        self._previous: Optional[CounterSnapshot] = None
        self._active_bsd: Optional[str] = None
        self._active_net_id: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Session statistics — accumulated bytes from valid samples.
        # Survives stop/start cycles (interval changes).
        self._session_downloaded: int = 0
        self._session_uploaded: int = 0
        self._session_start_time: datetime = datetime.now(timezone.utc)
        self._session_peak_download: float = 0.0
        self._session_peak_upload: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        """Whether the monitor loop is active."""
        return self._running

    @property
    def buffer(self) -> DataBuffer:
        """The rolling sample buffer."""
        return self._buffer

    @property
    def interval(self) -> float:
        """Current sampling interval in seconds."""
        return self._interval

    @property
    def session_downloaded(self) -> int:
        """Total bytes downloaded during this session."""
        return self._session_downloaded

    @property
    def session_uploaded(self) -> int:
        """Total bytes uploaded during this session."""
        return self._session_uploaded

    @property
    def session_start_time(self) -> datetime:
        """UTC timestamp when the session began."""
        return self._session_start_time

    @property
    def session_peak_download(self) -> float:
        """Peak download speed in bytes/sec seen during this session."""
        return self._session_peak_download

    @property
    def session_peak_upload(self) -> float:
        """Peak upload speed in bytes/sec seen during this session."""
        return self._session_peak_upload

    def subscribe(self, callback: SampleCallback) -> None:
        """Register a callback to receive ``NetworkSample`` each cycle."""
        with self._subscribers_lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: SampleCallback) -> None:
        """Remove a previously registered callback."""
        with self._subscribers_lock:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

    def set_interval(self, seconds: float) -> None:
        """Change the sampling interval.

        If the monitor is running, it is safely stopped and restarted
        with the new interval. Subscribers and session statistics are
        preserved. The SpeedCalculator's max_measurement_gap is scaled
        to ``max(original_gap, seconds * 10)`` so that the gap
        threshold remains sensible for the new interval.
        """
        if seconds <= 0:
            logger.warning("Invalid interval: %.2f, ignoring", seconds)
            return
        was_running = self._running
        if was_running:
            self.stop()
        self._interval = seconds
        self._calculator = SpeedCalculator(
            max_measurement_gap=max(self._max_measurement_gap, seconds * 10)
        )
        if was_running:
            self.start()
        logger.info("Sampling interval changed to %.1fs", seconds)

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            logger.warning("Monitor already running")
            return

        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="NetPulse-Monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("Network monitor started (interval=%.1fs)", self._interval)

    def stop(self) -> None:
        """Stop monitoring and wait for the thread to finish."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._thread is not None:
            self._thread.join(timeout=self._interval * 3)
            self._thread = None

        self._previous = None
        logger.info("Network monitor stopped")

    def reset_accounting(self) -> None:
        """Reset cumulative byte baselines, session counters, and rolling buffer.

        Critical for reset safety: ensures next sample establishes a clean
        baseline without computing a massive delta spike from prior counters.
        """
        self._previous = None
        self._active_bsd = None
        self._active_net_id = None
        self._session_downloaded = 0
        self._session_uploaded = 0
        self._session_start_time = datetime.now(timezone.utc)
        self._session_peak_download = 0.0
        self._session_peak_upload = 0.0
        self._buffer.clear()
        logger.info("NetworkMonitor accounting, baseline, and session metrics reset")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """Main loop — runs in background thread."""
        logger.debug("Monitor loop entered")

        while not self._stop_event.is_set():
            try:
                self._sample()
            except Exception:
                logger.exception("Error during network sampling")

            self._stop_event.wait(timeout=self._interval)

        logger.debug("Monitor loop exited")

    def _sample(self) -> None:
        """Take one counter reading, compute speed, notify subscribers."""
        current_bsd = None
        current_net_id = None
        current_iface_id = None

        if self._context_manager is not None:
            try:
                ctx = self._context_manager.current_context
                if ctx.is_connected:
                    current_bsd = ctx.interface.bsd_name
                    current_net_id = ctx.network.network_id
                    current_iface_id = ctx.interface.interface_id
            except Exception:
                logger.debug("Error reading current network context")

        # Detect interface or network transition to reset speed baseline
        if (current_bsd, current_net_id) != (self._active_bsd, self._active_net_id):
            if self._active_bsd is not None or self._active_net_id is not None:
                logger.info(
                    "Network connection changed: (%s, %s) -> (%s, %s), resetting speed baseline",
                    self._active_bsd, self._active_net_id, current_bsd, current_net_id
                )
            self._previous = None
            self._active_bsd = current_bsd
            self._active_net_id = current_net_id

        # Determine counters (prefer per-interface if available, fallback to global)
        counters = None
        if current_bsd:
            try:
                pernic = psutil.net_io_counters(pernic=True)
                if pernic and current_bsd in pernic:
                    counters = pernic[current_bsd]
            except Exception:
                pass

        if counters is None:
            counters = psutil.net_io_counters()

        if counters is None:
            logger.debug("psutil returned no counters")
            self._previous = None
            return

        current = CounterSnapshot(
            monotonic_time=time.monotonic(),
            bytes_received=counters.bytes_recv,
            bytes_sent=counters.bytes_sent,
        )

        if self._previous is None:
            # First sample — establish baseline, no speed yet
            self._previous = current
            return

        result = self._calculator.calculate(self._previous, current)
        self._previous = current  # always update baseline

        if result is None:
            # Counter reset or sleep/wake — baseline updated, skip this cycle
            return

        # Accumulate session statistics from valid deltas
        self._session_downloaded += int(result.download_bps * result.elapsed)
        self._session_uploaded += int(result.upload_bps * result.elapsed)
        if result.download_bps > self._session_peak_download:
            self._session_peak_download = result.download_bps
        if result.upload_bps > self._session_peak_upload:
            self._session_peak_upload = result.upload_bps

        sample = NetworkSample(
            timestamp=datetime.now(timezone.utc),
            download_bps=result.download_bps,
            upload_bps=result.upload_bps,
            total_download_bytes=current.bytes_received,
            total_upload_bytes=current.bytes_sent,
            interface=current_bsd,
            network_id=current_net_id,
            interface_id=current_iface_id,
        )

        self._buffer.append(sample)
        self._notify_subscribers(sample)

    def _notify_subscribers(self, sample: NetworkSample) -> None:
        """Dispatch sample to subscribers. Failures are logged, never propagated."""
        with self._subscribers_lock:
            subscribers = list(self._subscribers)

        for callback in subscribers:
            try:
                callback(sample)
            except Exception:
                logger.exception(
                    "Subscriber callback %s raised an exception",
                    getattr(callback, "__name__", repr(callback)),
                )
