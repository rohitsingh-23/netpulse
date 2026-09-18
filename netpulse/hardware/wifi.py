"""macOS CoreWLAN Wi-Fi inspection layer.

Bridges to CoreWLAN.framework via PyObjC/objc dynamic loading.
Maps Apple raw enums to clean Python domain values and handles macOS
Location Services permission degradation gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass
import platform
from typing import Optional

from netpulse.utils.log import get_logger

logger = get_logger("wifi")


# Domain enum mappings for Apple CoreWLAN types
PHY_MODE_MAP = {
    0: "None",
    1: "802.11a",
    2: "802.11b",
    3: "802.11g",
    4: "Wi-Fi 4 (802.11n)",
    5: "Wi-Fi 5 (802.11ac)",
    6: "Wi-Fi 6 (802.11ax)",
}

CHANNEL_BAND_MAP = {
    1: "2.4 GHz",
    2: "5 GHz",
    3: "6 GHz",
}

CHANNEL_WIDTH_MAP = {
    1: "20 MHz",
    2: "40 MHz",
    3: "80 MHz",
    4: "160 MHz",
}

SECURITY_MAP = {
    0: "Open",
    1: "WEP",
    2: "WPA Personal",
    3: "WPA Personal Mixed",
    4: "WPA2 Personal",
    5: "Personal",
    6: "WPA Enterprise",
    7: "WPA Enterprise Mixed",
    8: "WPA2 Enterprise",
    9: "Enterprise",
    10: "WPA3 Personal",
    11: "WPA3 Enterprise",
    12: "WPA3 Transition",
}


@dataclass(frozen=True)
class WiFiDetails:
    """Clean domain values for Wi-Fi interface and RF characteristics."""

    interface_name: str
    is_powered_on: bool
    is_connected: bool
    ssid: Optional[str]
    bssid: Optional[str]
    rssi: Optional[int]
    noise: Optional[int]
    channel_number: Optional[int]
    band: Optional[str]
    channel_width: Optional[str]
    phy_mode: Optional[str]
    transmit_rate_mbps: Optional[float]
    security: Optional[str]
    permission_restricted: bool = False


class WiFiInspector:
    """Inspects Wi-Fi state via Apple CoreWLAN framework."""

    def __init__(self) -> None:
        self._cw_client_cls = None
        self._init_framework()

    def _init_framework(self) -> None:
        """Dynamically load CoreWLAN framework."""
        if platform.system() != "Darwin":
            return
        try:
            import objc
            objc.loadBundle(
                "CoreWLAN",
                bundle_path="/System/Library/Frameworks/CoreWLAN.framework",
                module_globals=globals(),
            )
            self._cw_client_cls = objc.lookUpClass("CWWiFiClient")
        except Exception as e:
            logger.debug("CoreWLAN framework not available: %s", e)
            self._cw_client_cls = None

        try:
            import objc
            objc.loadBundle(
                "CoreLocation",
                bundle_path="/System/Library/Frameworks/CoreLocation.framework",
                module_globals=globals(),
            )
            self._cl_manager_cls = objc.lookUpClass("CLLocationManager")
            if self._cl_manager_cls:
                # Retain a reference to the manager so the delegate/auth process is not interrupted
                self._location_manager = self._cl_manager_cls.alloc().init()

                # Check status and prompt if not determined (0 = kCLAuthorizationStatusNotDetermined)
                status = self._cl_manager_cls.authorizationStatus()
                if status == 0:
                    logger.info("Location authorization not determined, requesting when-in-use authorization")
                    self._location_manager.requestWhenInUseAuthorization()
        except Exception as e:
            logger.debug("CoreLocation framework not available or failed to initialize: %s", e)
            self._cl_manager_cls = None
            self._location_manager = None

    def inspect_wifi(self, interface_name: Optional[str] = None) -> Optional[WiFiDetails]:
        """Query CoreWLAN for current Wi-Fi status and RF signal metrics."""
        if not self._cw_client_cls:
            return None

        try:
            client = self._cw_client_cls.sharedWiFiClient()
            if not client:
                return None

            if interface_name:
                iface = client.interfaceWithName_(interface_name)
            else:
                iface = client.interface()

            if not iface:
                return None

            bsd_name = iface.interfaceName() or "en0"
            power_on = bool(iface.powerOn())
            if not power_on:
                return WiFiDetails(
                    interface_name=bsd_name,
                    is_powered_on=False,
                    is_connected=False,
                    ssid=None,
                    bssid=None,
                    rssi=None,
                    noise=None,
                    channel_number=None,
                    band=None,
                    channel_width=None,
                    phy_mode=None,
                    transmit_rate_mbps=None,
                    security=None,
                    permission_restricted=False,
                )

            # Check if associated with an AP
            # In CoreWLAN, serviceActive() and rssiValue() indicate active link
            rssi = iface.rssiValue()
            noise = iface.noiseMeasurement()
            # RSSI == 0 on some interfaces indicates not connected
            is_connected = bool(iface.serviceActive() and rssi != 0)

            # SSID and BSSID may be redacted (None) if Location permission is missing
            raw_ssid = iface.ssid()
            raw_bssid = iface.bssid()

            permission_restricted = False
            if is_connected and raw_ssid is None:
                permission_restricted = True

            # Channel info
            ch = iface.wlanChannel()
            ch_num = None
            band_str = None
            width_str = None
            if ch:
                ch_num = ch.channelNumber()
                band_str = CHANNEL_BAND_MAP.get(ch.channelBand(), f"Band {ch.channelBand()}")
                width_str = CHANNEL_WIDTH_MAP.get(ch.channelWidth(), f"Width {ch.channelWidth()}")

            # PHY mode (use activePHYMode or phyMode)
            raw_phy = getattr(iface, "activePHYMode", None)
            phy_val = raw_phy() if callable(raw_phy) else getattr(iface, "phyMode", None)
            if callable(phy_val):
                phy_val = phy_val()
            phy_str = PHY_MODE_MAP.get(phy_val, "Unknown" if phy_val else None)

            # Transmit rate
            tx_rate = None
            try:
                raw_tx = iface.transmitRate()
                if raw_tx and raw_tx > 0:
                    tx_rate = float(raw_tx)
            except Exception:
                pass

            # Security
            raw_sec = iface.security()
            sec_str = SECURITY_MAP.get(raw_sec, "Unknown" if raw_sec else None)

            return WiFiDetails(
                interface_name=bsd_name,
                is_powered_on=power_on,
                is_connected=is_connected,
                ssid=raw_ssid,
                bssid=raw_bssid,
                rssi=rssi if is_connected else None,
                noise=noise if is_connected else None,
                channel_number=ch_num,
                band=band_str,
                channel_width=width_str,
                phy_mode=phy_str,
                transmit_rate_mbps=tx_rate,
                security=sec_str,
                permission_restricted=permission_restricted,
            )
        except Exception as e:
            logger.debug("Exception querying CoreWLAN: %s", e)
            return None
