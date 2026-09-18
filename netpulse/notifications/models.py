"""Strongly-typed data models for the NetPulse notification subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class NotificationType(Enum):
    """Categorized types of network notification events."""

    NETWORK_CONNECTED = "network_connected"
    NETWORK_DISCONNECTED = "network_disconnected"
    NETWORK_CHANGED = "network_changed"
    CONNECTION_RESTORED = "connection_restored"
    WEAK_SIGNAL = "weak_signal"
    HIGH_DOWNLOAD_SPEED = "high_download_speed"
    HIGH_UPLOAD_SPEED = "high_upload_speed"
    HIGH_DATA_USAGE = "high_data_usage"


class NotificationSeverity(Enum):
    """Visual/urgency severity of a notification."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class NotificationEvent:
    """Immutable model representing an evaluated notification event.

    Attributes:
        event_type: Category of event.
        timestamp: Time of event creation in UTC.
        title: Short bold notification title.
        body: Informative notification body text (no private data/BSSIDs).
        network_id: Stable network identity if applicable.
        interface_id: Interface ID if applicable.
        severity: Severity level.
        metadata: Extra structured metadata for inspection or testing.
    """

    event_type: NotificationType
    title: str
    body: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    network_id: Optional[str] = None
    interface_id: Optional[str] = None
    severity: NotificationSeverity = NotificationSeverity.INFO
    metadata: Dict[str, Any] = field(default_factory=dict)
