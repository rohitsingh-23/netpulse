"""Bridge for safely passing data from background threads to PySide6.

The NetworkMonitor runs in a background daemon thread.
Qt requires all UI updates to happen on the main thread.
By emitting a Qt Signal, Qt automatically uses a queued connection
to run the slot on the main thread.
"""

from PySide6.QtCore import QObject, Signal

from netpulse.core.network_sample import NetworkSample


class UIBridge(QObject):
    """Bridges NetworkMonitor callbacks to Qt signals.

    Must be instantiated on the main Qt thread.
    """

    # Signal that emits the latest NetworkSample
    sample_received = Signal(object)

    # Signal that emits the latest NetworkContext
    network_context_updated = Signal(object)

    # Signal that emits evaluated NotificationEvent
    notification_event_emitted = Signal(object)

    def dispatch_sample(self, sample: NetworkSample) -> None:
        """Callback to be registered with NetworkMonitor.

        Can be called from any thread.
        Emits the sample_received signal to safely jump to the main thread.
        """
        self.sample_received.emit(sample)

    def dispatch_context(self, context: object) -> None:
        """Callback to be registered with NetworkContextManager.

        Can be called from any thread.
        Emits the network_context_updated signal to safely jump to the main thread.
        """
        self.network_context_updated.emit(context)

    def dispatch_notification(self, event: object) -> None:
        """Callback to be registered with NotificationEngine.

        Can be called from any thread.
        Emits the notification_event_emitted signal on the main Qt thread.
        """
        self.notification_event_emitted.emit(event)
