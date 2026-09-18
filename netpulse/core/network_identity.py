"""Immutable network identity model.

Represents a logical network connection (e.g. Wi-Fi SSID, Ethernet link).
SSID is the primary logical grouping for Wi-Fi history — multiple BSSIDs (APs)
belonging to the same SSID are grouped under the same logical network identity.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Optional


@dataclass(frozen=True)
class NetworkIdentity:
    """Stable identity for a logical network connection.

    Attributes:
        network_id: Stable deterministic ID (e.g. "wifi:Rohit-Home" or "eth:en1").
        connection_type: "wifi", "ethernet", "vpn", "system", "other".
        ssid: Logical SSID for Wi-Fi (None if Ethernet/VPN or permission restricted).
        display_name: Formatted name for UI presentation.
        interface_id: ID of the interface currently or primarily associated.
        bssid_hash: Salted SHA-256 hash of AP BSSID for secondary access point tracking.
    """

    network_id: str
    connection_type: str
    ssid: Optional[str]
    display_name: str
    interface_id: str
    bssid_hash: Optional[str] = None

    @classmethod
    def create_wifi(
        cls,
        ssid: Optional[str],
        interface_id: str,
        bssid: Optional[str] = None,
        permission_restricted: bool = False,
    ) -> NetworkIdentity:
        """Create a Wi-Fi NetworkIdentity, grouping by SSID."""
        b_hash = None
        if bssid:
            # Salt with constant prefix to avoid raw BSSID leaking
            b_hash = hashlib.sha256(f"netpulse-bssid:{bssid.lower()}".encode()).hexdigest()[:16]

        if ssid and not permission_restricted:
            cleaned_ssid = ssid.strip()
            # Slug/hash for ID
            net_id = f"wifi:{cleaned_ssid.lower()}"
            display = cleaned_ssid
        else:
            # Fallback when location permission restricts SSID
            net_id = f"wifi-unpermitted:{interface_id}"
            display = "Wi-Fi Network"

        return cls(
            network_id=net_id,
            connection_type="wifi",
            ssid=ssid if not permission_restricted else None,
            display_name=display,
            interface_id=interface_id,
            bssid_hash=b_hash,
        )

    @classmethod
    def create_ethernet(
        cls,
        interface_id: str,
        display_name: str = "Ethernet",
    ) -> NetworkIdentity:
        """Create an Ethernet NetworkIdentity."""
        return cls(
            network_id=f"eth:{interface_id}",
            connection_type="ethernet",
            ssid=None,
            display_name=display_name,
            interface_id=interface_id,
            bssid_hash=None,
        )

    @classmethod
    def create_system_legacy(cls) -> NetworkIdentity:
        """Sentinel network for pre-Phase 6 legacy historical data."""
        return cls(
            network_id="__SYSTEM_LEGACY__",
            connection_type="system",
            ssid=None,
            display_name="System Total (Legacy)",
            interface_id="iface:all",
            bssid_hash=None,
        )
