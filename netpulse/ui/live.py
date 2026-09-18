"""Live real-time monitoring page for the NetPulse Dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from netpulse.ui.graph import BandwidthGraph
from netpulse.ui.metrics import calculate_window_metrics, filter_samples_by_range
from netpulse.ui.widgets import CardContainer
from netpulse.utils.formatters import format_speed

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.data_buffer import DataBuffer
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.core.network_sample import NetworkSample


class LivePage(QWidget):
    """Live real-time bandwidth view with window averages and peaks."""

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
        self._selected_range: int = 15 * 60  # Default: 15 minutes

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Prominent Live Speed Cards (Download & Upload)
        speeds_layout = QHBoxLayout()
        speeds_layout.setSpacing(16)

        # Download Panel
        self._dl_panel = self._create_speed_panel("DOWNLOAD", "#007AFF")
        speeds_layout.addWidget(self._dl_panel, stretch=1)

        # Upload Panel
        self._ul_panel = self._create_speed_panel("UPLOAD", "#34C759")
        speeds_layout.addWidget(self._ul_panel, stretch=1)

        layout.addLayout(speeds_layout)

        # 3. Live Bandwidth Graph (instantiate before button toggles)
        self._graph = BandwidthGraph(self._buffer, show_legend=True)

        # 2. Graph Controls Header
        ctrl_layout = QHBoxLayout()
        graph_title = QLabel("Live Activity Window")
        graph_title.setStyleSheet("font-size: 13px; font-weight: bold; color: palette(text);")
        ctrl_layout.addWidget(graph_title)
        ctrl_layout.addStretch()

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

        layout.addLayout(ctrl_layout)
        layout.addWidget(self._graph, stretch=1)

    def _create_speed_panel(self, direction: str, accent_color: str) -> CardContainer:
        """Construct a card showing current, average, and peak speeds."""
        card = CardContainer()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(8)

        # Header title
        title_label = QLabel(direction)
        font_dir = QFont()
        font_dir.setPointSize(11)
        font_dir.setWeight(QFont.Weight.Bold)
        title_label.setFont(font_dir)
        title_label.setStyleSheet(f"color: {accent_color}; letter-spacing: 0.5px;")
        card_layout.addWidget(title_label)

        # Big Current Speed
        cur_val = QLabel("0 B/s")
        font_speed = QFont()
        font_speed.setPointSize(26)
        font_speed.setWeight(QFont.Weight.Medium)
        cur_val.setFont(font_speed)
        card_layout.addWidget(cur_val)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: palette(mid);")
        card_layout.addWidget(line)

        # Stats Breakdown Grid (Current, Average, Peak for visible range)
        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setSpacing(6)

        font_stat = QFont()
        font_stat.setPointSize(11)
        font_stat.setWeight(QFont.Weight.Medium)

        avg_label_title = QLabel("Window Average:")
        avg_label_title.setStyleSheet("color: gray; font-size: 11px;")
        avg_val = QLabel("0 B/s")
        avg_val.setFont(font_stat)

        peak_label_title = QLabel("Window Peak:")
        peak_label_title.setStyleSheet("color: gray; font-size: 11px;")
        peak_val = QLabel("0 B/s")
        peak_val.setFont(font_stat)

        grid.addWidget(avg_label_title, 0, 0)
        grid.addWidget(avg_val, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        grid.addWidget(peak_label_title, 1, 0)
        grid.addWidget(peak_val, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)

        card_layout.addLayout(grid)

        # Store labels as properties on the card for quick updating
        card.setProperty("cur_val", cur_val)
        card.setProperty("avg_val", avg_val)
        card.setProperty("peak_val", peak_val)

        return card

    def _on_time_toggled(self, checked: bool) -> None:
        if not checked:
            return
        btn = self.sender()
        if isinstance(btn, QPushButton) and hasattr(self, "_graph"):
            seconds = btn.property("seconds")
            self._selected_range = seconds
            self._graph.set_time_range(seconds)
            self._update_metrics()

    def on_sample_received(self, sample: NetworkSample) -> None:
        """Update live panel metrics and graph."""
        self._update_metrics()
        unit_str = self._prefs.preferences.unit_mode.value
        unit_arg = "auto" if unit_str == "auto" else unit_str
        self._graph.set_unit(unit_arg)
        self._graph.update_plot()

    def _update_metrics(self) -> None:
        """Compute window metrics for current visible range."""
        unit_str = self._prefs.preferences.unit_mode.value
        unit_arg = "auto" if unit_str == "auto" else unit_str

        samples = self._buffer.get_samples()
        window_samples = filter_samples_by_range(samples, self._selected_range)
        metrics = calculate_window_metrics(window_samples)

        # Update Download Panel
        dl_cur: QLabel = self._dl_panel.property("cur_val")
        dl_avg: QLabel = self._dl_panel.property("avg_val")
        dl_peak: QLabel = self._dl_panel.property("peak_val")
        dl_cur.setText(f"↓ {format_speed(metrics.current_download_bps, unit=unit_arg)}")
        dl_avg.setText(format_speed(metrics.average_download_bps, unit=unit_arg))
        dl_peak.setText(format_speed(metrics.peak_download_bps, unit=unit_arg))

        # Update Upload Panel
        ul_cur: QLabel = self._ul_panel.property("cur_val")
        ul_avg: QLabel = self._ul_panel.property("avg_val")
        ul_peak: QLabel = self._ul_panel.property("peak_val")
        ul_cur.setText(f"↑ {format_speed(metrics.current_upload_bps, unit=unit_arg)}")
        ul_avg.setText(format_speed(metrics.average_upload_bps, unit=unit_arg))
        ul_peak.setText(format_speed(metrics.peak_upload_bps, unit=unit_arg))

    def refresh_after_reset(self) -> None:
        """Reset live panel metrics and clear graph immediately after reset."""
        self._update_metrics()
        unit_str = self._prefs.preferences.unit_mode.value
        unit_arg = "auto" if unit_str == "auto" else unit_str
        self._graph.set_unit(unit_arg)
        self._graph.update_plot()
