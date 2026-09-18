"""macOS menu-bar controller using rumps.

Subscribes to NetworkMonitor for speed updates, provides configuration
menus (display mode, units, refresh interval), and shows session stats.
Contains zero network calculation logic — formatting comes from
``menubar.display``, speeds come from ``NetworkMonitor``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import rumps

from netpulse.config.models import (
    DISPLAY_MODE_LABELS,
    INTERVAL_LABELS,
    UNIT_MODE_LABELS,
    DisplayMode,
    UnitMode,
)
from netpulse.core.network_sample import NetworkSample
from netpulse.menubar.display import format_menubar_title
from netpulse.ui.mascot import LionMascotController, MascotFrame
from netpulse.utils.constants import APP_NAME
from netpulse.utils.formatters import format_bytes, format_speed
from netpulse.utils.log import get_logger

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.ui.dashboard import DashboardWindow
    from netpulse.ui.popover import NetworkPopover

logger = get_logger("menubar")


class MenuBarController(rumps.App):
    """Menu-bar application with live speed display and configuration menus.

    Menu structure::

        Network Monitor
        ↓ X MB/s
        ↑ Y MB/s
        ──────────────
        Display  ▸  (submenu with checkmarks)
        Units    ▸  (submenu with checkmarks)
        Refresh  ▸  (submenu with checkmarks)
        ──────────────
        Session Statistics
        Downloaded: X
        Uploaded: Y
        ──────────────
        Open Dashboard
        Preferences
        ──────────────
        Quit NetPulse
    """

    def __init__(
        self,
        preferences_manager: PreferencesManager,
        monitor: NetworkMonitor,
        popover: NetworkPopover = None,
        dashboard: Optional[DashboardWindow] = None,
    ) -> None:
        super().__init__(
            name=APP_NAME,
            title=self._initial_title(preferences_manager),
            quit_button="Quit NetPulse",
        )
        self._prefs_manager = preferences_manager
        self._monitor = monitor
        self._popover = popover
        self._dashboard = dashboard

        # Cache latest speeds for immediate re-format on config change
        self._last_dl_bps: float = 0.0
        self._last_ul_bps: float = 0.0

        # Tracking dicts for checkmark management
        self._display_items: dict = {}
        self._unit_items: dict = {}
        self._interval_items: dict = {}

        # Lion mascot animation controller
        self._mascot = LionMascotController(
            enabled=self._prefs_manager.preferences.enable_mascot,
            on_frame_changed=self._on_mascot_frame,
        )
        self._prefs_manager.subscribe(self._on_preferences_changed)

        # Build menu
        self._build_menu()
        self._apply_all_checkmarks()

    def initialize_status_bar(self) -> None:
        """Initialize the macOS menu bar status item without taking over the event loop."""
        if getattr(self, "_nsapp", None) is not None:
            return

        from AppKit import NSApplication
        from rumps.rumps import NSApp, App, clicked, notifications

        self._nsapp = NSApp.alloc().init()
        self._nsapp._app = self.__dict__
        notifications._init_nsapp(self._nsapp)
        setattr(App, "*app_instance", self)

        for b in getattr(clicked, "*buttons", []):
            b(self)

        self._nsapp.initializeStatusBar()
        self._update_attributed_title(self.title)

        # Apply initial mascot frame if enabled
        if self._mascot.enabled and self._mascot.current_frame:
            self._on_mascot_frame(self._mascot.current_frame)


    # ------------------------------------------------------------------
    # Public callbacks — called by NetworkMonitor / UIBridge
    # ------------------------------------------------------------------

    def on_sample(self, sample: NetworkSample) -> None:
        """Receive a NetworkSample and update the menu bar.

        Safe to call from any thread.
        """
        try:
            self._last_dl_bps = sample.download_bps
            self._last_ul_bps = sample.upload_bps

            # Update mascot state and animation speed
            self._mascot.update_speed(sample.download_bps, sample.upload_bps)

            prefs = self._prefs_manager.preferences
            new_title = format_menubar_title(
                sample.download_bps,
                sample.upload_bps,
                prefs.display_mode,
                prefs.unit_mode,
            )

            # Avoid unnecessary UI updates
            if new_title != self.title:
                self.title = new_title
                self._update_attributed_title(new_title)

            # Update speed info in menu
            unit_arg = "auto" if prefs.unit_mode == UnitMode.AUTO else prefs.unit_mode.value
            self._dl_info.title = f"↓ {format_speed(sample.download_bps, unit=unit_arg)}"
            self._ul_info.title = f"↑ {format_speed(sample.upload_bps, unit=unit_arg)}"

            # Update session statistics
            self._session_dl.title = f"  Downloaded: {format_bytes(self._monitor.session_downloaded)}"
            self._session_ul.title = f"  Uploaded: {format_bytes(self._monitor.session_uploaded)}"

        except Exception:
            logger.exception("Failed to update menu bar")

    def _update_attributed_title(self, raw_title: str) -> None:
        """Apply custom attributed title styling: smaller and lighter unit labels."""
        if not raw_title:
            return
        try:
            nsapp = getattr(self, "_nsapp", None)
            if nsapp is None:
                return
            status_item = getattr(nsapp, "nsstatusitem", None)
            if status_item is None:
                return

            import re
            import AppKit

            # Speed numbers: white (#FFFFFF), prominent font size (13.0 pt)
            # Unit: white (#FFFFFF), ~75% of speed numbers (10.0 pt), not greyed out
            font_main = AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(13.0, AppKit.NSFontWeightRegular)
            font_unit = AppKit.NSFont.systemFontOfSize_weight_(10.0, AppKit.NSFontWeightRegular)
            color_white = AppKit.NSColor.whiteColor()

            attr_str = AppKit.NSMutableAttributedString.alloc().initWithString_(raw_title)
            full_rng = AppKit.NSMakeRange(0, len(raw_title))
            attr_str.addAttribute_value_range_(AppKit.NSFontAttributeName, font_main, full_rng)
            attr_str.addAttribute_value_range_(AppKit.NSForegroundColorAttributeName, color_white, full_rng)

            unit_regex = re.compile(r'(KB/s|MB/s|GB/s|TB/s|B/s|kbps|Mbps|Gbps|[KMGT]B?)')
            for m in unit_regex.finditer(raw_title):
                start, end = m.span()
                rng = AppKit.NSMakeRange(start, end - start)
                attr_str.addAttribute_value_range_(AppKit.NSFontAttributeName, font_unit, rng)
                attr_str.addAttribute_value_range_(AppKit.NSForegroundColorAttributeName, color_white, rng)
                attr_str.addAttribute_value_range_(AppKit.NSBaselineOffsetAttributeName, 0.5, rng)

            btn = getattr(status_item, "button", lambda: None)()
            if btn is not None:
                btn.setAttributedTitle_(attr_str)
            elif hasattr(status_item, "setAttributedTitle_"):
                status_item.setAttributedTitle_(attr_str)
        except Exception:
            logger.debug("Attributed title styling unavailable; default text rendering used.")

    def on_network_context(self, context: Any) -> None:
        """Receive NetworkContext updates to handle disconnected / reconnected states."""
        try:
            is_conn = getattr(context, "is_connected", True)
            self._mascot.update_connection(is_conn)
        except Exception:
            logger.exception("Failed to update mascot connection state")

    def _on_mascot_frame(self, frame: Optional[MascotFrame]) -> None:
        """Apply the latest mascot frame to the menu bar status item."""
        try:
            if frame is not None and self._mascot.enabled:
                self._icon_nsimage = frame.nsimage
                self._icon = frame.filepath
            else:
                self._icon_nsimage = None
                self._icon = None

            if getattr(self, "_nsapp", None) is not None:
                self._nsapp.setStatusBarIcon()
        except Exception:
            logger.exception("Failed to update status bar icon")

    def _on_preferences_changed(self, prefs: Any) -> None:
        """Handle preference updates (e.g. mascot toggled)."""
        enabled = getattr(prefs, "enable_mascot", True)
        self._mascot.set_enabled(enabled)
        self._apply_all_checkmarks()
        self._refresh_title()

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        """Construct the full menu hierarchy."""
        prefs = self._prefs_manager.preferences

        # Header + speed info
        header = rumps.MenuItem("Network Monitor")
        self._dl_info = rumps.MenuItem("↓ 0 B/s")
        self._ul_info = rumps.MenuItem("↑ 0 B/s")

        # Display mode submenu
        display_menu = rumps.MenuItem("Display")
        for mode, label in DISPLAY_MODE_LABELS.items():
            item = rumps.MenuItem(label, callback=self._on_display_mode)
            self._display_items[mode] = item
            display_menu[label] = item

        # Unit mode submenu
        units_menu = rumps.MenuItem("Units")
        for mode, label in UNIT_MODE_LABELS.items():
            item = rumps.MenuItem(label, callback=self._on_unit_mode)
            self._unit_items[mode] = item
            units_menu[label] = item

        # Refresh interval submenu
        refresh_menu = rumps.MenuItem("Refresh")
        for interval, label in INTERVAL_LABELS.items():
            item = rumps.MenuItem(label, callback=self._on_refresh_interval)
            self._interval_items[interval] = item
            refresh_menu[label] = item

        # Session statistics
        session_header = rumps.MenuItem("Session Statistics")
        self._session_dl = rumps.MenuItem("  Downloaded: 0 B")
        self._session_ul = rumps.MenuItem("  Uploaded: 0 B")

        # Notifications toggle
        self._notif_item = rumps.MenuItem("Notifications Enabled", callback=self._on_toggle_notifications)

        # Action items
        dashboard = rumps.MenuItem("Open Dashboard", callback=self._on_dashboard)
        preferences = rumps.MenuItem("Preferences", callback=self._on_preferences)

        self.menu = [
            header,
            self._dl_info,
            self._ul_info,
            None,
            display_menu,
            units_menu,
            refresh_menu,
            self._notif_item,
            None,
            session_header,
            self._session_dl,
            self._session_ul,
            None,
            dashboard,
            preferences,
        ]

    # ------------------------------------------------------------------
    # Checkmark management
    # ------------------------------------------------------------------

    def _apply_all_checkmarks(self) -> None:
        """Set checkmarks on all submenus to reflect current preferences."""
        prefs = self._prefs_manager.preferences
        for mode, item in self._display_items.items():
            item.state = 1 if mode == prefs.display_mode else 0
        for mode, item in self._unit_items.items():
            item.state = 1 if mode == prefs.unit_mode else 0
        for interval, item in self._interval_items.items():
            item.state = 1 if interval == prefs.sample_interval else 0
        if hasattr(self, "_notif_item"):
            self._notif_item.state = 1 if prefs.notifications_enabled else 0


    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_display_mode(self, sender: rumps.MenuItem) -> None:
        """Handle display mode selection."""
        # Reverse-lookup: label → mode
        for mode, item in self._display_items.items():
            if item is sender:
                self._prefs_manager.update(display_mode=mode)
                self._apply_all_checkmarks()
                self._refresh_title()
                return

    def _on_unit_mode(self, sender: rumps.MenuItem) -> None:
        """Handle unit mode selection."""
        for mode, item in self._unit_items.items():
            if item is sender:
                self._prefs_manager.update(unit_mode=mode)
                self._apply_all_checkmarks()
                self._refresh_title()
                return

    def _on_refresh_interval(self, sender: rumps.MenuItem) -> None:
        """Handle refresh interval selection."""
        for interval, item in self._interval_items.items():
            if item is sender:
                self._prefs_manager.update(sample_interval=interval)
                self._monitor.set_interval(interval)
                self._apply_all_checkmarks()
                return

    def _on_toggle_notifications(self, _: rumps.MenuItem) -> None:
        """Toggle master notification setting."""
        current = self._prefs_manager.preferences.notifications_enabled
        self._prefs_manager.update(notifications_enabled=not current)
        self._apply_all_checkmarks()


    def _on_dashboard(self, _: rumps.MenuItem) -> None:
        """Open the PySide6 dashboard window or popover."""
        if self._dashboard:
            self._dashboard.show_dashboard()
        elif self._popover:
            self._popover.show()
            self._popover.raise_()
            self._popover.activateWindow()

    def _on_preferences(self, _: rumps.MenuItem) -> None:
        """Placeholder — full preferences window is a future feature."""
        rumps.alert(
            title="Preferences",
            message="More preferences will be available in a future version.\n\n"
                    "Use the Display, Units, and Refresh menus above for now.",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_title(self) -> None:
        """Re-format and set the menu-bar title using cached speeds."""
        prefs = self._prefs_manager.preferences
        new_title = format_menubar_title(
            self._last_dl_bps,
            self._last_ul_bps,
            prefs.display_mode,
            prefs.unit_mode,
        )
        self.title = new_title
        self._update_attributed_title(new_title)

    @staticmethod
    def _initial_title(prefs_manager: PreferencesManager) -> str:
        """Generate the initial menu-bar title before any samples arrive."""
        prefs = prefs_manager.preferences
        return format_menubar_title(0.0, 0.0, prefs.display_mode, prefs.unit_mode)
