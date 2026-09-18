"""NetPulse application entry point.

Wires PreferencesManager → NetworkMonitor → MenuBarController
and manages lifecycle.

Usage::

    python -m netpulse.app
"""

from __future__ import annotations

import sys
import signal

try:
    import AppKit
    _APPKIT_AVAILABLE = True
except ImportError:
    _APPKIT_AVAILABLE = False

from PySide6.QtWidgets import QApplication

from netpulse.config.preferences import PreferencesManager
from netpulse.core.data_buffer import DataBuffer
from netpulse.core.network_monitor import NetworkMonitor
from netpulse.menubar.controller import MenuBarController
from netpulse.storage.aggregator import SampleAggregator
from netpulse.storage.database import Database
from netpulse.storage.repository import StatsRepository
from netpulse.ui.bridge import UIBridge
from netpulse.ui.dashboard import DashboardWindow
from netpulse.ui.popover import NetworkPopover
from netpulse.ui.theme import apply_appearance_theme
from netpulse.utils.constants import APP_NAME, APP_VERSION
from netpulse.utils.log import get_logger, setup_logging


def main() -> None:
    """Launch NetPulse.

    Startup:
        1. Configure logging
        2. Initialize Qt Application
        3. Load preferences and apply theme
        4. Create core models (DataBuffer, NetworkMonitor)
        5. Create UI components (Bridge, DashboardWindow, Popover, MenuBarController)
        6. Subscribe UI to monitor via Bridge
        7. Start monitor
        8. Run Qt event loop
    """
    setup_logging()
    logger = get_logger("app")
    logger.info("%s v%s starting", APP_NAME, APP_VERSION)

    # Initialize Qt
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    # Load preferences
    prefs_manager = PreferencesManager()
    prefs_manager.load()
    prefs = prefs_manager.preferences
    logger.info(
        "Preferences: display=%s, unit=%s, interval=%.1fs, appearance=%s",
        prefs.display_mode.value,
        prefs.unit_mode.value,
        prefs.sample_interval,
        prefs.appearance.value,
    )
    apply_appearance_theme(prefs.appearance)

    # Make application accessory (no dock icon, no app menu)
    if _APPKIT_AVAILABLE:
        AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        # Hide the main menu
        if AppKit.NSApp.mainMenu():
            AppKit.NSApp.mainMenu().removeAllItems()

    # Sync login item
    from netpulse.platform.login_item import set_login_item_enabled
    set_login_item_enabled(prefs.start_at_login)

    from netpulse.hardware.context_manager import NetworkContextManager
    from netpulse.notifications.engine import NotificationEngine

    # Initialize persistence (SQLite)
    database = Database()
    stats_repo = StatsRepository(database)
    aggregator = SampleAggregator(database)

    # Initialize context manager for interface & network intelligence
    context_manager = NetworkContextManager()

    # Initialize notifications subsystem
    notif_engine = NotificationEngine(prefs_manager=prefs_manager)

    # Create core components (single monitoring source)
    monitor = NetworkMonitor(
        interval=prefs.sample_interval,
        context_manager=context_manager,
    )
    data_buffer = monitor.buffer

    # Initialize reset coordinator for safe user-facing reset operations
    from netpulse.core.reset_coordinator import DataResetCoordinator

    reset_coordinator = DataResetCoordinator(
        preferences_manager=prefs_manager,
        database=database,
        monitor=monitor,
        aggregator=aggregator,
        context_manager=context_manager,
        notification_engine=notif_engine,
    )

    # Create UI components
    bridge = UIBridge()
    dashboard = DashboardWindow(
        prefs_manager=prefs_manager,
        monitor=monitor,
        data_buffer=data_buffer,
        database=database,
        context_manager=context_manager,
        reset_coordinator=reset_coordinator,
    )
    popover = NetworkPopover(
        prefs_manager=prefs_manager,
        monitor=monitor,
        data_buffer=data_buffer,
        dashboard=dashboard,
    )

    # Create controller
    controller = MenuBarController(
        preferences_manager=prefs_manager,
        monitor=monitor,
        popover=popover,
        dashboard=dashboard,
    )
    controller.initialize_status_bar()

    # Connect bridge signals to popover, controller, and dashboard
    # This guarantees that ALL UI components update on the main Qt thread!
    bridge.sample_received.connect(popover.on_sample_received)
    bridge.sample_received.connect(controller.on_sample)
    bridge.sample_received.connect(dashboard.on_sample_received)
    bridge.network_context_updated.connect(dashboard.on_context_updated)
    bridge.network_context_updated.connect(controller.on_network_context)

    # Automatically persist network identity on resolution
    def on_context_resolved(ctx) -> None:
        if ctx.is_connected:
            stats_repo.upsert_network(
                network_id=ctx.network.network_id,
                connection_type=ctx.network.connection_type,
                ssid=ctx.network.ssid,
                display_name=ctx.network.display_name,
                interface_id=ctx.network.interface_id,
                bssid_hash=ctx.network.bssid_hash,
            )

    context_manager.subscribe(bridge.dispatch_context)
    context_manager.subscribe(on_context_resolved)
    context_manager.subscribe(notif_engine.on_context_updated)
    context_manager.start()

    # Initial context push to dashboard, notifications, and menu bar controller
    dashboard.on_context_updated(context_manager.current_context)
    controller.on_network_context(context_manager.current_context)
    on_context_resolved(context_manager.current_context)
    notif_engine.on_context_updated(context_manager.current_context)

    # Subscribe UI bridge, storage aggregator, and notification engine to monitor
    monitor.subscribe(bridge.dispatch_sample)
    monitor.subscribe(aggregator.on_sample)
    monitor.subscribe(notif_engine.on_sample_received)
    monitor.start()


    def shutdown(*_args: object) -> None:
        logger.info("Shutdown signal received")
        context_manager.stop()
        monitor.stop()
        aggregator.flush()
        database.close()
        qt_app.quit()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    def on_about_to_quit() -> None:
        context_manager.stop()
        monitor.stop()
        aggregator.flush()
        database.close()

    qt_app.aboutToQuit.connect(on_about_to_quit)

    try:
        # We run the Qt event loop. Since both Qt and rumps (via PyObjC)
        # integrate with the native NSApplication run loop, the menu bar
        # continues to work while Qt drives the event processing.
        sys.exit(qt_app.exec())
    finally:
        context_manager.stop()
        monitor.unsubscribe(bridge.dispatch_sample)
        monitor.stop()
        logger.info("%s exited cleanly", APP_NAME)


if __name__ == "__main__":
    main()
