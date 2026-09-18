"""Session statistics page for the NetPulse Dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from netpulse.ui.metrics import calculate_session_metrics, format_duration
from netpulse.ui.widgets import CardContainer, MetricCard
from netpulse.utils.formatters import format_bytes, format_speed

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.core.network_sample import NetworkSample


class SessionPage(QWidget):
    """Session traffic statistics, elapsed time, and peaks."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        monitor: NetworkMonitor,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._monitor = monitor

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Notice banner
        banner = CardContainer()
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        notice_label = QLabel("ℹ Statistics reset when NetPulse restarts. Historical persistence is not yet stored.")
        notice_label.setStyleSheet("color: gray; font-size: 11px;")
        banner_layout.addWidget(notice_label)
        layout.addWidget(banner)

        # 2. Session Traffic Total Cards (Downloaded, Uploaded, Total)
        totals_grid = QGridLayout()
        totals_grid.setSpacing(12)

        self._card_dl = MetricCard("Session Downloaded", "0 B", value_color="#007AFF")
        self._card_ul = MetricCard("Session Uploaded", "0 B", value_color="#34C759")
        self._card_total = MetricCard("Total Transferred", "0 B")

        totals_grid.addWidget(self._card_dl, 0, 0)
        totals_grid.addWidget(self._card_ul, 0, 1)
        totals_grid.addWidget(self._card_total, 0, 2)

        layout.addLayout(totals_grid)

        # 3. Session Details Card
        details_card = CardContainer()
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(20, 18, 20, 18)
        details_layout.setSpacing(12)

        card_title = QLabel("SESSION METRICS")
        font_title = QFont()
        font_title.setPointSize(11)
        font_title.setWeight(QFont.Weight.Bold)
        card_title.setFont(font_title)
        card_title.setStyleSheet("color: gray; letter-spacing: 0.5px;")
        details_layout.addWidget(card_title)

        grid = QGridLayout()
        grid.setSpacing(10)

        # Rows
        self._lbl_started = QLabel("—")
        self._lbl_elapsed = QLabel("0s")
        self._lbl_current_speed = QLabel("↓ 0 B/s  •  ↑ 0 B/s")
        self._lbl_peaks = QLabel("↓ 0 B/s  •  ↑ 0 B/s")

        font_val = QFont()
        font_val.setPointSize(12)
        font_val.setWeight(QFont.Weight.Medium)
        for lbl in (self._lbl_started, self._lbl_elapsed, self._lbl_current_speed, self._lbl_peaks):
            lbl.setFont(font_val)

        grid.addWidget(self._create_field_label("Session Started:"), 0, 0)
        grid.addWidget(self._lbl_started, 0, 1)

        grid.addWidget(self._create_field_label("Elapsed Duration:"), 1, 0)
        grid.addWidget(self._lbl_elapsed, 1, 1)

        grid.addWidget(self._create_field_label("Current Speeds:"), 2, 0)
        grid.addWidget(self._lbl_current_speed, 2, 1)

        grid.addWidget(self._create_field_label("Session Peaks:"), 3, 0)
        grid.addWidget(self._lbl_peaks, 3, 1)

        details_layout.addLayout(grid)
        layout.addWidget(details_card)
        layout.addStretch(1)

    def _create_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: gray; font-size: 12px;")
        return lbl

    def on_sample_received(self, sample: NetworkSample) -> None:
        """Update session statistics."""
        unit_str = self._prefs.preferences.unit_mode.value
        unit_arg = "auto" if unit_str == "auto" else unit_str

        metrics = calculate_session_metrics(self._monitor, sample)

        # Update total cards
        self._card_dl.set_value(format_bytes(metrics.downloaded_bytes))
        self._card_ul.set_value(format_bytes(metrics.uploaded_bytes))
        self._card_total.set_value(format_bytes(metrics.total_bytes))

        # Update metadata fields
        local_start = metrics.session_start.astimezone()
        self._lbl_started.setText(local_start.strftime("%Y-%m-%d %I:%M:%S %p"))
        self._lbl_elapsed.setText(format_duration(metrics.elapsed_seconds))

        cur_dl_str = format_speed(metrics.current_download_bps, unit=unit_arg)
        cur_ul_str = format_speed(metrics.current_upload_bps, unit=unit_arg)
        self._lbl_current_speed.setText(f"↓ {cur_dl_str}   •   ↑ {cur_ul_str}")

        peak_dl_str = format_speed(metrics.peak_download_bps, unit=unit_arg)
        peak_ul_str = format_speed(metrics.peak_upload_bps, unit=unit_arg)
        self._lbl_peaks.setText(f"↓ {peak_dl_str}   •   ↑ {peak_ul_str}")

    def refresh_after_reset(self) -> None:
        """Reset session metric cards and labels immediately after reset."""
        unit_str = self._prefs.preferences.unit_mode.value
        unit_arg = "auto" if unit_str == "auto" else unit_str

        self._card_dl.set_value(format_bytes(0))
        self._card_ul.set_value(format_bytes(0))
        self._card_total.set_value(format_bytes(0))

        local_start = self._monitor.session_start_time.astimezone()
        self._lbl_started.setText(local_start.strftime("%Y-%m-%d %I:%M:%S %p"))
        self._lbl_elapsed.setText("0s")

        zero_speed = format_speed(0.0, unit=unit_arg)
        self._lbl_current_speed.setText(f"↓ {zero_speed}   •   ↑ {zero_speed}")
        self._lbl_peaks.setText(f"↓ {zero_speed}   •   ↑ {zero_speed}")
