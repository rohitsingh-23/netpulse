"""Immutable network connection state snapshot.

Contains active interface and network identity along with RF/signal metrics,
IP addresses, and permission status. Decoupled from high-frequency NetworkSample.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from netpulse.core.interface_identity import InterfaceIdentity
from netpulse.core.network_identity import NetworkIdentity


@dataclass(frozen=True)
class NetworkContext:
    """Snapshot of active connection and RF/link metadata at a point in time."""

    timestamp: datetime
    interface: InterfaceIdentity
    network: NetworkIdentity
    is_connected: bool
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    router_ip: Optional[str] = None

    # Wi-Fi specific physical characteristics (None for Ethernet/other)
    rssi: Optional[int] = None                     # dBm (e.g. -57)
    noise: Optional[int] = None                    # dBm (e.g. -94)
    channel: Optional[int] = None                  # e.g. 44
    band: Optional[str] = None                     # "2.4 GHz", "5 GHz", "6 GHz"
    channel_width: Optional[str] = None            # "20 MHz", "40 MHz", "80 MHz", "160 MHz"
    phy_mode: Optional[str] = None                 # "Wi-Fi 6", "Wi-Fi 5", "Wi-Fi 4", etc.
    transmit_rate_mbps: Optional[float] = None     # e.g. 648.0
    security: Optional[str] = None                 # "WPA2 Personal", "WPA3 Personal", etc.

    # Privacy state
    permission_restricted: bool = False            # True if SSID blocked by macOS Location Services

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))

    @classmethod
    def disconnected(cls) -> NetworkContext:
        """Create a disconnected state sentinel."""
        iface = InterfaceIdentity.create("none", display_name="None", interface_type="other")
        net = NetworkIdentity(
            network_id="__DISCONNECTED__",
            connection_type="other",
            ssid=None,
            display_name="Disconnected",
            interface_id="iface:none",
        )
        return cls(
            timestamp=datetime.now(timezone.utc),
            interface=iface,
            network=net,
            is_connected=False,
        )
