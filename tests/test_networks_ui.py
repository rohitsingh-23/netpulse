"""Tests for NetworksPage UI component and state updates."""

from datetime import datetime, timezone
import pytest
from PySide6.QtWidgets import QApplication

from netpulse.config.preferences import PreferencesManager
from netpulse.core.interface_identity import InterfaceIdentity
from netpulse.core.network_context import NetworkContext
from netpulse.core.network_identity import NetworkIdentity
from netpulse.core.network_sample import NetworkSample
from netpulse.storage.database import Database
from netpulse.ui.networks import NetworksPage


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def networks_page(qapp: QApplication) -> NetworksPage:
    prefs = PreferencesManager()
    db = Database(":memory:")
    return NetworksPage(prefs_manager=prefs, database=db)


def test_networks_page_initial_render(networks_page: NetworksPage) -> None:
    assert networks_page is not None
    assert networks_page._lbl_net_title.text() == "Checking Connection..."
    assert networks_page._graph is not None


def test_networks_page_update_context_connected(networks_page: NetworksPage) -> None:
    iface = InterfaceIdentity.create("en0", "ac:07:75:0d:50:19", "Wi-Fi", "wifi", is_primary=True)
    net = NetworkIdentity.create_wifi("Rohit-Home", iface.interface_id, "aa:bb:cc:dd:ee:ff")
    ctx = NetworkContext(
        timestamp=datetime.now(timezone.utc),
        interface=iface,
        network=net,
        is_connected=True,
        ipv4_address="192.168.31.196",
        rssi=-57,
        noise=-94,
        channel=44,
        band="5 GHz",
        channel_width="80 MHz",
        phy_mode="Wi-Fi 6 (802.11ax)",
        transmit_rate_mbps=648.0,
        security="WPA2 Personal",
        permission_restricted=False,
    )

    networks_page.update_context(ctx)

    assert networks_page._lbl_net_title.text() == "Rohit-Home"
    assert "en0" in networks_page._lbl_iface_badge.text()
    assert "-57 dBm" in networks_page._lbl_rssi.text()
    assert "44" in networks_page._lbl_channel.text()
    assert "5 GHz" in networks_page._lbl_band.text()
    assert "80 MHz" in networks_page._lbl_width.text()
    assert "Wi-Fi 6" in networks_page._lbl_phy.text()
    assert "648 Mbps" in networks_page._lbl_rate.text()
    assert networks_page._lbl_ip.text() == "192.168.31.196"
    assert networks_page._perm_banner.isVisible() is False


def test_networks_page_update_context_permission_restricted(networks_page: NetworksPage) -> None:
    iface = InterfaceIdentity.create("en0", "ac:07:75:0d:50:19", "Wi-Fi", "wifi", is_primary=True)
    net = NetworkIdentity.create_wifi(None, iface.interface_id, permission_restricted=True)
    ctx = NetworkContext(
        timestamp=datetime.now(timezone.utc),
        interface=iface,
        network=net,
        is_connected=True,
        rssi=-62,
        phy_mode="Wi-Fi 6 (802.11ax)",
        permission_restricted=True,
    )

    networks_page.update_context(ctx)

    assert networks_page._lbl_net_title.text() == "Wi-Fi Network"
    assert not networks_page._perm_banner.isHidden()


def test_networks_page_on_sample(networks_page: NetworksPage) -> None:
    sample = NetworkSample(
        timestamp=datetime.now(timezone.utc),
        download_bps=1048576.0,
        upload_bps=524288.0,
        total_download_bytes=1000,
        total_upload_bytes=500,
        interface="en0",
    )
    networks_page.on_sample(sample)
    text = networks_page._lbl_live_speed.text()
    assert "↓" in text and "↑" in text
