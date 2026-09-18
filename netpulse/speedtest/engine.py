"""Dedicated HTTPS-based internet speed test service using Cloudflare edge endpoints.

Completely independent of NetworkMonitor and live bandwidth accounting.
Executes only upon user request in a separate background thread with cancellation support.
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable, List, Optional

from netpulse.speedtest.models import (
    SpeedTestProgress,
    SpeedTestResult,
    SpeedTestStage,
)
from netpulse.utils.log import get_logger

logger = get_logger("speedtest")

# Cloudflare Speed Test Endpoints (HTTPS, public, keyless)
BASE_URL = "https://speed.cloudflare.com"
PING_URL = f"{BASE_URL}/__down?bytes=0"
DOWN_URL = f"{BASE_URL}/__down"
UP_URL = f"{BASE_URL}/__up"
USER_AGENT = "NetPulse/0.7.0 (macOS; NetworkAnalytics)"


class SpeedTestEngine:
    """Performs HTTP-based speed test measurements safely without external dependencies."""

    def __init__(self) -> None:
        self._is_running: bool = False
        self._cancel_requested: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def cancel(self) -> None:
        """Signal the running speed test to cancel safely."""
        with self._lock:
            if self._is_running:
                self._cancel_requested = True
                logger.info("Speed test cancellation requested")

    def start_test(
        self,
        on_progress: Callable[[SpeedTestProgress], None],
        on_complete: Callable[[SpeedTestResult], None],
        on_error: Callable[[str], None],
    ) -> bool:
        """Start a speed test asynchronously. Returns False if a test is already running."""
        with self._lock:
            if self._is_running:
                return False
            self._is_running = True
            self._cancel_requested = False

        def _worker() -> None:
            try:
                result = self._run_test(on_progress)
                if result is not None:
                    on_complete(result)
            except Exception as exc:
                if self._cancel_requested:
                    logger.info("Speed test cancelled by user")
                    on_progress(
                        SpeedTestProgress(
                            stage=SpeedTestStage.CANCELLED,
                            message="Test cancelled",
                            percent=0.0,
                        )
                    )
                else:
                    err_msg = self._format_error(exc)
                    logger.error("Speed test failed: %s", err_msg, exc_info=True)
                    on_error(err_msg)
            finally:
                with self._lock:
                    self._is_running = False
                    self._cancel_requested = False

        self._thread = threading.Thread(target=_worker, name="SpeedTestWorker", daemon=True)
        self._thread.start()
        return True

    def _format_error(self, exc: Exception) -> str:
        if isinstance(exc, (socket.timeout, urllib.error.URLError)) and "timed out" in str(exc).lower():
            return "Connection timed out. Please check your network."
        if isinstance(exc, urllib.error.URLError):
            reason = str(exc.reason)
            if "nodename nor servname provided" in reason or "name resolution" in reason.lower():
                return "DNS failure. No internet connection detected."
            return f"Network error: {reason}"
        if isinstance(exc, socket.gaierror):
            return "DNS failure. Could not reach test server."
        if isinstance(exc, ConnectionError):
            return "Connection interrupted. Please verify your internet connection."
        return f"Test failed: {str(exc)}"

    def _run_test(
        self,
        on_progress: Callable[[SpeedTestProgress], None],
    ) -> Optional[SpeedTestResult]:
        """Core execution logic run inside worker thread."""

        # 1. Finding server / connection check
        on_progress(
            SpeedTestProgress(
                stage=SpeedTestStage.FINDING_SERVER,
                message="Finding server...",
                percent=0.05,
            )
        )
        if self._cancel_requested:
            return None

        # Verify reachability with a fast head/get request
        req = urllib.request.Request(PING_URL, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                resp.read()
        except Exception as e:
            if self._cancel_requested:
                return None
            raise e

        # 2. Testing latency & jitter (10 samples)
        on_progress(
            SpeedTestProgress(
                stage=SpeedTestStage.TESTING_LATENCY,
                message="Testing latency...",
                percent=0.15,
            )
        )

        ping_samples: List[float] = []
        for i in range(8):
            if self._cancel_requested:
                return None
            t0 = time.perf_counter()
            req = urllib.request.Request(PING_URL, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=4) as resp:
                resp.read()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            ping_samples.append(elapsed_ms)
            on_progress(
                SpeedTestProgress(
                    stage=SpeedTestStage.TESTING_LATENCY,
                    message="Testing latency...",
                    percent=0.15 + (i / 8.0) * 0.15,
                )
            )

        if not ping_samples:
            raise RuntimeError("Could not collect latency samples.")

        mean_latency = sum(ping_samples) / len(ping_samples)
        jitter = 0.0
        if len(ping_samples) > 1:
            diffs = [abs(ping_samples[i] - ping_samples[i - 1]) for i in range(1, len(ping_samples))]
            jitter = sum(diffs) / len(diffs)

        # 3. Testing download speed (multi-tiered payload: 5MB -> 10MB -> 15MB)
        on_progress(
            SpeedTestProgress(
                stage=SpeedTestStage.TESTING_DOWNLOAD,
                message="Testing download...",
                percent=0.30,
            )
        )

        dl_sizes = [2_000_000, 5_000_000, 10_000_000]
        total_dl_bytes = 0
        total_dl_time = 0.0

        for idx, size in enumerate(dl_sizes):
            if self._cancel_requested:
                return None
            url = f"{DOWN_URL}?bytes={size}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=12) as resp:
                chunk_len = 0
                while True:
                    if self._cancel_requested:
                        return None
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    chunk_len += len(chunk)
            dt = max(time.perf_counter() - t0, 0.001)
            total_dl_bytes += chunk_len
            total_dl_time += dt

            inst_mbps = (chunk_len * 8.0) / (dt * 1e6)
            progress_pct = 0.30 + ((idx + 1) / len(dl_sizes)) * 0.35
            on_progress(
                SpeedTestProgress(
                    stage=SpeedTestStage.TESTING_DOWNLOAD,
                    message=f"Testing download ({inst_mbps:.1f} Mbps)...",
                    current_speed_mbps=inst_mbps,
                    percent=progress_pct,
                )
            )

        dl_speed_mbps = (total_dl_bytes * 8.0) / (max(total_dl_time, 0.001) * 1e6)

        # 4. Testing upload speed (multi-tiered payload: 1MB -> 2MB -> 4MB)
        on_progress(
            SpeedTestProgress(
                stage=SpeedTestStage.TESTING_UPLOAD,
                message="Testing upload...",
                percent=0.65,
            )
        )

        up_sizes = [500_000, 1_500_000, 3_000_000]
        total_up_bytes = 0
        total_up_time = 0.0

        for idx, size in enumerate(up_sizes):
            if self._cancel_requested:
                return None
            payload = b"0" * size
            req = urllib.request.Request(
                UP_URL,
                data=payload,
                method="POST",
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/octet-stream",
                },
            )
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp.read()
            dt = max(time.perf_counter() - t0, 0.001)
            total_up_bytes += len(payload)
            total_up_time += dt

            inst_mbps = (len(payload) * 8.0) / (dt * 1e6)
            progress_pct = 0.65 + ((idx + 1) / len(up_sizes)) * 0.35
            on_progress(
                SpeedTestProgress(
                    stage=SpeedTestStage.TESTING_UPLOAD,
                    message=f"Testing upload ({inst_mbps:.1f} Mbps)...",
                    current_speed_mbps=inst_mbps,
                    percent=progress_pct,
                )
            )

        up_speed_mbps = (total_up_bytes * 8.0) / (max(total_up_time, 0.001) * 1e6)

        if self._cancel_requested:
            return None

        on_progress(
            SpeedTestProgress(
                stage=SpeedTestStage.COMPLETED,
                message="Test complete",
                percent=1.0,
            )
        )

        return SpeedTestResult(
            timestamp=datetime.now(timezone.utc),
            download_mbps=round(dl_speed_mbps, 1),
            upload_mbps=round(up_speed_mbps, 1),
            latency_ms=round(mean_latency, 1),
            jitter_ms=round(jitter, 1),
            packet_loss_pct=None,  # Not reported over HTTP/TCP; displayed cleanly as Unavailable
            server_location="Cloudflare Edge",
        )
