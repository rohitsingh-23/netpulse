"""Notification policy governing deduplication, rate-limiting, and hysteresis.

Ensures that NetPulse remains quiet by default and never spams the user.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from netpulse.notifications.models import NotificationEvent, NotificationType
from netpulse.utils.log import get_logger

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager

logger = get_logger("notifications.policy")


class NotificationPolicy:
    """Evaluates whether candidate notification events should be delivered.

    Enforces:
    1. User preference toggles (master enable and per-event settings).
    2. Cooldown windows (prevents rapid repetitive alerts).
    3. Payload deduplication.
    4. State hysteresis for metrics (weak signal, high download/upload speed, data usage).
    """

    # Default cooldowns in seconds
    DEFAULT_COOLDOWNS: Dict[NotificationType, float] = {
        NotificationType.NETWORK_CONNECTED: 5.0,
        NotificationType.NETWORK_DISCONNECTED: 5.0,
        NotificationType.NETWORK_CHANGED: 5.0,
        NotificationType.CONNECTION_RESTORED: 5.0,
        NotificationType.WEAK_SIGNAL: 60.0,
        NotificationType.HIGH_DOWNLOAD_SPEED: 45.0,
        NotificationType.HIGH_UPLOAD_SPEED: 45.0,
        NotificationType.HIGH_DATA_USAGE: 300.0,
    }

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        cooldowns: Optional[Dict[NotificationType, float]] = None,
    ) -> None:
        self._prefs = prefs_manager
        self._cooldowns = dict(self.DEFAULT_COOLDOWNS)
        if cooldowns:
            self._cooldowns.update(cooldowns)

        # Tracking last delivery timestamps: (NotificationType, Optional[network_id]) -> timestamp
        self._last_delivered: Dict[Tuple[NotificationType, Optional[str]], float] = {}
        # Tracking last delivered message body for deduplication
        self._last_body: Dict[NotificationType, str] = {}

        # Hysteresis state tracking
        # Wi-Fi weak signal: True if currently inside weak state (armed to recover)
        self._is_in_weak_signal: bool = False

        # High download speed: True if currently in high speed state
        self._is_in_high_download: bool = False

        # High upload speed: True if currently in high upload state
        self._is_in_high_upload: bool = False

        # Data usage alerts: set of network_ids that have already alerted this session/cycle
        self._alerted_data_usage_networks: set[str] = set()

    def reset_state(self) -> None:
        """Reset all cooldown tracking, deduplication history, and hysteresis flags."""
        self._last_delivered.clear()
        self._last_body.clear()
        self._is_in_weak_signal = False
        self._is_in_high_download = False
        self._is_in_high_upload = False
        self._alerted_data_usage_networks.clear()
        logger.info("NotificationPolicy cooldowns, deduplication, and hysteresis states reset")

    # ------------------------------------------------------------------
    # Policy Evaluation
    # ------------------------------------------------------------------

    def is_enabled(self, event_type: NotificationType) -> bool:
        """Check if notifications and this specific category are enabled in preferences."""
        prefs = self._prefs.preferences
        if not prefs.notifications_enabled:
            return False

        mapping = {
            NotificationType.NETWORK_CONNECTED: prefs.notify_network_connected,
            NotificationType.NETWORK_DISCONNECTED: prefs.notify_network_disconnected,
            NotificationType.NETWORK_CHANGED: prefs.notify_network_changed,
            NotificationType.CONNECTION_RESTORED: prefs.notify_connection_restored,
            NotificationType.WEAK_SIGNAL: prefs.notify_weak_signal,
            NotificationType.HIGH_DOWNLOAD_SPEED: prefs.notify_high_download_speed,
            NotificationType.HIGH_UPLOAD_SPEED: prefs.notify_high_upload_speed,
            NotificationType.HIGH_DATA_USAGE: prefs.notify_high_data_usage,
        }
        return mapping.get(event_type, False)

    def should_deliver(self, event: NotificationEvent, now: Optional[float] = None) -> bool:
        """Determine if an event passes preference, cooldown, and deduplication rules."""
        if not self.is_enabled(event.event_type):
            return False

        current_time = now if now is not None else time.monotonic()
        key = (event.event_type, event.network_id)
        last_time = self._last_delivered.get(key)
        cooldown = self._cooldowns.get(event.event_type, 10.0)

        if last_time is not None and (current_time - last_time < cooldown):
            logger.debug(
                "Event %s suppressed by cooldown (%.1fs < %.1fs)",
                event.event_type.value,
                current_time - last_time,
                cooldown,
            )
            return False

        # Deduplication check for identical message body if delivered recently
        if (
            last_time is not None
            and self._last_body.get(event.event_type) == event.body
            and (current_time - last_time < cooldown * 2)
        ):
            logger.debug("Duplicate event %s body suppressed", event.event_type.value)
            return False


        return True

    def record_delivery(self, event: NotificationEvent, now: Optional[float] = None) -> None:
        """Record that an event was successfully dispatched."""
        current_time = now if now is not None else time.monotonic()
        key = (event.event_type, event.network_id)
        self._last_delivered[key] = current_time
        self._last_body[event.event_type] = event.body

    # ------------------------------------------------------------------
    # Hysteresis Evaluators
    # ------------------------------------------------------------------

    def evaluate_weak_signal(self, rssi: Optional[int]) -> bool:
        """Evaluate Wi-Fi RSSI with hysteresis.

        Hysteresis rules:
            weak threshold: <= weak_signal_rssi_threshold (default -75 dBm)
            recovery threshold: >= weak_signal_rssi_threshold + 5 dBm (default -70 dBm)

        Returns:
            True only when transitioning from Normal -> Weak.
        """
        if rssi is None or rssi == 0:
            # If RSSI is invalid, reset state silently
            self._is_in_weak_signal = False
            return False

        weak_thresh = self._prefs.preferences.weak_signal_rssi_threshold
        recovery_thresh = weak_thresh + 5

        if self._is_in_weak_signal:
            # Currently in weak signal state; wait for recovery
            if rssi >= recovery_thresh:
                logger.debug("Wi-Fi signal recovered to %d dBm (>= %d dBm)", rssi, recovery_thresh)
                self._is_in_weak_signal = False
            return False
        else:
            # Currently in normal state; check if crossing into weak
            if rssi <= weak_thresh:
                logger.debug("Wi-Fi signal became weak at %d dBm (<= %d dBm)", rssi, weak_thresh)
                self._is_in_weak_signal = True
                return True
            return False

    def evaluate_high_download(self, download_bps: float) -> bool:
        """Evaluate instantaneous download speed with hysteresis.

        Trigger: download_bytes_sec > threshold_mbps * 1,000,000
        Recovery: download_bytes_sec < threshold_mbps * 1,000,000 * 0.8 (80%)

        Returns:
            True only when transitioning from Normal -> High.
        """
        thresh_bytes = self._prefs.preferences.download_speed_threshold_mbps * 1_000_000
        recovery_bytes = thresh_bytes * 0.8

        if self._is_in_high_download:
            if download_bps < recovery_bytes:
                self._is_in_high_download = False
            return False
        else:
            if download_bps >= thresh_bytes:
                self._is_in_high_download = True
                return True
            return False

    def evaluate_high_upload(self, upload_bps: float) -> bool:
        """Evaluate instantaneous upload speed with hysteresis.

        Trigger: upload_bytes_sec > threshold_mbps * 1,000,000
        Recovery: upload_bytes_sec < threshold_mbps * 1,000,000 * 0.8 (80%)

        Returns:
            True only when transitioning from Normal -> High.
        """
        thresh_bytes = self._prefs.preferences.upload_speed_threshold_mbps * 1_000_000
        recovery_bytes = thresh_bytes * 0.8

        if self._is_in_high_upload:
            if upload_bps < recovery_bytes:
                self._is_in_high_upload = False
            return False
        else:
            if upload_bps >= thresh_bytes:
                self._is_in_high_upload = True
                return True
            return False

    def evaluate_data_usage(self, network_id: Optional[str], session_bytes: int) -> bool:
        """Evaluate accumulated session/network data usage.

        Trigger: session_bytes >= threshold_gb * 1,073,741,824 (1 GB = 1024^3)
        Returns True once per network_id.
        """
        if not network_id:
            return False

        thresh_bytes = int(self._prefs.preferences.data_usage_threshold_gb * (1024**3))
        if session_bytes >= thresh_bytes and network_id not in self._alerted_data_usage_networks:
            self._alerted_data_usage_networks.add(network_id)
            return True
        return False

    def reset_network_state(self, new_network_id: Optional[str]) -> None:
        """Reset hysteresis state on network transition."""
        self._is_in_weak_signal = False
        self._is_in_high_download = False
        self._is_in_high_upload = False
