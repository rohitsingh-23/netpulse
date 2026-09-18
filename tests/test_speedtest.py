"""Tests for NetPulse Speed Test engine, state transitions, and UI components."""

from __future__ import annotations

import socket
import time
import urllib.error
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from netpulse.config.preferences import PreferencesManager
from netpulse.core.network_monitor import NetworkMonitor
from netpulse.speedtest.engine import SpeedTestEngine
from netpulse.speedtest.models import (
    SpeedTestProgress,
    SpeedTestResult,
    SpeedTestStage,
)
from netpulse.ui.speedtest import SpeedTestPage


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def speedtest_page(qapp: QApplication) -> SpeedTestPage:
    prefs = PreferencesManager()
    return SpeedTestPage(prefs_manager=prefs)


def test_speed_test_engine_initial_state():
    engine = SpeedTestEngine()
    assert not engine.is_running
    assert not engine._cancel_requested


def test_speed_test_engine_concurrent_prevention():
    engine = SpeedTestEngine()
    engine._is_running = True

    on_progress = MagicMock()
    on_complete = MagicMock()
    on_error = MagicMock()

    started = engine.start_test(on_progress, on_complete, on_error)
    assert started is False


def test_speed_test_engine_cancellation():
    engine = SpeedTestEngine()
    engine._is_running = True
    engine.cancel()
    assert engine._cancel_requested is True


def test_speed_test_engine_error_formatting():
    engine = SpeedTestEngine()

    timeout_err = socket.timeout("timed out")
    assert "timed out" in engine._format_error(timeout_err).lower()

    dns_err = socket.gaierror(8, "nodename nor servname provided, or not known")
    assert "DNS" in engine._format_error(dns_err)

    url_dns_err = urllib.error.URLError("nodename nor servname provided")
    assert "DNS failure" in engine._format_error(url_dns_err)

    conn_err = ConnectionResetError("Connection reset by peer")
    assert "interrupted" in engine._format_error(conn_err).lower()


def test_speed_test_engine_successful_flow():
    engine = SpeedTestEngine()
    progress_updates = []
    completion_results = []
    errors = []

    # Mock response that produces bytes on read()
    class MockResponse:
        def __init__(self, url):
            self.url = url
            self._read_count = 0

        def read(self, amt=None):
            if "bytes=0" in self.url or "/__up" in self.url:
                return b""
            # download test
            if self._read_count == 0:
                self._read_count += 1
                return b"x" * 65536
            return b""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        return MockResponse(url)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        started = engine.start_test(
            on_progress=lambda p: progress_updates.append(p),
            on_complete=lambda r: completion_results.append(r),
            on_error=lambda e: errors.append(e),
        )
        assert started is True

        # Wait for worker thread to complete
        if engine._thread:
            engine._thread.join(timeout=5.0)

    assert len(errors) == 0
    assert len(completion_results) == 1
    res = completion_results[0]
    assert isinstance(res, SpeedTestResult)
    assert res.download_mbps >= 0.0
    assert res.upload_mbps >= 0.0
    assert res.latency_ms >= 0.0
    assert res.server_location == "Cloudflare Edge"


def test_speed_test_page_initial_ui(speedtest_page: SpeedTestPage):
    assert speedtest_page._btn_start.text() == "Start Test"
    assert speedtest_page._btn_start.isEnabled() is True
    assert speedtest_page._btn_cancel.isHidden() is True
    assert speedtest_page._card_dl._value_label.text() == "-- Mbps"
    assert speedtest_page._card_ul._value_label.text() == "-- Mbps"
    assert speedtest_page._card_ping._value_label.text() == "-- ms"
    assert speedtest_page._card_jitter._value_label.text() == "-- ms"
    assert speedtest_page._card_loss._value_label.text() == "Unavailable"


def test_speed_test_page_progress_and_complete_ui(speedtest_page: SpeedTestPage):
    # Simulate progress update
    prog = SpeedTestProgress(
        stage=SpeedTestStage.TESTING_DOWNLOAD,
        message="Testing download (85.2 Mbps)...",
        current_speed_mbps=85.2,
        percent=0.5,
    )
    speedtest_page._on_engine_progress(prog)
    assert speedtest_page._lbl_status.text() == "Testing download (85.2 Mbps)..."
    assert speedtest_page._card_dl._value_label.text() == "85.2 Mbps"

    # Simulate completion
    result = SpeedTestResult(
        timestamp=datetime.now(timezone.utc),
        download_mbps=95.4,
        upload_mbps=22.1,
        latency_ms=18.5,
        jitter_ms=2.1,
        packet_loss_pct=None,
    )
    speedtest_page._on_engine_complete(result)
    assert speedtest_page._card_dl._value_label.text() == "95.4 Mbps"
    assert speedtest_page._card_ul._value_label.text() == "22.1 Mbps"
    assert speedtest_page._card_ping._value_label.text() == "18.5 ms"
    assert speedtest_page._card_jitter._value_label.text() == "2.1 ms"
    assert speedtest_page._card_loss._value_label.text() == "Unavailable"
    assert "Tested at" in speedtest_page._lbl_time.text()
    assert speedtest_page._btn_start.isEnabled() is True
    assert speedtest_page._btn_cancel.isHidden() is True


def test_speed_test_page_error_ui(speedtest_page: SpeedTestPage):
    speedtest_page._on_engine_error("DNS failure. No internet connection detected.")
    assert "DNS failure" in speedtest_page._lbl_status.text()
    assert speedtest_page._btn_start.isEnabled() is True
    assert speedtest_page._btn_cancel.isHidden() is True


def test_speed_test_traffic_does_not_modify_monitor_accounting():
    monitor = NetworkMonitor()
    assert not hasattr(monitor, "speedtest")

    engine = SpeedTestEngine()
    # SpeedTestEngine is completely isolated with no reference to NetworkMonitor or DataBuffer
    assert not hasattr(engine, "_monitor")
    assert not hasattr(engine, "_buffer")
    assert not hasattr(engine, "_db")
