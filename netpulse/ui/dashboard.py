"""Main desktop Network Analytics Dashboard window for NetPulse."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from netpulse.storage.database import Database
from netpulse.ui.help import HelpPage
from netpulse.ui.live import LivePage
from netpulse.ui.networks import NetworksPage
from netpulse.ui.overview import OverviewPage
from netpulse.ui.session import SessionPage
from netpulse.ui.settings import SettingsPage
from netpulse.ui.speedtest import SpeedTestPage
from netpulse.ui.updates import UpdatesPage
from netpulse.ui.widgets import PageScrollArea, StatusIndicator
from netpulse.utils.constants import APP_NAME, APP_VERSION
from netpulse.utils.log import get_logger

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.data_buffer import DataBuffer
    from netpulse.core.network_context import NetworkContext
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.core.network_sample import NetworkSample
    from netpulse.core.reset_coordinator import DataResetCoordinator
    from netpulse.hardware.context_manager import NetworkContextManager

logger = get_logger("dashboard")


def _create_sidebar_icon(icon_name: str) -> QIcon:
    """Create a dual-state tinted SVG icon for macOS sidebar navigation."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    svg_path = base_dir / "resources" / "icons" / f"{icon_name}.svg"
    if not svg_path.exists():
        # Fallback to current working directory
        svg_path = Path("resources") / "icons" / f"{icon_name}.svg"

    if not svg_path.exists():
        return QIcon()

    base_icon = QIcon(str(svg_path))
    icon = QIcon()

    for size in (18, 20, 24, 36):
        base_pm = base_icon.pixmap(size, size)
        if base_pm.isNull():
            continue

        # Unselected subtle state (macOS subtle grey)
        norm_pm = QPixmap(size, size)
        norm_pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(norm_pm)
        p.drawPixmap(0, 0, base_pm)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(norm_pm.rect(), QColor("#8E8E93"))
        p.end()
        icon.addPixmap(norm_pm, QIcon.Mode.Normal, QIcon.State.Off)

        # Selected state (white on blue highlight)
        sel_pm = QPixmap(size, size)
        sel_pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(sel_pm)
        p.drawPixmap(0, 0, base_pm)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(sel_pm.rect(), QColor("#FFFFFF"))
        p.end()
        icon.addPixmap(sel_pm, QIcon.Mode.Selected, QIcon.State.Off)
        icon.addPixmap(sel_pm, QIcon.Mode.Selected, QIcon.State.On)

    return icon


class DashboardWindow(QMainWindow):
    """Main desktop Network Analytics Dashboard window.

    Maintains a single reusable instance. Closing hides the window
    without disrupting background monitoring.
    """

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        monitor: NetworkMonitor,
        data_buffer: DataBuffer,
        database: Optional[Database] = None,
        context_manager: Optional[NetworkContextManager] = None,
        reset_coordinator: Optional[DataResetCoordinator] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._monitor = monitor
        self._buffer = data_buffer
        self._db = database or Database()
        self._context_manager = context_manager
        self._reset_coordinator = reset_coordinator

        self.setWindowTitle(f"{APP_NAME} — Network Analytics")
        self.resize(1020, 680)
        self.setMinimumSize(850, 520)

        self._setup_ui()
        logger.info("Dashboard window initialized")

    def _setup_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar Navigation
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(200)
        sidebar_widget.setStyleSheet("background-color: palette(alternate-base); border-right: 1px solid palette(mid);")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(12, 18, 12, 16)
        sidebar_layout.setSpacing(10)

        # App Brand in Sidebar
        brand_layout = QVBoxLayout()
        brand_title = QLabel(APP_NAME)
        font_brand = QFont()
        font_brand.setPointSize(16)
        font_brand.setWeight(QFont.Weight.Bold)
        brand_title.setFont(font_brand)

        version_label = QLabel(f"v{APP_VERSION}")
        font_ver = QFont()
        font_ver.setPointSize(10)
        version_label.setFont(font_ver)
        version_label.setStyleSheet("color: gray;")
        brand_layout.addWidget(brand_title)
        brand_layout.addWidget(version_label)
        sidebar_layout.addLayout(brand_layout)

        # Sidebar items list
        self._nav_list = QListWidget()
        self._nav_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._nav_list.setIconSize(QSize(18, 18))
        self._nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._nav_list.setMinimumHeight(240)
        self._nav_list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
                outline: none;
            }
            QListWidget::item {
                height: 36px;
                border-radius: 6px;
                padding-left: 8px;
                font-size: 13px;
                font-weight: 500;
                color: palette(text);
            }
            QListWidget::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QListWidget::item:hover:!selected {
                background-color: rgba(140, 140, 145, 0.12);
            }
        """)

        nav_items = [
            ("Overview", "overview"),
            ("Live", "live"),
            ("Speed Test", "speedtest"),
            ("Networks", "networks"),
            ("Session", "session"),
            ("Help", "help"),
            ("Updates", "updates"),
            ("Settings", "settings"),
        ]

        for label, icon_name in nav_items:
            icon = _create_sidebar_icon(icon_name)
            item = QListWidgetItem(icon, f"  {label}")
            item.setSizeHint(QSize(176, 36))
            self._nav_list.addItem(item)

        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self._nav_list)
        sidebar_layout.addStretch(1)

        # Connection status at bottom of sidebar
        self._status_indicator = StatusIndicator()
        sidebar_layout.addWidget(self._status_indicator)

        root_layout.addWidget(sidebar_widget)

        # 2. Right Content Area (QStackedWidget)
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget()

        # Instantiate Pages
        self._overview_page = OverviewPage(self._prefs, self._monitor, self._buffer)
        self._live_page = LivePage(self._prefs, self._monitor, self._buffer)
        self._speedtest_page = SpeedTestPage(self._prefs)
        self._networks_page = NetworksPage(self._prefs, self._db, self._context_manager)
        self._session_page = SessionPage(self._prefs, self._monitor)
        self._help_page = HelpPage(self._prefs)
        self._updates_page = UpdatesPage(self._prefs)
        self._settings_page = SettingsPage(
            self._prefs,
            self._monitor,
            database=self._db,
            reset_coordinator=self._reset_coordinator,
        )

        if self._reset_coordinator is not None:
            self._reset_coordinator._on_reset_callback = self.refresh_after_reset

        # Wrap each page in its own independent vertical QScrollArea
        self._scroll_overview = PageScrollArea(self._overview_page)
        self._scroll_live = PageScrollArea(self._live_page)
        self._scroll_speedtest = PageScrollArea(self._speedtest_page)
        self._scroll_networks = PageScrollArea(self._networks_page)
        self._scroll_session = PageScrollArea(self._session_page)
        self._scroll_help = PageScrollArea(self._help_page)
        self._scroll_updates = PageScrollArea(self._updates_page)
        self._scroll_settings = PageScrollArea(self._settings_page)

        self._stack.addWidget(self._scroll_overview)
        self._stack.addWidget(self._scroll_live)
        self._stack.addWidget(self._scroll_speedtest)
        self._stack.addWidget(self._scroll_networks)
        self._stack.addWidget(self._scroll_session)
        self._stack.addWidget(self._scroll_help)
        self._stack.addWidget(self._scroll_updates)
        self._stack.addWidget(self._scroll_settings)

        content_layout.addWidget(self._stack)
        root_layout.addWidget(content_container, stretch=1)

        # Default to Overview
        self._nav_list.setCurrentRow(0)

    def _on_nav_changed(self, row: int) -> None:
        self._stack.setCurrentIndex(row)

    def show_dashboard(self) -> None:
        """Display the dashboard, raising it to the front."""
        logger.info("Showing dashboard window")
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Hide the window instead of destroying it to maintain single instance."""
        logger.info("Dashboard window hidden via close event")
        self.hide()
        event.ignore()

    def on_sample_received(self, sample: NetworkSample) -> None:
        """Receive sample from UIBridge on the main Qt thread."""
        # Only update pages if the dashboard is visible to optimize performance
        if not self.isVisible():
            return

        # Check connection status
        if sample.download_bps == 0 and sample.upload_bps == 0 and not self._monitor.running:
            self._status_indicator.set_status("No network")
        else:
            if sample.interface:
                self._status_indicator.set_status(f"Connected ({sample.interface})")
            else:
                self._status_indicator.set_status("Connected")

        # Dispatch to active/all pages
        self._overview_page.on_sample_received(sample)
        self._live_page.on_sample_received(sample)
        self._networks_page.on_sample(sample)
        self._session_page.on_sample_received(sample)

    def on_context_updated(self, context: NetworkContext) -> None:
        """Receive updated NetworkContext from UIBridge."""
        self._networks_page.update_context(context)
        if context.is_connected:
            self._status_indicator.set_status(f"Connected ({context.interface.bsd_name})")
        else:
            self._status_indicator.set_status("Disconnected")

    def refresh_after_reset(self, is_full_reset: bool = False) -> None:
        """Refresh all dashboard views immediately after reset without restarting."""
        self._overview_page.refresh_after_reset()
        self._live_page.refresh_after_reset()
        self._session_page.refresh_after_reset()
        self._networks_page.refresh_after_reset()
        self._settings_page.refresh_storage_info()
        if is_full_reset:
            self._settings_page.reload_preferences_ui()
