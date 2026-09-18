"""PySide6 popover window for Network Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QButtonGroup,
    QFrame,
)

from netpulse.ui.graph import BandwidthGraph
from netpulse.utils.formatters import format_speed, format_bytes

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.data_buffer import DataBuffer
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.core.network_sample import NetworkSample
    from netpulse.ui.dashboard import DashboardWindow


class NetworkPopover(QWidget):
    """Main popover window displaying live stats and graph."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        monitor: NetworkMonitor,
        data_buffer: DataBuffer,
        dashboard: Optional[DashboardWindow] = None,
    ) -> None:
        super().__init__()
        self._prefs_manager = prefs_manager
        self._monitor = monitor
        self._data_buffer = data_buffer
        self._dashboard = dashboard

        self.setWindowTitle("Network Monitor")
        self.setMinimumSize(450, 370)

        # Make it stay on top, look like a tool window
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. Current Speed Header
        speed_layout = QHBoxLayout()

        dl_layout = QVBoxLayout()
        dl_title = QLabel("↓ DOWNLOAD")
        dl_title.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
        self._dl_label = QLabel("0 B/s")
        self._dl_label.setFont(QFont("San Francisco", 24, QFont.Weight.Medium))
        dl_layout.addWidget(dl_title)
        dl_layout.addWidget(self._dl_label)

        ul_layout = QVBoxLayout()
        ul_title = QLabel("↑ UPLOAD")
        ul_title.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
        self._ul_label = QLabel("0 B/s")
        self._ul_label.setFont(QFont("San Francisco", 24, QFont.Weight.Medium))
        ul_layout.addWidget(ul_title)
        ul_layout.addWidget(self._ul_label)

        speed_layout.addLayout(dl_layout)
        speed_layout.addStretch()
        speed_layout.addLayout(ul_layout)
        layout.addLayout(speed_layout)

        # 2. Graph
        self._graph = BandwidthGraph(self._data_buffer)
        layout.addWidget(self._graph, stretch=1)

        # 3. Time Range Controls
        time_layout = QHBoxLayout()
        self._time_group = QButtonGroup(self)

        ranges = [("5m", 5 * 60), ("15m", 15 * 60), ("30m", 30 * 60), ("1h", 60 * 60)]
        for text, seconds in ranges:
            btn = QPushButton(text)
            btn.setCheckable(True)
            # Store seconds as property for the toggled signal to use
            btn.setProperty("time_range", seconds)
            btn.toggled.connect(self._on_time_range_toggled)
            self._time_group.addButton(btn)
            time_layout.addWidget(btn)

            # Default to 15m
            if text == "15m":
                btn.setChecked(True)

        time_layout.addStretch()
        layout.addLayout(time_layout)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 4. Session & Status
        bottom_layout = QHBoxLayout()

        session_layout = QVBoxLayout()
        session_title = QLabel("SESSION")
        session_title.setStyleSheet("color: #666; font-size: 11px; font-weight: bold;")
        self._session_dl = QLabel("↓ Downloaded: 0 B")
        self._session_ul = QLabel("↑ Uploaded: 0 B")
        session_layout.addWidget(session_title)
        session_layout.addWidget(self._session_dl)
        session_layout.addWidget(self._session_ul)

        bottom_layout.addLayout(session_layout)
        bottom_layout.addStretch()

        right_layout = QVBoxLayout()
        self._open_btn = QPushButton("Open Dashboard ↗")
        self._open_btn.clicked.connect(self._on_open_dashboard)
        self._status_label = QLabel("● Connected")
        self._status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        right_layout.addWidget(self._open_btn)
        right_layout.addWidget(self._status_label, alignment=Qt.AlignmentFlag.AlignRight)

        bottom_layout.addLayout(right_layout)
        layout.addLayout(bottom_layout)

    def _on_open_dashboard(self) -> None:
        """Open the full dashboard window and close popover."""
        if self._dashboard:
            self.close()
            self._dashboard.show_dashboard()

    def set_dashboard(self, dashboard: DashboardWindow) -> None:
        """Set the dashboard window instance."""
        self._dashboard = dashboard

    def _on_time_range_toggled(self, checked: bool) -> None:
        if not checked:
            return
        btn = self.sender()
        if isinstance(btn, QPushButton):
            seconds = btn.property("time_range")
            self._graph.set_time_range(seconds)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Close on Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def on_sample_received(self, sample: NetworkSample) -> None:
        """Update UI with new sample data.

        This slot is called on the main thread via UIBridge.
        """
        # Current speeds
        unit_arg = "auto" if self._prefs_manager.preferences.unit_mode.value == "auto" else self._prefs_manager.preferences.unit_mode.value
        self._dl_label.setText(format_speed(sample.download_bps, unit=unit_arg))
        self._ul_label.setText(format_speed(sample.upload_bps, unit=unit_arg))

        # Session totals
        self._session_dl.setText(f"↓ Downloaded: {format_bytes(self._monitor.session_downloaded)}")
        self._session_ul.setText(f"↑ Uploaded: {format_bytes(self._monitor.session_uploaded)}")

        # Connectivity status (simplistic for Phase 3 based on any activity)
        if sample.download_bps == 0 and sample.upload_bps == 0:
            # Check if any samples have been non-zero recently, if not, maybe disconnected.
            # But standard is just assuming connected if psutil can read interfaces.
            pass
        self._status_label.setText("● Connected")

        # Update graph
        self._graph.update_plot()
