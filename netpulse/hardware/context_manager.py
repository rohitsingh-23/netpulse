"""Network connection context coordinator.

Discovers active hardware interfaces, queries CoreWLAN for Wi-Fi details,
resolves primary network routing, and emits immutable NetworkContext updates
on a controlled 5–10 second cadence without blocking speed sampling.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Callable, List, Optional

from netpulse.core.interface_identity import InterfaceIdentity
from netpulse.core.network_context import NetworkContext
from netpulse.core.network_identity import NetworkIdentity
from netpulse.hardware.discovery import NetworkDiscovery
from netpulse.hardware.wifi import WiFiInspector
from netpulse.utils.log import get_logger

logger = get_logger("context_manager")

ContextCallback = Callable[[NetworkContext], None]


class NetworkContextManager:
    """Manages active network context and interface state."""

    DEFAULT_METADATA_INTERVAL = 6.0  # seconds between RF/metadata refreshes

    def __init__(
        self,
        discovery: Optional[NetworkDiscovery] = None,
        wifi_inspector: Optional[WiFiInspector] = None,
        refresh_interval: float = DEFAULT_METADATA_INTERVAL,
    ) -> None:
        self._discovery = discovery or NetworkDiscovery()
        self._wifi = wifi_inspector or WiFiInspector()
        self._refresh_interval = refresh_interval

        self._lock = threading.Lock()
        self._subscribers: List[ContextCallback] = []
        self._current_context: NetworkContext = NetworkContext.disconnected()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Immediate first synchronous resolution
        self._resolve_context()

    @property
    def current_context(self) -> NetworkContext:
        """Current immutable connection context."""
        with self._lock:
            return self._current_context

    def subscribe(self, callback: ContextCallback) -> None:
        """Register a callback to receive NetworkContext updates."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: ContextCallback) -> None:
        """Unregister a previously registered callback."""
        with self._lock:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

    def start(self) -> None:
        """Start background context polling loop."""
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="NetPulse-ContextManager",
            daemon=True,
        )
        self._thread.start()
        logger.info("NetworkContextManager started (interval=%.1fs)", self._refresh_interval)

    def stop(self) -> None:
        """Stop background context polling loop."""
        if not self._running:
            return
        self._stop_event.set()
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("NetworkContextManager stopped")

    def refresh_now(self) -> NetworkContext:
        """Force an immediate context refresh."""
        return self._resolve_context()

    def _run_loop(self) -> None:
        """Background metadata polling loop."""
        while not self._stop_event.is_set():
            try:
                self._resolve_context()
            except Exception:
                logger.exception("Error during context resolution")

            self._stop_event.wait(timeout=self._refresh_interval)

    def _resolve_context(self) -> NetworkContext:
        """Resolve current interface, Wi-Fi, and network identity."""
        try:
            interfaces = self._discovery.discover_interfaces()
            primary_iface = next((i for i in interfaces if i.is_primary), None)

            if not primary_iface:
                # If no primary found, pick first active non-system interface
                for i in interfaces:
                    if i.interface_type in ("wifi", "ethernet") and i.bsd_name != "lo0":
                        primary_iface = i
                        break

            if not primary_iface:
                ctx = NetworkContext.disconnected()
                self._update_context(ctx)
                return ctx

            ipv4, ipv6, router_ip = self._discovery.get_interface_ip_info(primary_iface.bsd_name)

            if primary_iface.interface_type == "wifi":
                wifi_details = self._wifi.inspect_wifi(primary_iface.bsd_name)
                if wifi_details and wifi_details.is_connected:
                    net_ident = NetworkIdentity.create_wifi(
                        ssid=wifi_details.ssid,
                        interface_id=primary_iface.interface_id,
                        bssid=wifi_details.bssid,
                        permission_restricted=wifi_details.permission_restricted,
                    )
                    ctx = NetworkContext(
                        timestamp=datetime.now(timezone.utc),
                        interface=primary_iface,
                        network=net_ident,
                        is_connected=True,
                        ipv4_address=ipv4,
                        ipv6_address=ipv6,
                        router_ip=router_ip,
                        rssi=wifi_details.rssi,
                        noise=wifi_details.noise,
                        channel=wifi_details.channel_number,
                        band=wifi_details.band,
                        channel_width=wifi_details.channel_width,
                        phy_mode=wifi_details.phy_mode,
                        transmit_rate_mbps=wifi_details.transmit_rate_mbps,
                        security=wifi_details.security,
                        permission_restricted=wifi_details.permission_restricted,
                    )
                else:
                    # Wi-Fi interface exists but not connected to any AP
                    ctx = NetworkContext(
                        timestamp=datetime.now(timezone.utc),
                        interface=primary_iface,
                        network=NetworkIdentity(
                            network_id=f"wifi-disconnected:{primary_iface.interface_id}",
                            connection_type="wifi",
                            ssid=None,
                            display_name="Wi-Fi Not Connected",
                            interface_id=primary_iface.interface_id,
                        ),
                        is_connected=False,
                        ipv4_address=ipv4,
                        ipv6_address=ipv6,
                        router_ip=router_ip,
                    )
            elif primary_iface.interface_type == "ethernet":
                net_ident = NetworkIdentity.create_ethernet(
                    interface_id=primary_iface.interface_id,
                    display_name=primary_iface.display_name or f"Ethernet ({primary_iface.bsd_name})",
                )
                ctx = NetworkContext(
                    timestamp=datetime.now(timezone.utc),
                    interface=primary_iface,
                    network=net_ident,
                    is_connected=bool(ipv4 or ipv6),
                    ipv4_address=ipv4,
                    ipv6_address=ipv6,
                    router_ip=router_ip,
                )
            else:
                # Other / VPN / Bridge
                ctx = NetworkContext(
                    timestamp=datetime.now(timezone.utc),
                    interface=primary_iface,
                    network=NetworkIdentity(
                        network_id=f"{primary_iface.interface_type}:{primary_iface.interface_id}",
                        connection_type=primary_iface.interface_type,
                        ssid=None,
                        display_name=primary_iface.display_name,
                        interface_id=primary_iface.interface_id,
                    ),
                    is_connected=bool(ipv4 or ipv6),
                    ipv4_address=ipv4,
                    ipv6_address=ipv6,
                    router_ip=router_ip,
                )

            self._update_context(ctx)
            return ctx
        except Exception:
            logger.exception("Failed resolving network context")
            return self._current_context

    def _update_context(self, new_ctx: NetworkContext) -> None:
        """Update current context and notify subscribers if changed."""
        with self._lock:
            old_ctx = self._current_context
            self._current_context = new_ctx
            subscribers = list(self._subscribers)

        # Notify if any significant field changed
        changed = (
            old_ctx.is_connected != new_ctx.is_connected
            or old_ctx.network.network_id != new_ctx.network.network_id
            or old_ctx.interface.interface_id != new_ctx.interface.interface_id
            or old_ctx.rssi != new_ctx.rssi
            or old_ctx.channel != new_ctx.channel
            or old_ctx.transmit_rate_mbps != new_ctx.transmit_rate_mbps
        )
        if changed:
            for cb in subscribers:
                try:
                    cb(new_ctx)
                except Exception:
                    logger.exception("Context subscriber raised exception")
