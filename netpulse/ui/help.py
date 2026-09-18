"""Help and documentation page for the NetPulse Dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from netpulse.ui.widgets import CardContainer
from netpulse.utils.constants import (
    APP_NAME,
    APP_VERSION,
    GITHUB_ISSUES_URL,
    GITHUB_REPOSITORY_URL,
    SUPPORT_EMAIL,
)

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager


def _create_section_card(
    title_text: str,
    items: list[tuple[str, str]],
) -> CardContainer:
    """Create a styled documentation card with items."""
    card = CardContainer()
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(22, 18, 22, 18)
    card_layout.setSpacing(14)

    # Section header
    hdr = QLabel(title_text.upper())
    font_hdr = QFont()
    font_hdr.setPointSize(11)
    font_hdr.setWeight(QFont.Weight.Bold)
    hdr.setFont(font_hdr)
    hdr.setStyleSheet("color: gray; letter-spacing: 0.5px;")
    card_layout.addWidget(hdr)

    for heading, desc in items:
        item_layout = QVBoxLayout()
        item_layout.setSpacing(3)

        lbl_head = QLabel(heading)
        font_sub = QFont()
        font_sub.setPointSize(13)
        font_sub.setWeight(QFont.Weight.DemiBold)
        lbl_head.setFont(font_sub)

        lbl_desc = QLabel(desc)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: palette(text); line-height: 1.4;")
        lbl_desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        item_layout.addWidget(lbl_head)
        item_layout.addWidget(lbl_desc)
        card_layout.addLayout(item_layout)

    return card


class HelpPage(QWidget):
    """Native macOS-style Help and documentation view in the NetPulse Dashboard."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header card
        header_card = CardContainer()
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(4)

        title = QLabel("Help")
        font_title = QFont()
        font_title.setPointSize(20)
        font_title.setWeight(QFont.Weight.Bold)
        title.setFont(font_title)

        subtitle = QLabel("Learn how NetPulse works and get help with common questions.")
        subtitle.setStyleSheet("color: gray; font-size: 13px;")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_card)

        # 1. Getting Started
        layout.addWidget(
            _create_section_card(
                "1. Getting Started",
                [
                    (
                        "What NetPulse Does",
                        "NetPulse is a lightweight, privacy-focused network monitor engineered specifically for macOS. "
                        "It runs in your menu bar and delivers real-time download and upload bandwidth speeds, Wi-Fi link diagnostics, "
                        "historical analytics, and customizable notifications.",
                    ),
                    (
                        "Understanding the Menu Bar",
                        "The menu bar displays your active transfer rates alongside an animated lion mascot. "
                        "Click the status item to open a menu with quick toggles for display modes (Both, Download Only, Upload Only, Compact, Smart), "
                        "speed units, refresh intervals, session statistics, and shortcuts to the Dashboard.",
                    ),
                    (
                        "Understanding the Dashboard",
                        "The Dashboard provides in-depth metrics: Overview (live speeds, peak rates, and historical summaries), "
                        "Live (real-time graphs), Speed Test (bandwidth and latency verification), Networks (Wi-Fi RF telemetry and interface info), "
                        "Session (traffic since launch), and Settings.",
                    ),
                    (
                        "How to Run a Speed Test",
                        "Navigate to the Speed Test tab in the sidebar and click 'Start Test'. NetPulse measures download throughput, upload throughput, "
                        "round-trip ping, and jitter against Cloudflare Edge servers.",
                    ),
                ],
            )
        )

        # 2. Network Monitoring
        layout.addWidget(
            _create_section_card(
                "2. Network Monitoring",
                [
                    (
                        "Download vs Upload",
                        "Download traffic (indicated by ↓) represents incoming data received by your Mac. "
                        "Upload traffic (indicated by ↑) represents outgoing data transmitted by your Mac.",
                    ),
                    (
                        "Speed Units",
                        "Speeds can be formatted in Byte-based units (B/s, KB/s, MB/s, GB/s) using binary multiples (1024 bytes = 1 KB), "
                        "or bit-based units (kbps, Mbps, Gbps) using decimal multiples. 'Auto' selects the optimal unit tier based on the higher traffic stream.",
                    ),
                    (
                        "Network & Interface Detection",
                        "NetPulse identifies the active primary network route. Traffic accounting tracks the active BSD interface (such as en0 for Wi-Fi) "
                        "and attributes usage specifically to that network identity.",
                    ),
                    (
                        "Wi-Fi Information",
                        "On macOS, Wi-Fi telemetry captures signal strength (RSSI), RF noise floor, channel frequency, channel width, "
                        "PHY generation (Wi-Fi 4/5/6), transmit link rate, and security protocol.",
                    ),
                    (
                        "VPN & Virtual Interfaces",
                        "Virtual adapters, tunnels (utun*), and bridge interfaces are detected and handled to prevent double-counting traffic. "
                        "NetPulse isolates the underlying physical route carrying the payload.",
                    ),
                ],
            )
        )

        # 3. Speed Test
        layout.addWidget(
            _create_section_card(
                "3. Speed Test",
                [
                    (
                        "What the Speed Test Measures",
                        "The built-in Speed Test verifies your internet connection against nearby edge endpoints. "
                        "It measures latency, jitter, download throughput, and upload throughput.",
                    ),
                    (
                        "Download & Upload Speed",
                        "Throughput calculations reflect payload transfer speeds achieved over concurrent HTTP streams. "
                        "Running a speed test actively utilizes network bandwidth for the duration of the test.",
                    ),
                    (
                        "Ping & Jitter",
                        "Ping measures the round-trip latency in milliseconds. Jitter measures the statistical variance in round-trip latency over time, "
                        "indicating connection stability for real-time video calls and gaming.",
                    ),
                    (
                        "Packet Loss Availability",
                        "Packet Loss may show as 'Unavailable'. Precise packet loss calculation requires low-level raw socket ICMP access, "
                        "which macOS restricts for standard user-space applications without elevated root privileges.",
                    ),
                    (
                        "Accounting Isolation",
                        "Speed-test traffic is completely isolated from NetPulse historical accounting. "
                        "Test payloads do not pollute your session counters, hourly buckets, or SQLite analytics tables.",
                    ),
                ],
            )
        )

        # 4. Notifications
        layout.addWidget(
            _create_section_card(
                "4. Notifications",
                [
                    (
                        "Notification Events",
                        "NetPulse supports native macOS alerts for: Network Connected, Network Disconnected, Network Changed, "
                        "Connection Restored, Weak Wi-Fi Signal, High Download Speed, High Upload Speed, and High Data Usage.",
                    ),
                    (
                        "Anti-Spam & Hysteresis",
                        "Every alert type implements rate-limiting cooldowns and dual-boundary hysteresis (e.g. triggering weak signal alerts at ≤ -75 dBm "
                        "and requiring recovery to ≥ -70 dBm before re-arming) to prevent alert spam.",
                    ),
                    (
                        "Configuration",
                        "All notifications can be enabled, disabled, or tuned with custom thresholds in the Settings page.",
                    ),
                ],
            )
        )

        # 5. Privacy & Data
        layout.addWidget(
            _create_section_card(
                "5. Privacy & Data",
                [
                    (
                        "Local Storage Only",
                        "Network monitoring data and historical statistics are stored strictly on your Mac in a local SQLite database "
                        "(~/Library/Application Support/NetPulse/netpulse.db). No external accounts, servers, or cloud synchronization exist.",
                    ),
                    (
                        "Zero Telemetry",
                        "NetPulse does not include analytics, telemetry, tracking SDKs, or background usage reporting.",
                    ),
                    (
                        "macOS Location Permission",
                        "Apple requires Location Services permission to read the current Wi-Fi network name (SSID). "
                        "If Location permission is not granted, NetPulse displays 'Wi-Fi Network' while maintaining all speed monitoring, RF physics, and interface intelligence.",
                    ),
                    (
                        "Hardware MAC & BSSID Protection",
                        "Raw Access Point BSSIDs are never displayed or stored in plaintext. They are salted and cryptographically hashed "
                        "to protect privacy while allowing roaming detection.",
                    ),
                    (
                        "Speed Test Data Flow",
                        "The Speed Test is the only feature that transmits external data, which occurs exclusively when you explicitly click 'Start Test'.",
                    ),
                ],
            )
        )

        # 6. Data & Storage
        layout.addWidget(
            _create_section_card(
                "6. Data & Storage",
                [
                    (
                        "Historical Aggregation",
                        "Samples are aggregated in memory and committed to SQLite in hourly, daily, and monthly rollups.",
                    ),
                    (
                        "Reset Statistics & History",
                        "Truncates all hourly, daily, monthly, and interface records in the local database and compacts storage. "
                        "Your application preferences, display modes, and notification settings are preserved.",
                    ),
                    (
                        "Reset All NetPulse Data",
                        "Performs a complete factory reset. Truncates all database records, removes cached network profiles, "
                        "and resets all user preferences back to default values.",
                    ),
                ],
            )
        )

        # 7. Troubleshooting
        layout.addWidget(
            _create_section_card(
                "7. Troubleshooting",
                [
                    (
                        "Speed Displays Zero (0 B/s)",
                        "Check that you are actively transmitting traffic on the primary network interface. "
                        "If using a third-party VPN, verify that the active route is not filtering packet inspection.",
                    ),
                    (
                        "Wi-Fi Network Name Unavailable",
                        "Ensure macOS Location Services is enabled in System Settings > Privacy & Security > Location Services for NetPulse. "
                        "Location permission is required by macOS to read Wi-Fi SSIDs.",
                    ),
                    (
                        "Notifications Do Not Appear",
                        "Verify that NetPulse notifications are permitted in System Settings > Notifications > NetPulse, "
                        "and check that macOS Focus mode / Do Not Disturb is not suppressing banner alerts.",
                    ),
                    (
                        "Speed Test Fails",
                        "Ensure your Mac has an active internet connection. If you are behind a corporate proxy or firewall that blocks HTTPS streaming, "
                        "connection timeouts may occur.",
                    ),
                    (
                        "Dashboard Does Not Open",
                        "Click the menu bar icon and select 'Open Dashboard'. NetPulse is a menu-bar accessory application without a permanent Dock icon.",
                    ),
                    (
                        "App Does Not Appear in Menu Bar",
                        "If your menu bar has many icons, macOS may hide status items on smaller screens or displays with camera notches. "
                        "Close other menu-bar utilities or adjust screen resolution.",
                    ),
                ],
            )
        )

        # 8. About NetPulse
        about_card = CardContainer()
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(22, 18, 22, 18)
        about_layout.setSpacing(8)

        lbl_about = QLabel("8. ABOUT NETPULSE")
        font_about = QFont()
        font_about.setPointSize(11)
        font_about.setWeight(QFont.Weight.Bold)
        lbl_about.setFont(font_about)
        lbl_about.setStyleSheet("color: gray; letter-spacing: 0.5px;")
        about_layout.addWidget(lbl_about)

        app_name_lbl = QLabel(f"{APP_NAME} v{APP_VERSION}")
        font_name = QFont()
        font_name.setPointSize(14)
        font_name.setWeight(QFont.Weight.Bold)
        app_name_lbl.setFont(font_name)
        about_layout.addWidget(app_name_lbl)

        desc_lbl = QLabel(
            "Privacy-first macOS network monitor.\n"
            "Engineered for speed, clarity, and zero external telemetry."
        )
        desc_lbl.setStyleSheet("color: palette(text); line-height: 1.4;")
        about_layout.addWidget(desc_lbl)

        # Support contact
        support_lbl = QLabel(
            f'Need help?<br>'
            f'<a href="mailto:{SUPPORT_EMAIL}" style="color: palette(highlight); text-decoration: none;">{SUPPORT_EMAIL}</a>'
        )
        support_lbl.setOpenExternalLinks(True)
        support_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        support_lbl.setStyleSheet("line-height: 1.4; margin-top: 4px;")
        about_layout.addWidget(support_lbl)

        # Repository and Bug Report links
        links_lbl = QLabel(
            f'<div style="margin-top: 6px; line-height: 1.6;">'
            f'<a href="{GITHUB_REPOSITORY_URL}" style="color: palette(highlight); text-decoration: none;">Source Code</a>'
            f' &nbsp;•&nbsp; '
            f'<a href="{GITHUB_ISSUES_URL}" style="color: palette(highlight); text-decoration: none;">Report a Bug</a>'
            f'</div>'
        )
        links_lbl.setOpenExternalLinks(True)
        links_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        about_layout.addWidget(links_lbl)

        layout.addWidget(about_card)
