"""Strongly-typed configuration models for NetPulse.

Enums prevent string-literal scattering. AppPreferences validates
fields on construction so the rest of the app can trust the values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DisplayMode(Enum):
    """Menu-bar display format."""

    DOWNLOAD_UPLOAD = "download_upload"
    DOWNLOAD_ONLY = "download_only"
    UPLOAD_ONLY = "upload_only"
    COMPACT = "compact"
    SMART = "smart"


class UnitMode(Enum):
    """Speed display unit."""

    AUTO = "auto"
    KB = "KB"
    MB = "MB"
    GB = "GB"


class AppearanceMode(Enum):
    """UI appearance theme."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


# Allowed sample intervals in seconds
VALID_INTERVALS = (0.5, 1.0, 2.0, 5.0)
DEFAULT_INTERVAL = 1.0

# Human-readable labels for menu items
DISPLAY_MODE_LABELS = {
    DisplayMode.DOWNLOAD_UPLOAD: "Download + Upload",
    DisplayMode.DOWNLOAD_ONLY: "Download Only",
    DisplayMode.UPLOAD_ONLY: "Upload Only",
    DisplayMode.COMPACT: "Compact",
    DisplayMode.SMART: "Smart",
}

UNIT_MODE_LABELS = {
    UnitMode.AUTO: "Automatic",
    UnitMode.KB: "KB/s",
    UnitMode.MB: "MB/s",
    UnitMode.GB: "GB/s",
}

APPEARANCE_MODE_LABELS = {
    AppearanceMode.SYSTEM: "System",
    AppearanceMode.LIGHT: "Light",
    AppearanceMode.DARK: "Dark",
}

INTERVAL_LABELS = {
    0.5: "0.5 seconds",
    1.0: "1 second",
    2.0: "2 seconds",
    5.0: "5 seconds",
}


@dataclass
class AppPreferences:
    """Application preferences with validated defaults.

    Invalid values are silently corrected to defaults so the app
    never operates with broken configuration.
    """

    display_mode: DisplayMode = DisplayMode.DOWNLOAD_UPLOAD
    unit_mode: UnitMode = UnitMode.AUTO
    sample_interval: float = DEFAULT_INTERVAL
    appearance: AppearanceMode = AppearanceMode.SYSTEM

    # Notification preferences
    notifications_enabled: bool = True
    notify_network_connected: bool = True
    notify_network_disconnected: bool = True
    notify_network_changed: bool = True
    notify_connection_restored: bool = False
    notify_weak_signal: bool = True
    notify_high_download_speed: bool = False
    notify_high_upload_speed: bool = False
    notify_high_data_usage: bool = False

    # Startup
    start_at_login: bool = True

    # Mascot
    enable_mascot: bool = True

    # Notification thresholds
    weak_signal_rssi_threshold: int = -75  # dBm (triggers <= -75)
    download_speed_threshold_mbps: float = 100.0  # MB/s
    upload_speed_threshold_mbps: float = 50.0  # MB/s
    data_usage_threshold_gb: float = 5.0  # GB

    def __post_init__(self) -> None:
        # Validate display_mode
        if not isinstance(self.display_mode, DisplayMode):
            self.display_mode = DisplayMode.DOWNLOAD_UPLOAD
        # Validate unit_mode
        if not isinstance(self.unit_mode, UnitMode):
            self.unit_mode = UnitMode.AUTO
        # Validate sample_interval
        if self.sample_interval not in VALID_INTERVALS:
            self.sample_interval = DEFAULT_INTERVAL
        # Validate appearance
        if not isinstance(self.appearance, AppearanceMode):
            self.appearance = AppearanceMode.SYSTEM

        # Validate boolean settings
        for attr in [
            "enable_mascot",
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
        ]:
            val = getattr(self, attr)
            if not isinstance(val, bool):
                setattr(self, attr, bool(val))

        # Validate thresholds
        try:
            self.weak_signal_rssi_threshold = int(self.weak_signal_rssi_threshold)
            # RSSI is typically between -100 and 0 dBm
            if not (-100 <= self.weak_signal_rssi_threshold <= -30):
                self.weak_signal_rssi_threshold = -75
        except (ValueError, TypeError):
            self.weak_signal_rssi_threshold = -75

        try:
            self.download_speed_threshold_mbps = float(self.download_speed_threshold_mbps)
            if self.download_speed_threshold_mbps <= 0:
                self.download_speed_threshold_mbps = 100.0
        except (ValueError, TypeError):
            self.download_speed_threshold_mbps = 100.0

        try:
            self.upload_speed_threshold_mbps = float(self.upload_speed_threshold_mbps)
            if self.upload_speed_threshold_mbps <= 0:
                self.upload_speed_threshold_mbps = 50.0
        except (ValueError, TypeError):
            self.upload_speed_threshold_mbps = 50.0

        try:
            self.data_usage_threshold_gb = float(self.data_usage_threshold_gb)
            if self.data_usage_threshold_gb <= 0:
                self.data_usage_threshold_gb = 5.0
        except (ValueError, TypeError):
            self.data_usage_threshold_gb = 5.0
