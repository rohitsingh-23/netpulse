"""Live bandwidth graph using PyQtGraph."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

import pyqtgraph as pg
from PySide6.QtCore import Qt

from netpulse.utils.formatters import format_speed

from netpulse.ui.graph_data_provider import IGraphDataProvider, LiveBufferDataProvider

if TYPE_CHECKING:
    from netpulse.core.data_buffer import DataBuffer
    from netpulse.core.network_sample import NetworkSample


class SpeedAxisItem(pg.AxisItem):
    """Custom Y-axis for PyQtGraph formatting bytes/sec into human units."""

    def __init__(self, orientation: str = "left", **kwargs) -> None:
        super().__init__(orientation=orientation, **kwargs)
        self.unit: str = "auto"

    def tickStrings(self, values, scale, spacing):
        strings = []
        for val in values:
            if val <= 0:
                strings.append("0 B/s")
            else:
                strings.append(format_speed(val, unit=self.unit))
        return strings


class BandwidthGraph(pg.PlotWidget):
    """Real-time graph displaying download and upload speeds.

    Supports configurable time ranges (5m, 15m, 30m, 1h, 24h, 7d), auto-scale,
    series legend, and dark/light themes.
    """

    def __init__(
        self,
        data_buffer: Optional[DataBuffer] = None,
        data_provider: Optional[IGraphDataProvider] = None,
        show_legend: bool = True,
        parent: Optional[object] = None,
    ) -> None:
        axis_bottom = pg.DateAxisItem(orientation="bottom")
        self._axis_left = SpeedAxisItem(orientation="left")

        super().__init__(
            parent=parent,
            axisItems={"bottom": axis_bottom, "left": self._axis_left},
        )
        if data_provider is not None:
            self._provider: Optional[IGraphDataProvider] = data_provider
        elif data_buffer is not None:
            self._provider = LiveBufferDataProvider(data_buffer)
        else:
            self._provider = None

        self._buffer = data_buffer
        self._time_range_seconds: int = 15 * 60  # Default: 15 minutes
        self._auto_scale: bool = True
        self._show_legend = show_legend

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configure graph visual presentation and curves."""
        self.setBackground("default")
        self.showGrid(x=True, y=True, alpha=0.25)
        self.setMouseEnabled(x=False, y=False)
        self.hideButtons()

        # Add legend
        if self._show_legend:
            self._legend = self.addLegend(offset=(10, 10))

        # Pens: Download = Vibrant Blue, Upload = Emerald Green
        pen_dl = pg.mkPen(color=(0, 122, 255), width=2.2)
        pen_ul = pg.mkPen(color=(52, 199, 89), width=2.2)

        self._dl_curve = self.plot(pen=pen_dl, name="Download (↓)")
        self._ul_curve = self.plot(pen=pen_ul, name="Upload (↑)")

        # Translucent area fills under curves
        brush_dl = pg.mkBrush(color=(0, 122, 255, 45))
        brush_ul = pg.mkBrush(color=(52, 199, 89, 45))

        self._dl_curve.setBrush(brush_dl)
        self._dl_curve.setFillLevel(0)

        self._ul_curve.setBrush(brush_ul)
        self._ul_curve.setFillLevel(0)

    def set_time_range(self, seconds: int) -> None:
        """Update the displayed time range (e.g., 5m, 15m, 30m, 1h)."""
        self._time_range_seconds = max(1, seconds)
        self.update_plot()

    @property
    def time_range(self) -> int:
        """Current time range in seconds."""
        return self._time_range_seconds

    def set_auto_scale(self, enabled: bool) -> None:
        """Toggle automatic Y-axis scaling."""
        self._auto_scale = enabled
        if not enabled:
            self.enableAutoRange(axis="y", enable=False)
        self.update_plot()

    @property
    def auto_scale(self) -> bool:
        """Whether auto-scale is currently enabled."""
        return self._auto_scale

    def set_unit(self, unit: str) -> None:
        """Set the display unit on the Y-axis."""
        self._axis_left.unit = unit
        self._axis_left.picture = None
        self._axis_left.update()

    def set_data_provider(self, provider: IGraphDataProvider) -> None:
        """Set or swap the active time-series data provider."""
        self._provider = provider
        self.update_plot()

    def update_plot(self) -> None:
        """Fetch series from provider and update curves."""
        if not self._provider:
            return

        now_ts = time.time()
        cutoff_ts = now_ts - self._time_range_seconds

        x_data, dl_data, ul_data = self._provider.get_series(self._time_range_seconds)

        if not x_data:
            self.setXRange(cutoff_ts, now_ts, padding=0)
            self._dl_curve.setData([], [])
            self._ul_curve.setData([], [])
            if not self._auto_scale:
                self.setYRange(0, 1024 * 1024, padding=0)
            return

        max_speed = 0.0
        if dl_data:
            max_speed = max(max_speed, max(dl_data))
        if ul_data:
            max_speed = max(max_speed, max(ul_data))

        # Extend curve to touch the right edge at "now" if live
        if x_data[-1] < now_ts and (now_ts - x_data[-1]) < self._time_range_seconds:
            x_data = list(x_data) + [now_ts]
            dl_data = list(dl_data) + [dl_data[-1]]
            ul_data = list(ul_data) + [ul_data[-1]]

        min_x = min(x_data[0], cutoff_ts)
        max_x = max(x_data[-1], now_ts)
        self.setXRange(min_x, max_x, padding=0)

        if self._auto_scale:
            upper_limit = max(1024.0, max_speed * 1.15)
            self.setYRange(0, upper_limit, padding=0)
        else:
            # Fixed scale benchmark (10 MB/s or peak)
            upper_limit = max(10.0 * 1024 * 1024, max_speed * 1.1)
            self.setYRange(0, upper_limit, padding=0)

        self._dl_curve.setData(x_data, dl_data)
        self._ul_curve.setData(x_data, ul_data)
