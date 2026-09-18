"""Tests for CoreWLAN Wi-Fi metadata mapping and permission degradation."""

from unittest.mock import MagicMock

from netpulse.hardware.wifi import (
    CHANNEL_BAND_MAP,
    CHANNEL_WIDTH_MAP,
    PHY_MODE_MAP,
    SECURITY_MAP,
    WiFiInspector,
)


def test_enum_mappings() -> None:
    assert PHY_MODE_MAP[6] == "Wi-Fi 6 (802.11ax)"
    assert PHY_MODE_MAP[5] == "Wi-Fi 5 (802.11ac)"
    assert PHY_MODE_MAP[4] == "Wi-Fi 4 (802.11n)"
    assert CHANNEL_BAND_MAP[1] == "2.4 GHz"
    assert CHANNEL_BAND_MAP[2] == "5 GHz"
    assert CHANNEL_BAND_MAP[3] == "6 GHz"
    assert CHANNEL_WIDTH_MAP[3] == "80 MHz"
    assert SECURITY_MAP[4] == "WPA2 Personal"
    assert SECURITY_MAP[10] == "WPA3 Personal"


def test_inspect_wifi_mocked_connected() -> None:
    inspector = WiFiInspector()

    # Create mock CoreWLAN interface
    mock_channel = MagicMock()
    mock_channel.channelNumber.return_value = 44
    mock_channel.channelBand.return_value = 2  # 5 GHz
    mock_channel.channelWidth.return_value = 3  # 80 MHz

    mock_iface = MagicMock()
    mock_iface.interfaceName.return_value = "en0"
    mock_iface.powerOn.return_value = True
    mock_iface.serviceActive.return_value = True
    mock_iface.rssiValue.return_value = -58
    mock_iface.noiseMeasurement.return_value = -92
    mock_iface.ssid.return_value = "MyHome"
    mock_iface.bssid.return_value = "aa:bb:cc:dd:ee:ff"
    mock_iface.wlanChannel.return_value = mock_channel
    mock_iface.activePHYMode.return_value = 6
    mock_iface.transmitRate.return_value = 648.0
    mock_iface.security.return_value = 4

    mock_client = MagicMock()
    mock_client.interface.return_value = mock_iface
    mock_client.interfaceWithName_.return_value = mock_iface

    inspector._cw_client_cls = MagicMock()
    inspector._cw_client_cls.sharedWiFiClient.return_value = mock_client

    details = inspector.inspect_wifi("en0")
    assert details is not None
    assert details.interface_name == "en0"
    assert details.is_powered_on is True
    assert details.is_connected is True
    assert details.ssid == "MyHome"
    assert details.rssi == -58
    assert details.noise == -92
    assert details.channel_number == 44
    assert details.band == "5 GHz"
    assert details.channel_width == "80 MHz"
    assert details.phy_mode == "Wi-Fi 6 (802.11ax)"
    assert details.transmit_rate_mbps == 648.0
    assert details.security == "WPA2 Personal"
    assert details.permission_restricted is False


def test_inspect_wifi_permission_denied_graceful() -> None:
    inspector = WiFiInspector()

    mock_iface = MagicMock()
    mock_iface.interfaceName.return_value = "en0"
    mock_iface.powerOn.return_value = True
    mock_iface.serviceActive.return_value = True
    mock_iface.rssiValue.return_value = -60
    mock_iface.noiseMeasurement.return_value = -90
    mock_iface.ssid.return_value = None  # Redacted by macOS location privacy
    mock_iface.bssid.return_value = None
    mock_iface.wlanChannel.return_value = None
    mock_iface.activePHYMode.return_value = 6
    mock_iface.transmitRate.return_value = 300.0
    mock_iface.security.return_value = 4

    mock_client = MagicMock()
    mock_client.interface.return_value = mock_iface
    mock_client.interfaceWithName_.return_value = mock_iface
    inspector._cw_client_cls = MagicMock()
    inspector._cw_client_cls.sharedWiFiClient.return_value = mock_client

    details = inspector.inspect_wifi("en0")
    assert details is not None
    assert details.is_connected is True
    assert details.ssid is None
    assert details.permission_restricted is True
    assert details.rssi == -60
    assert details.phy_mode == "Wi-Fi 6 (802.11ax)"
