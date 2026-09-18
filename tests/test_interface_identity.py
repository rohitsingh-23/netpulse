"""Tests for InterfaceIdentity model and interface classification."""

from netpulse.core.interface_identity import InterfaceIdentity
from netpulse.hardware.discovery import NetworkDiscovery


def test_interface_identity_creation() -> None:
    ident = InterfaceIdentity.create(
        bsd_name="en0",
        mac_address="AC:07:75:0D:50:19",
        display_name="Wi-Fi",
        interface_type="wifi",
        is_primary=True,
    )
    assert ident.interface_id == "iface:en0"
    assert ident.bsd_name == "en0"
    assert ident.mac_address == "ac:07:75:0d:50:19"
    assert ident.display_name == "Wi-Fi"
    assert ident.interface_type == "wifi"
    assert ident.is_primary is True


def test_interface_identity_virtual_fallback() -> None:
    ident = InterfaceIdentity.create(
        bsd_name="utun2",
        mac_address=None,
        display_name="VPN Tunnel",
        interface_type="vpn",
    )
    assert ident.interface_id == "iface:utun2"
    assert ident.bsd_name == "utun2"
    assert ident.mac_address is None
    assert ident.interface_type == "vpn"
    assert ident.is_primary is False


def test_classify_interfaces() -> None:
    disco = NetworkDiscovery()
    assert disco.classify_interface("en0", "IEEE80211") == "wifi"
    assert disco.classify_interface("en1", "Ethernet") == "ethernet"
    assert disco.classify_interface("bridge0", "Bridge") == "bridge"
    assert disco.classify_interface("utun3") == "vpn"
    assert disco.classify_interface("lo0") == "system"
    assert disco.classify_interface("awdl0") == "virtual"
    assert disco.classify_interface("llw0") == "virtual"
