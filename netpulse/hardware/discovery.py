"""System network interface discovery using macOS SystemConfiguration & psutil.

Discovers BSD interfaces, resolves hardware MAC addresses, maps human-readable
display names, classifies adapter types, and identifies the active primary interface.
"""

from __future__ import annotations

import ctypes
import os
import platform
import socket
from typing import Dict, List, Optional, Tuple

import psutil

from netpulse.core.interface_identity import InterfaceIdentity
from netpulse.utils.log import get_logger

logger = get_logger("discovery")


class NetworkDiscovery:
    """Discovers and inspects network interfaces on macOS."""

    def __init__(self) -> None:
        self._sc = None
        self._cf = None
        self._init_frameworks()

    def _init_frameworks(self) -> None:
        """Initialize CoreFoundation and SystemConfiguration dynamically."""
        if platform.system() != "Darwin":
            return
        try:
            self._cf = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
            )
            self._sc = ctypes.cdll.LoadLibrary(
                "/System/Library/Frameworks/SystemConfiguration.framework/SystemConfiguration"
            )

            # Define CF function signatures
            self._cf.CFArrayGetCount.restype = ctypes.c_long
            self._cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
            self._cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
            self._cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
            self._cf.CFStringGetCString.restype = ctypes.c_bool
            self._cf.CFStringGetCString.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_long,
                ctypes.c_uint,
            ]
            self._cf.CFRelease.restype = None
            self._cf.CFRelease.argtypes = [ctypes.c_void_p]

            # Define SC function signatures
            self._sc.SCNetworkInterfaceCopyAll.restype = ctypes.c_void_p
            self._sc.SCNetworkInterfaceGetBSDName.restype = ctypes.c_void_p
            self._sc.SCNetworkInterfaceGetBSDName.argtypes = [ctypes.c_void_p]
            self._sc.SCNetworkInterfaceGetLocalizedDisplayName.restype = ctypes.c_void_p
            self._sc.SCNetworkInterfaceGetLocalizedDisplayName.argtypes = [ctypes.c_void_p]
            self._sc.SCNetworkInterfaceGetInterfaceType.restype = ctypes.c_void_p
            self._sc.SCNetworkInterfaceGetInterfaceType.argtypes = [ctypes.c_void_p]
            self._sc.SCNetworkInterfaceGetHardwareAddressString.restype = ctypes.c_void_p
            self._sc.SCNetworkInterfaceGetHardwareAddressString.argtypes = [ctypes.c_void_p]
        except Exception as e:
            logger.debug("Failed to load SystemConfiguration frameworks: %s", e)
            self._sc = None
            self._cf = None

    def _cfstr_to_py(self, cfstr: ctypes.c_void_p) -> Optional[str]:
        """Convert a CFStringRef to a Python string."""
        if not cfstr or not self._cf:
            return None
        buf = ctypes.create_string_buffer(256)
        # 0x08000100 is kCFStringEncodingUTF8
        if self._cf.CFStringGetCString(cfstr, buf, 256, 0x08000100):
            return buf.value.decode("utf-8")
        return None

    def _query_sc_hardware_interfaces(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Query SystemConfiguration for BSD name -> {display_name, type, mac}."""
        result: Dict[str, Dict[str, Optional[str]]] = {}
        if not self._sc or not self._cf:
            return result

        arr = None
        try:
            arr = self._sc.SCNetworkInterfaceCopyAll()
            if not arr:
                return result
            count = self._cf.CFArrayGetCount(arr)
            for i in range(count):
                iface = self._cf.CFArrayGetValueAtIndex(arr, i)
                if not iface:
                    continue
                bsd = self._cfstr_to_py(self._sc.SCNetworkInterfaceGetBSDName(iface))
                if not bsd:
                    continue
                display = self._cfstr_to_py(
                    self._sc.SCNetworkInterfaceGetLocalizedDisplayName(iface)
                )
                itype = self._cfstr_to_py(self._sc.SCNetworkInterfaceGetInterfaceType(iface))
                mac = self._cfstr_to_py(
                    self._sc.SCNetworkInterfaceGetHardwareAddressString(iface)
                )
                result[bsd.lower()] = {
                    "display_name": display,
                    "interface_type": itype,
                    "mac": mac,
                }
        except Exception as e:
            logger.debug("Error querying SCNetworkInterfaceCopyAll: %s", e)
        finally:
            if arr and self._cf:
                self._cf.CFRelease(arr)
        return result

    @staticmethod
    def classify_interface(bsd_name: str, sc_type: Optional[str] = None) -> str:
        """Classify interface into standard type category.

        Categories:
            wifi, ethernet, vpn, bridge, virtual, system, other
        """
        bsd = bsd_name.lower().strip()
        if sc_type:
            sc_t = sc_type.lower()
            if "ieee80211" in sc_t or "wifi" in sc_t:
                return "wifi"
            if "ethernet" in sc_t:
                return "ethernet"
            if "bridge" in sc_t:
                return "bridge"
            if "ppp" in sc_t or "ipsec" in sc_t:
                return "vpn"

        # BSD prefix heuristics
        if bsd.startswith("lo"):
            return "system"
        if bsd.startswith(("awdl", "llw")):
            return "virtual"
        if bsd.startswith("bridge"):
            return "bridge"
        if bsd.startswith(("utun", "ipsec", "ppp", "tap", "tun", "wg")):
            return "vpn"
        if bsd.startswith("anpi"):
            return "system"
        if bsd.startswith("en"):
            # en0 is almost universally Wi-Fi on modern Macs, but could be ethernet
            return "ethernet"
        return "other"

    def get_primary_interface_bsd(self) -> Optional[str]:
        """Resolve the active primary default route interface name on macOS."""
        # 1. Try SCDynamicStore lookup if possible
        if platform.system() == "Darwin":
            try:
                import objc
                objc.loadBundle(
                    "SystemConfiguration",
                    bundle_path="/System/Library/Frameworks/SystemConfiguration.framework",
                    module_globals=globals(),
                )
                # Query dynamic store dictionary via scutil if available or fallback
            except Exception:
                pass

        # 2. Heuristic default route via socket probe (zero internet traffic sent)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 53))
            local_ip = s.getsockname()[0]
            s.close()
            # Find which interface owns this IP
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.address == local_ip:
                        return iface
        except Exception:
            pass

        # 3. Fallback: first active up interface that has an IP and is not loopback
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for iface, s in stats.items():
            if s.isup and iface not in ("lo0", "awdl0", "llw0") and not iface.startswith("utun"):
                if iface in addrs:
                    for a in addrs[iface]:
                        if a.family == socket.AF_INET and not a.address.startswith("127."):
                            return iface
        return None

    def discover_interfaces(self) -> List[InterfaceIdentity]:
        """Discover all network adapters and return structured InterfaceIdentity models."""
        hw_info = self._query_sc_hardware_interfaces()
        addrs_map = psutil.net_if_addrs()
        stats_map = psutil.net_if_stats()
        primary_bsd = self.get_primary_interface_bsd()

        all_bsd_names = set(hw_info.keys()) | set(addrs_map.keys()) | set(stats_map.keys())
        interfaces: List[InterfaceIdentity] = []

        for bsd in sorted(all_bsd_names):
            bsd_lower = bsd.lower()
            hw = hw_info.get(bsd_lower, {})
            display_name = hw.get("display_name")
            sc_type = hw.get("interface_type")
            mac = hw.get("mac")

            # Extract MAC from psutil if missing from SC
            if not mac and bsd in addrs_map:
                for a in addrs_map[bsd]:
                    # AF_LINK is 18 on macOS
                    if getattr(a.family, "name", "") in ("AF_LINK", "AF_PACKET") or a.family == 18:
                        if a.address and ":" in a.address:
                            mac = a.address
                            break

            classification = self.classify_interface(bsd_lower, sc_type)

            # If SC provided a name like 'Wi-Fi' ensure type matches
            if display_name and "wi-fi" in display_name.lower():
                classification = "wifi"

            if not display_name:
                if classification == "wifi":
                    display_name = f"Wi-Fi ({bsd})"
                elif classification == "ethernet":
                    display_name = f"Ethernet ({bsd})"
                elif classification == "vpn":
                    display_name = f"VPN ({bsd})"
                elif classification == "bridge":
                    display_name = f"Bridge ({bsd})"
                else:
                    display_name = bsd

            is_primary = (bsd_lower == primary_bsd.lower()) if primary_bsd else False

            ident = InterfaceIdentity.create(
                bsd_name=bsd,
                mac_address=mac,
                display_name=display_name,
                interface_type=classification,
                is_primary=is_primary,
            )
            interfaces.append(ident)

        return interfaces

    def get_interface_ip_info(
        self, bsd_name: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Retrieve (ipv4, ipv6, router_ip) for a specific BSD interface."""
        ipv4 = None
        ipv6 = None
        router_ip = None

        addrs = psutil.net_if_addrs().get(bsd_name, [])
        for a in addrs:
            fam = getattr(a.family, "name", str(a.family))
            if fam == "AF_INET" or a.family == socket.AF_INET:
                if not a.address.startswith("127."):
                    ipv4 = a.address
            elif fam == "AF_INET6" or a.family == socket.AF_INET6:
                # Prefer globally routable, skip link-local fe80
                if not a.address.startswith("fe80"):
                    ipv6 = a.address
                elif not ipv6:
                    ipv6 = a.address.split("%")[0]

        return ipv4, ipv6, router_ip
