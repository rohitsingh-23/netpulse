"""Overview page for the NetPulse Dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from netpulse.ui.graph import BandwidthGraph
from netpulse.ui.metrics import calculate_session_metrics
from netpulse.ui.widgets import MetricCard
from netpulse.utils.formatters import format_bytes, format_speed

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.data_buffer import DataBuffer
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.core.network_sample import NetworkSample


class OverviewPage(QWidget):
    """Network Overview page displaying primary metrics and live graph."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        monitor: NetworkMonitor,
        data_buffer: DataBuffer,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._monitor = monitor
        self._buffer = data_buffer

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Primary Metric Cards Grid (2 rows x 3 cols)
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)

        self._card_cur_dl = MetricCard("Current Download", "↓ 0 B/s", value_color="#007AFF", prominent=True)
        self._card_cur_ul = MetricCard("Current Upload", "↑ 0 B/s", value_color="#34C759", prominent=True)
        self._card_session_dl = MetricCard("Session Download", "0 B")
        self._card_session_ul = MetricCard("Session Upload", "0 B")
        self._card_peak_dl = MetricCard("Session Peak Download", "↓ 0 B/s")
        self._card_peak_ul = MetricCard("Session Peak Upload", "↑ 0 B/s")

        cards_grid.addWidget(self._card_cur_dl, 0, 0)
        cards_grid.addWidget(self._card_cur_ul, 0, 1)
        cards_grid.addWidget(self._card_peak_dl, 0, 2)
        cards_grid.addWidget(self._card_session_dl, 1, 0)
        cards_grid.addWidget(self._card_session_ul, 1, 1)
        cards_grid.addWidget(self._card_peak_ul, 1, 2)

        layout.addLayout(cards_grid)

        # 2. Graph Controls Header
        ctrl_layout = QHBoxLayout()
        graph_title = QLabel("Bandwidth History")
        graph_title.setStyleSheet("font-size: 13px; font-weight: bold; color: palette(text);")
        ctrl_layout.addWidget(graph_title)
        ctrl_layout.addStretch()

        # Time range button group
        # 3. Large Bandwidth Graph (instantiate before button toggles)
        self._graph = BandwidthGraph(self._buffer, show_legend=True)
        layout.addWidget(self._graph, stretch=1)

        self._time_group = QButtonGroup(self)
        ranges = [("5m", 5 * 60), ("15m", 15 * 60), ("30m", 30 * 60), ("1h", 60 * 60)]
        for label, seconds in ranges:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("seconds", seconds)
            btn.toggled.connect(self._on_time_toggled)
            self._time_group.addButton(btn)
            ctrl_layout.addWidget(btn)
            if label == "15m":
                btn.setChecked(True)

        # Auto Scale toggle button
        self._auto_scale_btn = QPushButton("Auto Scale")
        self._auto_scale_btn.setCheckable(True)
        self._auto_scale_btn.setChecked(True)
        self._auto_scale_btn.toggled.connect(self._on_auto_scale_toggled)
        ctrl_layout.addWidget(self._auto_scale_btn)

        layout.insertLayout(1, ctrl_layout)

        # 4. Status banner / empty state
        self._empty_label = QLabel("Waiting for network data…")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self._empty_label)

    def _on_time_toggled(self, checked: bool) -> None:
        if not checked:
            return
        btn = self.sender()
        if isinstance(btn, QPushButton) and hasattr(self, "_graph"):
            seconds = btn.property("seconds")
            self._graph.set_time_range(seconds)

    def _on_auto_scale_toggled(self, checked: bool) -> None:
        self._graph.set_auto_scale(checked)

    def on_sample_received(self, sample: NetworkSample) -> None:
        """Update metrics and graph on receiving a new sample."""
        unit_str = self._prefs.preferences.unit_mode.value
        unit_arg = "auto" if unit_str == "auto" else unit_str

        # Current speeds
        self._card_cur_dl.set_value(f"↓ {format_speed(sample.download_bps, unit=unit_arg)}")
        self._card_cur_ul.set_value(f"↑ {format_speed(sample.upload_bps, unit=unit_arg)}")

        # Session metrics
        session_m = calculate_session_metrics(self._monitor, sample)
        self._card_session_dl.set_value(format_bytes(session_m.downloaded_bytes))
        self._card_session_ul.set_value(format_bytes(session_m.uploaded_bytes))
        self._card_peak_dl.set_value(f"↓ {format_speed(session_m.peak_download_bps, unit=unit_arg)}")
        self._card_peak_ul.set_value(f"↑ {format_speed(session_m.peak_upload_bps, unit=unit_arg)}")

        # Hide empty state once samples are received
        if self._empty_label.isVisible():
            self._empty_label.hide()

        # Update graph
        self._graph.set_unit(unit_arg)
        self._graph.update_plot()

    def refresh_after_reset(self) -> None:
        """Reset metric cards and clear graph immediately after reset."""
        unit_str = self._prefs.preferences.unit_mode.value
        unit_arg = "auto" if unit_str == "auto" else unit_str

        self._card_cur_dl.set_value(f"↓ {format_speed(0.0, unit=unit_arg)}")
        self._card_cur_ul.set_value(f"↑ {format_speed(0.0, unit=unit_arg)}")
        self._card_session_dl.set_value(format_bytes(0))
        self._card_session_ul.set_value(format_bytes(0))
        self._card_peak_dl.set_value(f"↓ {format_speed(0.0, unit=unit_arg)}")
        self._card_peak_ul.set_value(f"↑ {format_speed(0.0, unit=unit_arg)}")
        self._graph.set_unit(unit_arg)
        self._graph.update_plot()
        if len(self._buffer) == 0:
            self._empty_label.show()
