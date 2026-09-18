"""Tests for NetworkIdentity model, SSID grouping, and permission fallback."""

from netpulse.core.network_identity import NetworkIdentity


def test_same_ssid_different_bssid_same_network_id() -> None:
    """Same SSID across different APs must share one logical network identity."""
    net1 = NetworkIdentity.create_wifi(
        ssid="Office-WiFi",
        interface_id="iface:en0",
        bssid="00:14:22:01:23:45",
    )
    net2 = NetworkIdentity.create_wifi(
        ssid="Office-WiFi",
        interface_id="iface:en0",
        bssid="00:14:22:99:88:77",
    )

    # Identical network_id grouping
    assert net1.network_id == net2.network_id
    assert net1.network_id == "wifi:office-wifi"
    assert net1.display_name == "Office-WiFi"
    assert net2.display_name == "Office-WiFi"

    # Distinct secondary access point hashes
    assert net1.bssid_hash is not None
    assert net2.bssid_hash is not None
    assert net1.bssid_hash != net2.bssid_hash
    # Salted hash prevents raw MAC leakage
    assert "00:14:22" not in net1.bssid_hash


def test_permission_restricted_fallback() -> None:
    """When Location permission restricts SSID, use privacy-safe fallback."""
    net = NetworkIdentity.create_wifi(
        ssid=None,
        interface_id="iface:en0",
        permission_restricted=True,
    )
    assert net.network_id == "wifi-unpermitted:iface:en0"
    assert net.display_name == "Wi-Fi Network"
    assert net.ssid is None
    assert net.connection_type == "wifi"


def test_ethernet_network_identity() -> None:
    net = NetworkIdentity.create_ethernet(
        interface_id="iface:en1",
        display_name="Thunderbolt Ethernet",
    )
    assert net.network_id == "eth:iface:en1"
    assert net.connection_type == "ethernet"
    assert net.ssid is None
    assert net.display_name == "Thunderbolt Ethernet"


def test_system_legacy_identity() -> None:
    legacy = NetworkIdentity.create_system_legacy()
    assert legacy.network_id == "__SYSTEM_LEGACY__"
    assert legacy.connection_type == "system"
    assert legacy.display_name == "System Total (Legacy)"
