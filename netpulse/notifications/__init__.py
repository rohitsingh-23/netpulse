"""Notification subsystem for NetPulse."""

from netpulse.notifications.backend import (
    MacOSNotificationBackend,
    MockNotificationBackend,
    NotificationBackend,
)
from netpulse.notifications.engine import NotificationEngine
from netpulse.notifications.models import (
    NotificationEvent,
    NotificationSeverity,
    NotificationType,
)
from netpulse.notifications.policy import NotificationPolicy

__all__ = [
    "MacOSNotificationBackend",
    "MockNotificationBackend",
    "NotificationBackend",
    "NotificationEngine",
    "NotificationEvent",
    "NotificationPolicy",
    "NotificationSeverity",
    "NotificationType",
]
