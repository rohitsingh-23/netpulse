"""Speed Test dashboard page for measuring internet bandwidth, ping, and jitter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from netpulse.speedtest.engine import SpeedTestEngine
from netpulse.speedtest.models import (
    SpeedTestProgress,
    SpeedTestResult,
    SpeedTestStage,
)
from netpulse.ui.widgets import CardContainer, MetricCard

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager


class _SpeedTestBridge(QObject):
    """Bridge Qt signals from the background worker thread onto the main UI thread."""

    progress_signal = Signal(object)
    complete_signal = Signal(object)
    error_signal = Signal(str)


class SpeedTestPage(QWidget):
    """Clean macOS-styled Speed Test view in the NetPulse Dashboard."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._engine = SpeedTestEngine()

        self._bridge = _SpeedTestBridge()
        self._bridge.progress_signal.connect(self._on_engine_progress)
        self._bridge.complete_signal.connect(self._on_engine_complete)
        self._bridge.error_signal.connect(self._on_engine_error)

        self._last_result: Optional[SpeedTestResult] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header & Action Card
        header_card = CardContainer()
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        title_lbl = QLabel("Speed Test")
        font_title = QFont()
        font_title.setPointSize(16)
        font_title.setWeight(QFont.Weight.Bold)
        title_lbl.setFont(font_title)
        title_col.addWidget(title_lbl)

        desc_lbl = QLabel("Test your current internet connection bandwidth and latency.")
        desc_lbl.setStyleSheet("color: gray; font-size: 12px;")
        title_col.addWidget(desc_lbl)

        title_row.addLayout(title_col)
        title_row.addStretch()

        # Action Buttons
        self._btn_start = QPushButton("Start Test")
        self._btn_start.setFixedWidth(120)
        self._btn_start.setFixedHeight(34)
        self._btn_start.setStyleSheet(
            "QPushButton { background-color: #007AFF; color: white; border: none; "
            "border-radius: 6px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #0069D9; }"
            "QPushButton:disabled { background-color: rgba(140, 140, 145, 0.3); color: #8E8E93; }"
        )
        self._btn_start.clicked.connect(self._start_test)
        title_row.addWidget(self._btn_start)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setFixedWidth(80)
        self._btn_cancel.setFixedHeight(34)
        self._btn_cancel.setStyleSheet(
            "QPushButton { background-color: rgba(255, 59, 48, 0.15); color: #FF3B30; "
            "border: 1px solid rgba(255, 59, 48, 0.3); border-radius: 6px; font-weight: 500; font-size: 12px; }"
            "QPushButton:hover { background-color: rgba(255, 59, 48, 0.25); }"
        )
        self._btn_cancel.clicked.connect(self._cancel_test)
        self._btn_cancel.hide()
        title_row.addWidget(self._btn_cancel)

        header_layout.addLayout(title_row)

        # Progress bar and status row
        self._status_box = QWidget()
        status_layout = QVBoxLayout(self._status_box)
        status_layout.setContentsMargins(0, 4, 0, 0)
        status_layout.setSpacing(6)

        self._lbl_status = QLabel("Speed tests use network bandwidth.")
        self._lbl_status.setStyleSheet("color: #8E8E93; font-size: 11px;")
        status_layout.addWidget(self._lbl_status)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(140, 140, 145, 0.2);
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #007AFF;
                border-radius: 3px;
            }
        """)
        self._progress_bar.hide()
        status_layout.addWidget(self._progress_bar)

        header_layout.addWidget(self._status_box)
        layout.addWidget(header_card)

        # 2. Prominent Results Grid
        results_grid = QGridLayout()
        results_grid.setSpacing(12)

        self._card_dl = MetricCard("Download", "-- Mbps", value_color="#007AFF", prominent=True)
        self._card_ul = MetricCard("Upload", "-- Mbps", value_color="#34C759", prominent=True)
        self._card_ping = MetricCard("Ping", "-- ms")
        self._card_jitter = MetricCard("Jitter", "-- ms")
        self._card_loss = MetricCard("Packet Loss", "Unavailable")

        results_grid.addWidget(self._card_dl, 0, 0)
        results_grid.addWidget(self._card_ul, 0, 1)
        results_grid.addWidget(self._card_ping, 1, 0)
        results_grid.addWidget(self._card_jitter, 1, 1)
        results_grid.addWidget(self._card_loss, 1, 2)

        layout.addLayout(results_grid)

        # 3. Details / Metadata Card
        meta_card = CardContainer()
        meta_layout = QVBoxLayout(meta_card)
        meta_layout.setContentsMargins(20, 16, 20, 16)
        meta_layout.setSpacing(10)

        meta_title = QLabel("TEST DETAILS")
        font_mtitle = QFont()
        font_mtitle.setPointSize(11)
        font_mtitle.setWeight(QFont.Weight.Bold)
        meta_title.setFont(font_mtitle)
        meta_title.setStyleSheet("color: gray; letter-spacing: 0.5px;")
        meta_layout.addWidget(meta_title)

        grid_meta = QGridLayout()
        grid_meta.setSpacing(8)

        lbl_s_title = QLabel("Server:")
        lbl_s_title.setStyleSheet("color: gray; font-size: 11px;")
        self._lbl_server = QLabel("Cloudflare Edge (HTTPS)")
        self._lbl_server.setStyleSheet("font-weight: 500; font-size: 12px;")

        lbl_t_title = QLabel("Completed:")
        lbl_t_title.setStyleSheet("color: gray; font-size: 11px;")
        self._lbl_time = QLabel("Not tested yet")
        self._lbl_time.setStyleSheet("font-weight: 500; font-size: 12px;")

        grid_meta.addWidget(lbl_s_title, 0, 0)
        grid_meta.addWidget(self._lbl_server, 0, 1)
        grid_meta.addWidget(lbl_t_title, 1, 0)
        grid_meta.addWidget(self._lbl_time, 1, 1)

        meta_layout.addLayout(grid_meta)
        layout.addWidget(meta_card)
        layout.addStretch(1)

    def _start_test(self) -> None:
        """User initiates speed test."""
        if self._engine.is_running:
            return

        self._btn_start.setEnabled(False)
        self._btn_start.setText("Testing...")
        self._btn_cancel.show()
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._lbl_status.setText("Finding server...")
        self._lbl_status.setStyleSheet("color: #007AFF; font-size: 11px; font-weight: 500;")

        # Reset displayed results to testing placeholders
        self._card_dl.set_value("-- Mbps")
        self._card_ul.set_value("-- Mbps")
        self._card_ping.set_value("-- ms")
        self._card_jitter.set_value("-- ms")
        self._card_loss.set_value("Unavailable")

        self._engine.start_test(
            on_progress=self._bridge.progress_signal.emit,
            on_complete=self._bridge.complete_signal.emit,
            on_error=self._bridge.error_signal.emit,
        )

    def _cancel_test(self) -> None:
        """User cancels active speed test."""
        self._lbl_status.setText("Cancelling test...")
        self._engine.cancel()

    def _on_engine_progress(self, progress: SpeedTestProgress) -> None:
        """Handle progress signal emitted on UI thread."""
        self._lbl_status.setText(progress.message)
        pct = int(progress.percent * 100)
        self._progress_bar.setValue(pct)

        if progress.current_speed_mbps is not None:
            if progress.stage == SpeedTestStage.TESTING_DOWNLOAD:
                self._card_dl.set_value(f"{progress.current_speed_mbps:.1f} Mbps")
            elif progress.stage == SpeedTestStage.TESTING_UPLOAD:
                self._card_ul.set_value(f"{progress.current_speed_mbps:.1f} Mbps")

        if progress.stage == SpeedTestStage.CANCELLED:
            self._reset_ui_after_test(status_text="Speed test cancelled.", is_error=False)

    def _on_engine_complete(self, result: SpeedTestResult) -> None:
        """Handle completion signal on UI thread."""
        self._last_result = result
        self._card_dl.set_value(f"{result.download_mbps:.1f} Mbps")
        self._card_ul.set_value(f"{result.upload_mbps:.1f} Mbps")
        self._card_ping.set_value(f"{result.latency_ms:.1f} ms")
        self._card_jitter.set_value(f"{result.jitter_ms:.1f} ms")
        if result.packet_loss_pct is not None:
            self._card_loss.set_value(f"{result.packet_loss_pct:.1f}%")
        else:
            self._card_loss.set_value("Unavailable")

        local_time = result.timestamp.astimezone()
        time_str = local_time.strftime("%I:%M %p")
        self._lbl_time.setText(f"Tested at {time_str}")

        self._reset_ui_after_test(status_text=f"Test complete. Tested at {time_str}", is_error=False)

    def _on_engine_error(self, error_msg: str) -> None:
        """Handle error signal on UI thread."""
        self._reset_ui_after_test(status_text=error_msg, is_error=True)

    def _reset_ui_after_test(self, status_text: str, is_error: bool) -> None:
        """Restore button states and finalize progress display."""
        self._btn_start.setEnabled(True)
        self._btn_start.setText("Start Test")
        self._btn_cancel.hide()
        self._progress_bar.hide()
        self._progress_bar.setValue(0)
        self._lbl_status.setText(status_text)
        if is_error:
            self._lbl_status.setStyleSheet("color: #FF3B30; font-size: 11px; font-weight: 500;")
        else:
            self._lbl_status.setStyleSheet("color: #8E8E93; font-size: 11px;")
