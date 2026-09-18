"""Coordinator for safe execution of NetPulse data reset operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from netpulse.utils.log import get_logger

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.hardware.context_manager import NetworkContextManager
    from netpulse.notifications.engine import NotificationEngine
    from netpulse.storage.aggregator import SampleAggregator
    from netpulse.storage.database import Database

logger = get_logger("reset_coordinator")


class DataResetCoordinator:
    """Coordinates multi-subsystem reset operations safely.

    Guarantees:
    - No artificial bandwidth delta spikes on subsequent samples
    - Staged database metrics discarded before clearing tables
    - SQLite schema version preserved (v2)
    - Notification cooldowns and hysteresis re-initialized
    - Active network rediscovery with fresh baseline
    """

    def __init__(
        self,
        preferences_manager: PreferencesManager,
        database: Database,
        monitor: NetworkMonitor,
        aggregator: Optional[SampleAggregator] = None,
        context_manager: Optional[NetworkContextManager] = None,
        notification_engine: Optional[NotificationEngine] = None,
        on_reset_callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self._prefs = preferences_manager
        self._db = database
        self._monitor = monitor
        self._aggregator = aggregator
        self._context_mgr = context_manager
        self._notif_engine = notification_engine
        self._on_reset_callback = on_reset_callback

    def reset_statistics_and_history(self) -> None:
        """Permanently delete all historical rollups, networks, and session metrics.

        Preserves user preferences, configuration, and notification settings.
        """
        logger.info("Executing 'Reset Statistics & History'")
        self._reset_statistics_and_history_internal()

        # Notify UI observers
        if self._on_reset_callback is not None:
            try:
                self._on_reset_callback(False)
            except Exception:
                logger.exception("Error executing on_reset_callback for statistics reset")

        logger.info("'Reset Statistics & History' completed successfully")

    def _reset_statistics_and_history_internal(self) -> None:
        """Internal worker executing core data and counter resets without UI notification."""
        # 1. Discard staged aggregator data and clear aggregator sample baseline
        if self._aggregator is not None:
            self._aggregator.reset()

        # 2. Reset NetworkMonitor baseline, counters, and buffer
        self._monitor.reset_accounting()

        # 3. Clear SQLite tables while preserving schema
        self._db.reset_statistics()

        # 4. Reset notification policy and cooldowns
        if self._notif_engine is not None:
            self._notif_engine.reset_state()

        # 5. Rediscover active network identity and re-register with 0 usage
        if self._context_mgr is not None:
            ctx = self._context_mgr.refresh_now()
            if ctx.is_connected:
                from netpulse.storage.repository import StatsRepository
                repo = StatsRepository(self._db)
                repo.upsert_network(
                    network_id=ctx.network.network_id,
                    connection_type=ctx.network.connection_type,
                    ssid=ctx.network.ssid,
                    display_name=ctx.network.display_name,
                    interface_id=ctx.network.interface_id,
                    bssid_hash=ctx.network.bssid_hash,
                )

    def reset_all_data(self) -> None:
        """Reset NetPulse to a clean first-run data state.

        Permanently deletes database history, resets session metrics,
        and restores application preferences and notification settings to defaults.
        """
        logger.info("Executing 'Reset All NetPulse Data'")

        # 1. Perform history and statistics reset without firing partial UI callback
        self._reset_statistics_and_history_internal()

        # 2. Reset preferences to defaults
        new_prefs = self._prefs.reset_to_defaults()

        # 3. Reset monitor sampling interval to default
        self._monitor.set_interval(new_prefs.sample_interval)

        # 4. Reapply appearance theme
        from netpulse.ui.theme import apply_appearance_theme
        apply_appearance_theme(new_prefs.appearance)

        # 5. Notify UI observers of full reset
        if self._on_reset_callback is not None:
            try:
                self._on_reset_callback(True)
            except Exception:
                logger.exception("Error executing on_reset_callback for all-data reset")

        logger.info("'Reset All NetPulse Data' completed successfully")
