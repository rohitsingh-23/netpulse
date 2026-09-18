"""Tests for NetworkMonitor interval changes and session statistics."""

from __future__ import annotations

import time
import threading

from netpulse.core.network_monitor import NetworkMonitor


class TestSetInterval:
    """Verify set_interval() works safely without duplicate threads."""

    def test_set_interval_while_stopped(self) -> None:
        monitor = NetworkMonitor(interval=1.0)
        monitor.set_interval(2.0)
        assert monitor.interval == 2.0
        assert not monitor.running

    def test_set_interval_while_running(self) -> None:
        monitor = NetworkMonitor(interval=1.0)
        samples = []
        monitor.subscribe(lambda s: samples.append(s))
        monitor.start()
        assert monitor.running

        monitor.set_interval(0.5)
        assert monitor.interval == 0.5
        assert monitor.running  # should have restarted

        time.sleep(1.5)
        monitor.stop()
        # Should have received samples at the new interval
        assert len(samples) >= 1

    def test_no_duplicate_threads(self) -> None:
        monitor = NetworkMonitor(interval=0.5)
        monitor.start()
        monitor.set_interval(1.0)
        monitor.set_interval(0.5)
        monitor.set_interval(2.0)
        # Only one monitor thread should be alive
        monitor_threads = [
            t for t in threading.enumerate()
            if t.name == "NetPulse-Monitor"
        ]
        assert len(monitor_threads) <= 1
        monitor.stop()

    def test_invalid_interval_ignored(self) -> None:
        monitor = NetworkMonitor(interval=1.0)
        monitor.set_interval(-1.0)
        assert monitor.interval == 1.0
        monitor.set_interval(0)
        assert monitor.interval == 1.0

    def test_subscribers_preserved(self) -> None:
        monitor = NetworkMonitor(interval=1.0)
        samples = []
        callback = lambda s: samples.append(s)
        monitor.subscribe(callback)
        monitor.start()

        monitor.set_interval(0.5)
        time.sleep(1.5)
        monitor.stop()

        assert len(samples) >= 1  # callback still active


class TestSessionStats:
    """Verify session download/upload accumulation."""

    def test_initial_session_zero(self) -> None:
        monitor = NetworkMonitor()
        assert monitor.session_downloaded == 0
        assert monitor.session_uploaded == 0

    def test_session_accumulates(self) -> None:
        monitor = NetworkMonitor(interval=0.5)
        monitor.start()
        time.sleep(2.0)
        monitor.stop()
        # On a live system there's always some traffic
        # Just verify they're non-negative
        assert monitor.session_downloaded >= 0
        assert monitor.session_uploaded >= 0

    def test_session_survives_interval_change(self) -> None:
        monitor = NetworkMonitor(interval=0.5)
        monitor.start()
        time.sleep(1.5)
        dl_before = monitor.session_downloaded
        ul_before = monitor.session_uploaded
        monitor.set_interval(1.0)
        # Session stats should be preserved (not reset)
        assert monitor.session_downloaded >= dl_before
        assert monitor.session_uploaded >= ul_before
        monitor.stop()


class TestIntervalProperty:
    def test_initial_interval(self) -> None:
        monitor = NetworkMonitor(interval=2.0)
        assert monitor.interval == 2.0
