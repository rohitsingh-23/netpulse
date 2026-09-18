"""Immutable interface identity model.

Represents a network interface adapter (e.g. en0, en1, utun2).
Identity is rooted in the hardware BSD name and MAC address where available.
Display name is kept as an attribute, not the primary identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InterfaceIdentity:
    """Stable identity and attributes of a network adapter.

    Attributes:
        interface_id: Internal stable identifier (e.g. "iface:en0").
        bsd_name: System BSD device name (e.g. "en0", "en1").
        mac_address: Hardware MAC address string (None for virtual/tunnel adapters).
        display_name: Human-friendly name (e.g. "Wi-Fi", "Thunderbolt Ethernet").
        interface_type: Classification: "wifi", "ethernet", "bridge", "vpn", "virtual", "system", "other".
        is_primary: Whether this interface currently holds the default internet route.
    """

    interface_id: str
    bsd_name: str
    mac_address: Optional[str]
    display_name: str
    interface_type: str
    is_primary: bool = False

    @classmethod
    def create(
        cls,
        bsd_name: str,
        mac_address: Optional[str] = None,
        display_name: Optional[str] = None,
        interface_type: str = "other",
        is_primary: bool = False,
    ) -> InterfaceIdentity:
        """Convenience constructor generating a normalized interface_id."""
        normalized_bsd = bsd_name.strip().lower()
        interface_id = f"iface:{normalized_bsd}"
        display = display_name if display_name else bsd_name
        return cls(
            interface_id=interface_id,
            bsd_name=normalized_bsd,
            mac_address=mac_address.lower().strip() if mac_address else None,
            display_name=display,
            interface_type=interface_type,
            is_primary=is_primary,
        )
