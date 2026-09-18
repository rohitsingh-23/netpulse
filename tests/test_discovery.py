"""Tests for interface discovery and classification."""

from unittest.mock import patch

from netpulse.hardware.discovery import NetworkDiscovery


def test_discover_interfaces_structure() -> None:
    disco = NetworkDiscovery()
    ifaces = disco.discover_interfaces()
    assert isinstance(ifaces, list)
    # On host Mac, at least loopback and en0 exist
    bsd_names = [i.bsd_name for i in ifaces]
    assert "lo0" in bsd_names


def test_primary_interface_resolution() -> None:
    disco = NetworkDiscovery()
    primary = disco.get_primary_interface_bsd()
    # If network is connected on host, primary should be a non-empty string like 'en0'
    if primary:
        assert isinstance(primary, str)
        assert primary != "lo0"


def test_get_interface_ip_info() -> None:
    disco = NetworkDiscovery()
    ipv4, ipv6, router = disco.get_interface_ip_info("lo0")
    # Loopback IP
    # In discovery.py we filter out 127.* for public IP
    assert router is None
