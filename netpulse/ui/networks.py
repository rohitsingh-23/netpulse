"""Networks dashboard page displaying active connection RF intelligence and historical network analytics."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from netpulse.core.network_context import NetworkContext
from netpulse.core.network_sample import NetworkSample
from netpulse.storage.models import NetworkSummary
from netpulse.storage.repository import StatsRepository
from netpulse.ui.graph import BandwidthGraph
from netpulse.ui.graph_data_provider import HistoricalNetworkDataProvider
from netpulse.ui.widgets import CardContainer, MetricCard
from netpulse.utils.formatters import format_bytes, format_speed

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.hardware.context_manager import NetworkContextManager
    from netpulse.storage.database import Database


class NetworksPage(QWidget):
    """Network & Interface Intelligence view in the NetPulse Dashboard."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        database: Database,
        context_manager: Optional[NetworkContextManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._db = database
        self._repo = StatsRepository(database)
        self._context_manager = context_manager

        self._current_context: Optional[NetworkContext] = None
        self._selected_network_id: Optional[str] = None
        self._known_networks: List[NetworkSummary] = []
        self._history_range_seconds: int = 24 * 3600  # Default 24h

        self._setup_ui()
        self._refresh_networks_list()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Top Section: Current Connection Card
        self._card_current = CardContainer()
        current_layout = QVBoxLayout(self._card_current)
        current_layout.setContentsMargins(20, 18, 20, 18)
        current_layout.setSpacing(12)

        # Header: status dot, network name, badges
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self._lbl_status_dot = QLabel("●")
        self._lbl_status_dot.setStyleSheet("color: #34C759; font-size: 16px;")
        header_row.addWidget(self._lbl_status_dot)

        self._lbl_net_title = QLabel("Checking Connection...")
        font_title = QFont()
        font_title.setPointSize(16)
        font_title.setWeight(QFont.Weight.Bold)
        self._lbl_net_title.setFont(font_title)
        header_row.addWidget(self._lbl_net_title)

        self._lbl_type_badge = QLabel("Wi-Fi")
        self._lbl_type_badge.setStyleSheet(
            "background-color: rgba(0, 122, 255, 0.15); color: #007AFF; "
            "padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;"
        )
        header_row.addWidget(self._lbl_type_badge)

        self._lbl_iface_badge = QLabel("en0")
        self._lbl_iface_badge.setStyleSheet(
            "background-color: rgba(128, 128, 128, 0.15); color: gray; "
            "padding: 3px 8px; border-radius: 6px; font-weight: bold; font-size: 11px;"
        )
        header_row.addWidget(self._lbl_iface_badge)

        header_row.addStretch()

        self._lbl_live_speed = QLabel("↓ 0 B/s  •  ↑ 0 B/s")
        font_spd = QFont()
        font_spd.setPointSize(12)
        font_spd.setWeight(QFont.Weight.Medium)
        self._lbl_live_speed.setFont(font_spd)
        header_row.addWidget(self._lbl_live_speed)

        current_layout.addLayout(header_row)

        # Location permission disclaimer banner (hidden by default)
        self._perm_banner = QFrame()
        self._perm_banner.setStyleSheet(
            "background-color: rgba(255, 149, 0, 0.12); border: 1px solid rgba(255, 149, 0, 0.3); "
            "border-radius: 6px; padding: 6px 12px;"
        )
        perm_layout = QHBoxLayout(self._perm_banner)
        perm_layout.setContentsMargins(8, 4, 8, 4)
        self._lbl_perm_text = QLabel(
            "ℹ macOS Location Services permission is required to show the Wi-Fi network SSID."
        )
        self._lbl_perm_text.setStyleSheet("color: #FF9500; font-size: 11px; font-weight: 500;")
        perm_layout.addWidget(self._lbl_perm_text)
        self._perm_banner.setVisible(False)
        current_layout.addWidget(self._perm_banner)

        # RF Signal & Connection Details Grid
        self._grid_details = QGridLayout()
        self._grid_details.setSpacing(10)

        self._lbl_rssi = QLabel("—")
        self._lbl_noise = QLabel("—")
        self._lbl_channel = QLabel("—")
        self._lbl_band = QLabel("—")
        self._lbl_width = QLabel("—")
        self._lbl_phy = QLabel("—")
        self._lbl_rate = QLabel("—")
        self._lbl_security = QLabel("—")
        self._lbl_ip = QLabel("—")

        font_v = QFont()
        font_v.setPointSize(11)
        font_v.setWeight(QFont.Weight.Medium)
        for l in (
            self._lbl_rssi, self._lbl_noise, self._lbl_channel, self._lbl_band,
            self._lbl_width, self._lbl_phy, self._lbl_rate, self._lbl_security, self._lbl_ip
        ):
            l.setFont(font_v)

        # Row 0
        self._grid_details.addWidget(self._field_lbl("Signal (RSSI):"), 0, 0)
        self._grid_details.addWidget(self._lbl_rssi, 0, 1)
        self._grid_details.addWidget(self._field_lbl("Channel:"), 0, 2)
        self._grid_details.addWidget(self._lbl_channel, 0, 3)
        self._grid_details.addWidget(self._field_lbl("PHY Mode:"), 0, 4)
        self._grid_details.addWidget(self._lbl_phy, 0, 5)

        # Row 1
        self._grid_details.addWidget(self._field_lbl("Noise:"), 1, 0)
        self._grid_details.addWidget(self._lbl_noise, 1, 1)
        self._grid_details.addWidget(self._field_lbl("Frequency Band:"), 1, 2)
        self._grid_details.addWidget(self._lbl_band, 1, 3)
        self._grid_details.addWidget(self._field_lbl("Link Rate:"), 1, 4)
        self._grid_details.addWidget(self._lbl_rate, 1, 5)

        # Row 2
        self._grid_details.addWidget(self._field_lbl("Channel Width:"), 2, 0)
        self._grid_details.addWidget(self._lbl_width, 2, 1)
        self._grid_details.addWidget(self._field_lbl("Security:"), 2, 2)
        self._grid_details.addWidget(self._lbl_security, 2, 3)
        self._grid_details.addWidget(self._field_lbl("IP Address:"), 2, 4)
        self._grid_details.addWidget(self._lbl_ip, 2, 5)

        current_layout.addLayout(self._grid_details)
        layout.addWidget(self._card_current)

        # 2. Bottom Section: Splitter with Known Networks on left, Detail/Graph on right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)

        # Left panel: Known networks
        left_card = CardContainer()
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        left_title = QLabel("KNOWN NETWORKS")
        left_title.setStyleSheet("color: gray; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        left_layout.addWidget(left_title)

        self._net_list = QListWidget()
        self._net_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: none; }"
            "QListWidget::item { padding: 8px 10px; border-radius: 6px; margin-bottom: 4px; }"
            "QListWidget::item:selected { background-color: rgba(0, 122, 255, 0.2); color: white; }"
            "QListWidget::item:hover:!selected { background-color: rgba(128, 128, 128, 0.1); }"
        )
        self._net_list.currentRowChanged.connect(self._on_network_selected)
        left_layout.addWidget(self._net_list)

        splitter.addWidget(left_card)

        # Right panel: Selected network analytics & historical graph
        right_card = CardContainer()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 14, 16, 14)
        right_layout.setSpacing(12)

        # Detail header with Range Selector
        detail_header = QHBoxLayout()
        self._lbl_detail_name = QLabel("Select a Network")
        font_d = QFont()
        font_d.setPointSize(14)
        font_d.setWeight(QFont.Weight.Bold)
        self._lbl_detail_name.setFont(font_d)
        detail_header.addWidget(self._lbl_detail_name)
        detail_header.addStretch()

        # Range buttons
        self._range_group = QButtonGroup(self)
        ranges = [("24h", 24 * 3600), ("7d", 7 * 86400), ("30d", 30 * 86400)]
        for text, secs in ranges:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedWidth(50)
            btn.setStyleSheet(
                "QPushButton { background: rgba(128,128,128,0.15); border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
                "QPushButton:checked { background: #007AFF; color: white; font-weight: bold; }"
            )
            if secs == self._history_range_seconds:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, s=secs: self._on_range_changed(s))
            self._range_group.addButton(btn)
            detail_header.addWidget(btn)

        right_layout.addLayout(detail_header)

        # Lifetime usage stat cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self._card_net_dl = MetricCard("Total Download", "0 B", value_color="#007AFF")
        self._card_net_ul = MetricCard("Total Upload", "0 B", value_color="#34C759")
        self._card_net_peak = MetricCard("Peak Speed", "0 B/s")
        stats_row.addWidget(self._card_net_dl)
        stats_row.addWidget(self._card_net_ul)
        stats_row.addWidget(self._card_net_peak)
        right_layout.addLayout(stats_row)

        # Historical graph
        self._history_provider = HistoricalNetworkDataProvider(self._repo, "")
        self._graph = BandwidthGraph(data_provider=self._history_provider, show_legend=True)
        self._graph.set_time_range(self._history_range_seconds)
        right_layout.addWidget(self._graph)

        splitter.addWidget(right_card)
        splitter.setSizes([260, 600])

        layout.addWidget(splitter)

    def _field_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: gray; font-size: 11px;")
        return lbl

    def on_sample(self, sample: NetworkSample) -> None:
        """Update live speed in current connection header."""
        unit = self._prefs.preferences.unit_mode.value
        dl_str = format_speed(sample.download_bps, unit=unit)
        ul_str = format_speed(sample.upload_bps, unit=unit)
        self._lbl_live_speed.setText(f"↓ {dl_str}  •  ↑ {ul_str}")

    def update_context(self, ctx: NetworkContext) -> None:
        """Update current connection card with new NetworkContext snapshot."""
        self._current_context = ctx

        if not ctx.is_connected:
            self._lbl_status_dot.setText("○")
            self._lbl_status_dot.setStyleSheet("color: gray; font-size: 16px;")
            self._lbl_net_title.setText("Disconnected")
            self._lbl_type_badge.setText("None")
            self._lbl_iface_badge.setText("—")
            self._perm_banner.setVisible(False)
            self._reset_rf_fields()
            return

        self._lbl_status_dot.setText("●")
        self._lbl_status_dot.setStyleSheet("color: #34C759; font-size: 16px;")

        name = ctx.network.display_name
        self._lbl_net_title.setText(name)
        self._lbl_type_badge.setText(ctx.interface.interface_type.upper())
        self._lbl_iface_badge.setText(ctx.interface.bsd_name)

        # Permission banner
        self._perm_banner.setVisible(ctx.permission_restricted)

        # RF signal and link details
        unit = self._prefs.preferences.unit_mode.value
        if ctx.rssi is not None:
            quality = "Excellent" if ctx.rssi >= -60 else ("Good" if ctx.rssi >= -70 else "Fair")
            self._lbl_rssi.setText(f"{ctx.rssi} dBm ({quality})")
        else:
            self._lbl_rssi.setText("—")

        self._lbl_noise.setText(f"{ctx.noise} dBm" if ctx.noise is not None else "—")
        self._lbl_channel.setText(str(ctx.channel) if ctx.channel is not None else "—")
        self._lbl_band.setText(ctx.band or "—")
        self._lbl_width.setText(ctx.channel_width or "—")
        self._lbl_phy.setText(ctx.phy_mode or "—")
        self._lbl_rate.setText(f"{ctx.transmit_rate_mbps:.0f} Mbps" if ctx.transmit_rate_mbps else "—")
        self._lbl_security.setText(ctx.security or "—")
        self._lbl_ip.setText(ctx.ipv4_address or ctx.ipv6_address or "—")

        # Refresh networks list in background
        self._refresh_networks_list()

    def _reset_rf_fields(self) -> None:
        for l in (
            self._lbl_rssi, self._lbl_noise, self._lbl_channel, self._lbl_band,
            self._lbl_width, self._lbl_phy, self._lbl_rate, self._lbl_security, self._lbl_ip
        ):
            l.setText("—")

    def _refresh_networks_list(self) -> None:
        """Query database for known networks and populate the left list widget."""
        self._known_networks = self._repo.get_known_networks()
        self._net_list.clear()

        if not self._known_networks:
            item = QListWidgetItem("No historical networks recorded")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._net_list.addItem(item)
            return

        selected_row = 0
        for i, net in enumerate(self._known_networks):
            total_bytes = net.total_download_bytes + net.total_upload_bytes
            traffic_str = format_bytes(total_bytes)
            type_str = net.connection_type.title()

            display_text = f"{net.display_name}\n{type_str} · {traffic_str} total"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, net.network_id)
            self._net_list.addItem(item)

            if self._selected_network_id == net.network_id:
                selected_row = i

        self._net_list.setCurrentRow(selected_row)

    def _on_network_selected(self, row: int) -> None:
        """Handle selection change in the known networks list."""
        if row < 0 or row >= len(self._known_networks):
            return

        net = self._known_networks[row]
        self._selected_network_id = net.network_id

        self._lbl_detail_name.setText(net.display_name)
        self._card_net_dl.update_value(format_bytes(net.total_download_bytes))
        self._card_net_ul.update_value(format_bytes(net.total_upload_bytes))

        unit = self._prefs.preferences.unit_mode.value
        max_peak = max(net.peak_download_bps, net.peak_upload_bps)
        self._card_net_peak.update_value(format_speed(max_peak, unit=unit))

        # Update graph data provider
        self._history_provider.set_network_id(net.network_id)
        self._graph.set_time_range(self._history_range_seconds)

    def _on_range_changed(self, seconds: int) -> None:
        """Update historical graph time range."""
        self._history_range_seconds = seconds
        self._graph.set_time_range(seconds)

    def refresh_after_reset(self) -> None:
        """Refresh network list and detail cards immediately after reset."""
        self._selected_network_id = None
        self._lbl_detail_name.setText("Select a Network")
        self._card_net_dl.update_value("0 B")
        self._card_net_ul.update_value("0 B")
        self._card_net_peak.update_value("0 B/s")
        self._history_provider.set_network_id("")
        self._graph.update_plot()
        self._refresh_networks_list()
        if self._current_context is not None:
            self.update_context(self._current_context)
