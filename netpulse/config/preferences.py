"""Persistent preferences storage.

Uses a JSON file in ``~/Library/Application Support/NetPulse/``.
Tolerates missing files, missing fields, and corrupted data —
always falls back to defaults rather than crashing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from netpulse.config.models import (
    AppPreferences,
    DisplayMode,
    UnitMode,
    VALID_INTERVALS,
)
from netpulse.utils.constants import APP_NAME
from netpulse.utils.log import get_logger

logger = get_logger("preferences")


def _default_prefs_dir() -> Path:
    """macOS-conventional application support directory."""
    return Path.home() / "Library" / "Application Support" / APP_NAME


class PreferencesManager:
    """Load, save, and manage application preferences.

    Falls back to defaults if the preferences file is missing,
    corrupted, or contains invalid values. Logs warnings but
    never crashes the application.

    Args:
        path: Explicit path to the preferences JSON file.
            Defaults to ``~/Library/Application Support/NetPulse/preferences.json``.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or (_default_prefs_dir() / "preferences.json")
        self._prefs = AppPreferences()
        self._subscribers: list = []

    @property
    def preferences(self) -> AppPreferences:
        """Current in-memory preferences."""
        return self._prefs

    @property
    def path(self) -> Path:
        """Path to the preferences file."""
        return self._path

    def load(self) -> AppPreferences:
        """Load preferences from disk.

        Returns defaults if the file doesn't exist, is corrupted,
        or contains invalid values.
        """
        if not self._path.exists():
            logger.info("No preferences file, using defaults")
            self._prefs = AppPreferences()
            return self._prefs

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupted preferences, falling back to defaults: %s", exc)
            self._prefs = AppPreferences()
            return self._prefs

        if not isinstance(data, dict):
            logger.warning("Preferences file is not a JSON object, using defaults")
            self._prefs = AppPreferences()
            return self._prefs

        self._prefs = self._parse(data)
        return self._prefs

    def subscribe(self, callback: Any) -> None:
        """Register a callback for preference changes."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Any) -> None:
        """Unregister a preference change callback."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify_subscribers(self) -> None:
        """Notify registered listeners of updated preferences."""
        for cb in list(self._subscribers):
            try:
                cb(self._prefs)
            except Exception:
                logger.exception("Error notifying preferences subscriber")

    def save(self) -> None:
        """Persist current preferences to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "display_mode": self._prefs.display_mode.value,
                "unit_mode": self._prefs.unit_mode.value,
                "sample_interval": self._prefs.sample_interval,
                "appearance": self._prefs.appearance.value,
                "enable_mascot": self._prefs.enable_mascot,
                "notifications_enabled": self._prefs.notifications_enabled,
                "notify_network_connected": self._prefs.notify_network_connected,
                "notify_network_disconnected": self._prefs.notify_network_disconnected,
                "notify_network_changed": self._prefs.notify_network_changed,
                "notify_connection_restored": self._prefs.notify_connection_restored,
                "notify_weak_signal": self._prefs.notify_weak_signal,
                "notify_high_download_speed": self._prefs.notify_high_download_speed,
                "notify_high_upload_speed": self._prefs.notify_high_upload_speed,
                "notify_high_data_usage": self._prefs.notify_high_data_usage,
                "start_at_login": self._prefs.start_at_login,
                "weak_signal_rssi_threshold": self._prefs.weak_signal_rssi_threshold,
                "download_speed_threshold_mbps": self._prefs.download_speed_threshold_mbps,
                "upload_speed_threshold_mbps": self._prefs.upload_speed_threshold_mbps,
                "data_usage_threshold_gb": self._prefs.data_usage_threshold_gb,
            }
            self._path.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to save preferences")

    def update(self, **kwargs: Any) -> None:
        """Update preference fields, validate, and save.

        Example::

            manager.update(display_mode=DisplayMode.COMPACT)
        """
        for key, value in kwargs.items():
            if hasattr(self._prefs, key):
                setattr(self._prefs, key, value)
        # Re-validate to catch bad values
        self._prefs.__post_init__()
        self.save()
        self._notify_subscribers()

    def reset_to_defaults(self) -> AppPreferences:
        """Reset all preferences to initial default values and persist to disk."""
        self._prefs = AppPreferences()
        self.save()
        self._notify_subscribers()
        logger.info("Preferences reset to defaults and saved to %s", self._path)
        return self._prefs

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse(self, data: Dict[str, Any]) -> AppPreferences:
        """Parse a dict into AppPreferences, using defaults for invalid fields."""
        prefs = AppPreferences()

        # display_mode
        dm_raw = data.get("display_mode")
        if dm_raw is not None:
            try:
                prefs.display_mode = DisplayMode(dm_raw)
            except ValueError:
                logger.warning("Invalid display_mode %r, using default", dm_raw)

        # unit_mode
        um_raw = data.get("unit_mode")
        if um_raw is not None:
            try:
                prefs.unit_mode = UnitMode(um_raw)
            except ValueError:
                logger.warning("Invalid unit_mode %r, using default", um_raw)

        # sample_interval
        si_raw = data.get("sample_interval")
        if si_raw is not None:
            try:
                si = float(si_raw)
                if si in VALID_INTERVALS:
                    prefs.sample_interval = si
                else:
                    logger.warning("Invalid sample_interval %r, using default", si_raw)
            except (ValueError, TypeError):
                logger.warning("Invalid sample_interval %r, using default", si_raw)

        # appearance
        app_raw = data.get("appearance")
        if app_raw is not None:
            try:
                from netpulse.config.models import AppearanceMode
                prefs.appearance = AppearanceMode(app_raw)
            except ValueError:
                logger.warning("Invalid appearance %r, using default", app_raw)

        # Mascot boolean setting
        if "enable_mascot" in data and isinstance(data["enable_mascot"], bool):
            prefs.enable_mascot = data["enable_mascot"]
        elif "mascot_enabled" in data and isinstance(data["mascot_enabled"], bool):
            prefs.enable_mascot = data["mascot_enabled"]

        # Notification boolean settings
        bool_keys = [
            "notifications_enabled",
            "notify_network_connected",
            "notify_network_disconnected",
            "notify_network_changed",
            "notify_connection_restored",
            "notify_weak_signal",
            "notify_high_download_speed",
            "notify_high_upload_speed",
            "notify_high_data_usage",
            "start_at_login",
        ]
        for key in bool_keys:
            if key in data and isinstance(data[key], bool):
                setattr(prefs, key, data[key])

        # Notification thresholds
        if "weak_signal_rssi_threshold" in data:
            try:
                prefs.weak_signal_rssi_threshold = int(data["weak_signal_rssi_threshold"])
            except (ValueError, TypeError):
                pass

        if "download_speed_threshold_mbps" in data:
            try:
                prefs.download_speed_threshold_mbps = float(data["download_speed_threshold_mbps"])
            except (ValueError, TypeError):
                pass

        if "upload_speed_threshold_mbps" in data:
            try:
                prefs.upload_speed_threshold_mbps = float(data["upload_speed_threshold_mbps"])
            except (ValueError, TypeError):
                pass

        if "data_usage_threshold_gb" in data:
            try:
                prefs.data_usage_threshold_gb = float(data["data_usage_threshold_gb"])
            except (ValueError, TypeError):
                pass

        prefs.__post_init__()
        return prefs
