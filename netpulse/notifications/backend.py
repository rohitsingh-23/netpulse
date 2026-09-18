"""Pluggable notification backends for NetPulse.

Abstracts platform-native delivery from application logic so that unit
testing and future bundle packaging can be handled without modifying
event detection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import platform
from typing import List, Optional

from netpulse.notifications.models import NotificationEvent
from netpulse.utils.log import get_logger

logger = get_logger("notifications.backend")


class NotificationBackend(ABC):
    """Abstract interface for dispatching notifications."""

    @abstractmethod
    def send(self, event: NotificationEvent) -> bool:
        """Send a notification.

        Args:
            event: The notification event to deliver.

        Returns:
            True if delivery succeeded or was queued, False otherwise.
        """
        raise NotImplementedError


class MockNotificationBackend(NotificationBackend):
    """In-memory mock backend for tests and headless verification."""

    def __init__(self) -> None:
        self.delivered_events: List[NotificationEvent] = []

    def send(self, event: NotificationEvent) -> bool:
        self.delivered_events.append(event)
        return True

    def clear(self) -> None:
        self.delivered_events.clear()


class MacOSNotificationBackend(NotificationBackend):
    """Modern native macOS notification backend using UserNotifications.framework.

    Uses Apple's supported UNUserNotificationCenter, UNMutableNotificationContent,
    and UNNotificationRequest APIs introduced in macOS 10.14+ (replacing the deprecated
    NSUserNotificationCenter).

    In development mode (unbundled Python), requests authorization from the user
    and dispatches requests via UNUserNotificationCenter. In packaged mode (.app),
    it integrates with the app's bundle identifier and permission entitlements.
    """

    # UNAuthorizationOptionBadge (1), Sound (2), Alert (4) -> 7 (or Sound | Alert = 6)
    AUTH_OPTIONS = (1 << 2) | (1 << 1)  # Alert | Sound

    def __init__(self) -> None:
        self._available = False
        self._notification_center = None
        self._content_cls = None
        self._request_cls = None
        self._sound_cls = None
        self._auth_requested = False
        self._auth_granted: Optional[bool] = None
        self._init_backend()

    def _init_backend(self) -> None:
        if platform.system() != "Darwin":
            return
        try:
            import objc

            objc.loadBundle(
                "UserNotifications",
                bundle_path="/System/Library/Frameworks/UserNotifications.framework",
                module_globals=globals(),
            )

            # Register block signatures for PyObjC if not already defined
            try:
                objc.registerMetaDataForSelector(
                    b"UNUserNotificationCenter",
                    b"requestAuthorizationWithOptions:completionHandler:",
                    {
                        "arguments": {
                            3: {
                                "callable": {
                                    "retval": {"type": b"v"},
                                    "arguments": {
                                        0: {"type": b"^v"},
                                        1: {"type": b"Z"},
                                        2: {"type": b"@"},
                                    },
                                }
                            }
                        }
                    },
                )
            except Exception:
                pass

            try:
                objc.registerMetaDataForSelector(
                    b"UNUserNotificationCenter",
                    b"addNotificationRequest:withCompletionHandler:",
                    {
                        "arguments": {
                            3: {
                                "callable": {
                                    "retval": {"type": b"v"},
                                    "arguments": {
                                        0: {"type": b"^v"},
                                        1: {"type": b"@"},
                                    },
                                }
                            }
                        }
                    },
                )
            except Exception:
                pass

            self._center_cls = objc.lookUpClass("UNUserNotificationCenter")
            self._content_cls = objc.lookUpClass("UNMutableNotificationContent")
            self._request_cls = objc.lookUpClass("UNNotificationRequest")
            self._sound_cls = objc.lookUpClass("UNNotificationSound")

            if self._center_cls:
                self._notification_center = self._center_cls.currentNotificationCenter()
                self._available = True
                self._request_authorization()
        except Exception as e:
            logger.debug("Failed to initialize UserNotifications.framework: %s", e)
            self._available = False

    def _request_authorization(self) -> None:
        """Request UserNotifications authorization asynchronously."""
        if not self._available or not self._notification_center or self._auth_requested:
            return

        self._auth_requested = True

        def auth_completion(granted: bool, error: object) -> None:
            self._auth_granted = bool(granted)
            if error:
                logger.debug("Notification authorization error: %s", error)
            else:
                logger.info("Notification authorization status: granted=%s", granted)

        try:
            self._notification_center.requestAuthorizationWithOptions_completionHandler_(
                self.AUTH_OPTIONS,
                auth_completion,
            )
        except Exception as e:
            logger.debug("Could not request notification authorization: %s", e)

    def send(self, event: NotificationEvent) -> bool:
        """Deliver notification via UNUserNotificationCenter."""
        if not self._available or not self._notification_center:
            logger.debug(
                "Native UserNotifications unavailable. Skipped: %s - %s",
                event.title,
                event.body,
            )
            return False

        try:
            content = self._content_cls.alloc().init()
            content.setTitle_(event.title)
            content.setBody_(event.body)
            if self._sound_cls:
                try:
                    content.setSound_(self._sound_cls.defaultSound())
                except Exception:
                    pass

            # Deterministic unique identifier per request
            identifier = f"netpulse-{event.event_type.value}-{event.timestamp.timestamp()}"
            request = self._request_cls.requestWithIdentifier_content_trigger_(
                identifier,
                content,
                None,  # Deliver immediately
            )

            def completion_handler(error: object) -> None:
                if error:
                    logger.debug("UNUserNotificationCenter delivery error: %s", error)

            self._notification_center.addNotificationRequest_withCompletionHandler_(
                request,
                completion_handler,
            )
            logger.debug("Dispatched UserNotification: %s - %s", event.title, event.body)
            return True
        except Exception as e:
            logger.warning("Error dispatching notification via UserNotifications: %s", e)
            return False
