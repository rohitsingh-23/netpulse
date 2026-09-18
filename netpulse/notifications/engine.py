"""Notification engine coordinating event detection, policy evaluation, and dispatch.

Operates in a thread-safe, non-blocking manner.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import threading
from typing import Deque, List, Optional

from netpulse.config.preferences import PreferencesManager
from netpulse.core.network_context import NetworkContext
from netpulse.core.network_sample import NetworkSample
from netpulse.notifications.backend import MacOSNotificationBackend, NotificationBackend
from netpulse.notifications.models import (
    NotificationEvent,
    NotificationSeverity,
    NotificationType,
)
from netpulse.notifications.policy import NotificationPolicy
from netpulse.utils.formatters import format_bytes, format_speed
from netpulse.utils.log import get_logger

logger = get_logger("notifications.engine")


class NotificationEngine:
    """Core notification coordinator.

    Subscribes to NetworkContextManager (for connection state & RF telemetry)
    and NetworkMonitor (for speeds & usage alerts).
    """

    MAX_RECENT_EVENTS = 50

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        policy: Optional[NotificationPolicy] = None,
        backend: Optional[NotificationBackend] = None,
    ) -> None:
        self._prefs = prefs_manager
        self._policy = policy or NotificationPolicy(prefs_manager)
        self._backend = backend or MacOSNotificationBackend()

        self._lock = threading.Lock()
        self._recent_events: Deque[NotificationEvent] = deque(maxlen=self.MAX_RECENT_EVENTS)
        self._event_listeners: list = []

        # Previous context tracking for lifecycle transitions
        self._previous_context: Optional[NetworkContext] = None
        self._last_connected_network_id: Optional[str] = None
        self._last_connected_display_name: Optional[str] = None

        # Track total session usage on active network
        self._current_network_session_bytes: int = 0

    @property
    def recent_events(self) -> List[NotificationEvent]:
        """Return a copy of recent notification events in chronological order."""
        with self._lock:
            return list(self._recent_events)

    def subscribe(self, callback) -> None:
        """Register listener for emitted events."""
        with self._lock:
            if callback not in self._event_listeners:
                self._event_listeners.append(callback)

    def unsubscribe(self, callback) -> None:
        """Unregister listener."""
        with self._lock:
            try:
                self._event_listeners.remove(callback)
            except ValueError:
                pass

    def reset_state(self) -> None:
        """Reset internal transition tracking, session accumulation, and policy state."""
        with self._lock:
            self._recent_events.clear()
            self._previous_context = None
            self._last_connected_network_id = None
            self._last_connected_display_name = None
            self._current_network_session_bytes = 0
            self._policy.reset_state()
        logger.info("NotificationEngine state and policy reset")

    # ------------------------------------------------------------------
    # Event Processors (Safe to call from background threads)
    # ------------------------------------------------------------------

    def on_context_updated(self, context: NetworkContext) -> None:
        """Process connection state transitions & Wi-Fi signal changes."""
        with self._lock:
            prev = self._previous_context
            self._previous_context = context

        # 1. Evaluate lifecycle transitions
        if prev is None:
            # First initialization
            if context.is_connected:
                self._last_connected_network_id = context.network.network_id
                self._last_connected_display_name = context.network.display_name
                self._dispatch_connected(context)
            return

        # Direct transition checks
        if not prev.is_connected and context.is_connected:
            # Was disconnected -> now connected
            # Check if this is a restored connection or fresh connected
            if (
                self._last_connected_network_id == context.network.network_id
                and self._policy.is_enabled(NotificationType.CONNECTION_RESTORED)
            ):
                self._dispatch_restored(context)
            else:
                self._dispatch_connected(context)

            self._last_connected_network_id = context.network.network_id
            self._last_connected_display_name = context.network.display_name
            self._policy.reset_network_state(context.network.network_id)
            self._current_network_session_bytes = 0

        elif prev.is_connected and not context.is_connected:
            # Was connected -> now disconnected
            self._dispatch_disconnected(prev)
            self._policy.reset_network_state(None)

        elif prev.is_connected and context.is_connected:
            # Both connected — did network identity or interface change?
            if (
                prev.network.network_id != context.network.network_id
                or prev.interface.interface_id != context.interface.interface_id
            ):
                self._dispatch_changed(prev, context)
                self._last_connected_network_id = context.network.network_id
                self._last_connected_display_name = context.network.display_name
                self._policy.reset_network_state(context.network.network_id)
                self._current_network_session_bytes = 0

        # 2. Evaluate Wi-Fi RF signal quality (weak signal with hysteresis)
        if context.is_connected and context.interface.interface_type == "wifi":
            if self._policy.evaluate_weak_signal(context.rssi):
                self._dispatch_weak_signal(context)

    def on_sample_received(self, sample: NetworkSample) -> None:
        """Process high-frequency samples for speed and data usage spikes."""
        # 1. High Download Speed Alert
        if self._policy.is_enabled(NotificationType.HIGH_DOWNLOAD_SPEED):
            if self._policy.evaluate_high_download(sample.download_bps):
                self._dispatch_high_download(sample)

        # 2. High Upload Speed Alert
        if self._policy.is_enabled(NotificationType.HIGH_UPLOAD_SPEED):
            if self._policy.evaluate_high_upload(sample.upload_bps):
                self._dispatch_high_upload(sample)

        # 3. High Data Usage Alert
        if self._policy.is_enabled(NotificationType.HIGH_DATA_USAGE) and sample.network_id:
            # Add delta if possible or use cumulative session bytes
            delta = sample.download_bps + sample.upload_bps
            self._current_network_session_bytes += int(delta)
            if self._policy.evaluate_data_usage(sample.network_id, self._current_network_session_bytes):
                self._dispatch_high_data_usage(sample, self._current_network_session_bytes)

    # ------------------------------------------------------------------
    # Dispatch Helpers
    # ------------------------------------------------------------------

    def _dispatch_connected(self, context: NetworkContext) -> None:
        net_name = context.network.display_name
        iface = context.interface.bsd_name
        event = NotificationEvent(
            event_type=NotificationType.NETWORK_CONNECTED,
            title="Network Connected",
            body=f"Connected to {net_name} ({iface})",
            network_id=context.network.network_id,
            interface_id=context.interface.interface_id,
            severity=NotificationSeverity.INFO,
        )
        self._emit_event(event)

    def _dispatch_restored(self, context: NetworkContext) -> None:
        net_name = context.network.display_name
        event = NotificationEvent(
            event_type=NotificationType.CONNECTION_RESTORED,
            title="Connection Restored",
            body=f"Reconnected to {net_name}",
            network_id=context.network.network_id,
            interface_id=context.interface.interface_id,
            severity=NotificationSeverity.INFO,
        )
        self._emit_event(event)

    def _dispatch_disconnected(self, prev_context: NetworkContext) -> None:
        prev_name = prev_context.network.display_name
        event = NotificationEvent(
            event_type=NotificationType.NETWORK_DISCONNECTED,
            title="Network Disconnected",
            body=f"Disconnected from {prev_name}",
            network_id=prev_context.network.network_id,
            interface_id=prev_context.interface.interface_id,
            severity=NotificationSeverity.WARNING,
        )
        self._emit_event(event)

    def _dispatch_changed(self, prev_ctx: NetworkContext, new_ctx: NetworkContext) -> None:
        p_name = prev_ctx.network.display_name
        n_name = new_ctx.network.display_name
        event = NotificationEvent(
            event_type=NotificationType.NETWORK_CHANGED,
            title="Network Changed",
            body=f"{p_name} → {n_name}",
            network_id=new_ctx.network.network_id,
            interface_id=new_ctx.interface.interface_id,
            severity=NotificationSeverity.INFO,
        )
        self._emit_event(event)

    def _dispatch_weak_signal(self, context: NetworkContext) -> None:
        rssi = context.rssi
        net_name = context.network.display_name
        event = NotificationEvent(
            event_type=NotificationType.WEAK_SIGNAL,
            title="Weak Wi-Fi Signal",
            body=f"Signal for {net_name} dropped to {rssi} dBm",
            network_id=context.network.network_id,
            interface_id=context.interface.interface_id,
            severity=NotificationSeverity.WARNING,
            metadata={"rssi": rssi},
        )
        self._emit_event(event)

    def _dispatch_high_download(self, sample: NetworkSample) -> None:
        speed_str = format_speed(sample.download_bps, unit="auto")
        thresh_mbps = self._prefs.preferences.download_speed_threshold_mbps
        event = NotificationEvent(
            event_type=NotificationType.HIGH_DOWNLOAD_SPEED,
            title="High Download Activity",
            body=f"Download speed exceeded {thresh_mbps:.0f} MB/s ({speed_str})",
            network_id=sample.network_id,
            interface_id=sample.interface_id,
            severity=NotificationSeverity.INFO,
            metadata={"speed_bps": sample.download_bps},
        )
        self._emit_event(event)

    def _dispatch_high_upload(self, sample: NetworkSample) -> None:
        speed_str = format_speed(sample.upload_bps, unit="auto")
        thresh_mbps = self._prefs.preferences.upload_speed_threshold_mbps
        event = NotificationEvent(
            event_type=NotificationType.HIGH_UPLOAD_SPEED,
            title="High Upload Activity",
            body=f"Upload speed exceeded {thresh_mbps:.0f} MB/s ({speed_str})",
            network_id=sample.network_id,
            interface_id=sample.interface_id,
            severity=NotificationSeverity.INFO,
            metadata={"speed_bps": sample.upload_bps},
        )
        self._emit_event(event)

    def _dispatch_high_data_usage(self, sample: NetworkSample, total_bytes: int) -> None:
        usage_str = format_bytes(total_bytes)
        thresh_gb = self._prefs.preferences.data_usage_threshold_gb
        event = NotificationEvent(
            event_type=NotificationType.HIGH_DATA_USAGE,
            title="High Data Usage",
            body=f"Data usage crossed {thresh_gb:.1f} GB ({usage_str})",
            network_id=sample.network_id,
            interface_id=sample.interface_id,
            severity=NotificationSeverity.WARNING,
            metadata={"total_bytes": total_bytes},
        )
        self._emit_event(event)

    def _emit_event(self, event: NotificationEvent) -> None:
        """Filter through policy, record history, and deliver."""
        if not self._policy.should_deliver(event):
            return

        with self._lock:
            self._recent_events.append(event)
            listeners = list(self._event_listeners)

        # Notify policy of delivery
        self._policy.record_delivery(event)

        # Dispatch via backend
        try:
            self._backend.send(event)
        except Exception:
            logger.exception("Backend failed to deliver notification")

        # Notify in-process listeners (e.g. UIBridge)
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Notification listener raised an error")
