"""Menu-bar title formatting.

Pure functions that convert speed values + display/unit configuration
into menu-bar title strings. Fully testable without macOS or rumps.

Compact mode design:
    Uses a shared unit (determined by the larger speed in auto mode)
    with abbreviated suffixes (K, M, G) to minimise menu-bar width.
    Example: ``↓12.4M ↑1.2M``

Smart mode design:
    Shows only directions with significant traffic (≥ 1 KB/s).
    If both directions are idle, shows both at the current level.
    Threshold: 1024 bytes/sec (1 KB/s).
"""

from __future__ import annotations

from netpulse.config.models import DisplayMode, UnitMode
from netpulse.utils.formatters import format_speed

# Smart-mode threshold: below this, traffic is considered idle
_SMART_THRESHOLD_BPS = 1024.0  # 1 KB/s


def _unit_arg(unit_mode: UnitMode) -> str:
    """Convert UnitMode enum to ``format_speed`` unit parameter."""
    if unit_mode == UnitMode.AUTO:
        return "auto"
    return unit_mode.value


def _speed(bps: float, unit_mode: UnitMode) -> str:
    """Format speed with the configured unit."""
    return format_speed(bps, unit=_unit_arg(unit_mode))


def _format_dual_speed(
    download_bps: float,
    upload_bps: float,
    unit_mode: UnitMode,
) -> str:
    """Format download and upload speeds with the unit displayed only once after upload."""
    if download_bps < 0:
        download_bps = 0.0
    if upload_bps < 0:
        upload_bps = 0.0

    max_bps = max(download_bps, upload_bps)

    if unit_mode == UnitMode.AUTO:
        if max_bps < 1024.0:
            divisor = 1.0
            unit_str = "B/s"
            is_bytes = True
        elif max_bps < 1024.0 ** 2:
            divisor = 1024.0
            unit_str = "KB/s"
            is_bytes = False
        elif max_bps < 1024.0 ** 3:
            divisor = 1024.0 ** 2
            unit_str = "MB/s"
            is_bytes = False
        elif max_bps < 1024.0 ** 4:
            divisor = 1024.0 ** 3
            unit_str = "GB/s"
            is_bytes = False
        else:
            divisor = 1024.0 ** 4
            unit_str = "TB/s"
            is_bytes = False
    else:
        unit_map = {
            "B": (1.0, "B/s", True),
            "KB": (1024.0, "KB/s", False),
            "MB": (1024.0 ** 2, "MB/s", False),
            "GB": (1024.0 ** 3, "GB/s", False),
            "TB": (1024.0 ** 4, "TB/s", False),
            "kbps": (1000.0 / 8.0, "kbps", False),
            "Mbps": (1000.0 ** 2 / 8.0, "Mbps", False),
            "Gbps": (1000.0 ** 3 / 8.0, "Gbps", False),
        }
        val = unit_mode.value if hasattr(unit_mode, "value") else str(unit_mode)
        divisor, unit_str, is_bytes = unit_map.get(val, (1024.0, f"{val}/s", False))

    if is_bytes:
        dl_str = f"{download_bps:.0f}"
        ul_str = f"{upload_bps:.0f}"
    else:
        dl_str = f"{download_bps / divisor:.1f}"
        ul_str = f"{upload_bps / divisor:.1f}"

    return f"↓ {dl_str} ↑ {ul_str} {unit_str}"


def format_menubar_title(
    download_bps: float,
    upload_bps: float,
    display_mode: DisplayMode,
    unit_mode: UnitMode,
) -> str:
    """Format the menu-bar title string.

    Args:
        download_bps: Current download speed in bytes/sec.
        upload_bps: Current upload speed in bytes/sec.
        display_mode: How to display the speeds.
        unit_mode: Which unit to use.

    Returns:
        Formatted title string for the macOS menu bar.
    """
    if display_mode == DisplayMode.DOWNLOAD_UPLOAD:
        return _format_dual_speed(download_bps, upload_bps, unit_mode)

    if display_mode == DisplayMode.DOWNLOAD_ONLY:
        return f"↓ {_speed(download_bps, unit_mode)}"

    if display_mode == DisplayMode.UPLOAD_ONLY:
        return f"↑ {_speed(upload_bps, unit_mode)}"

    if display_mode == DisplayMode.COMPACT:
        return _format_compact(download_bps, upload_bps, unit_mode)

    if display_mode == DisplayMode.SMART:
        return _format_smart(download_bps, upload_bps, unit_mode)

    # Fallback
    return _format_dual_speed(download_bps, upload_bps, unit_mode)


# ------------------------------------------------------------------
# Compact
# ------------------------------------------------------------------

_COMPACT_TIERS = [
    (1024 ** 3, "G"),
    (1024 ** 2, "M"),
    (1024, "K"),
]


def _compact_unit(bps: float) -> tuple:
    """Pick the compact unit tier for a speed value.

    Returns (divisor, suffix).
    """
    for divisor, suffix in _COMPACT_TIERS:
        if bps >= divisor:
            return (divisor, suffix)
    return (1, "B")


def _format_compact(
    download_bps: float,
    upload_bps: float,
    unit_mode: UnitMode,
) -> str:
    """Compact format using a shared unit and abbreviated suffix.

    In AUTO mode, the shared unit is chosen from the larger speed.
    Example: ``↓12.4M ↑1.2M``
    """
    if unit_mode != UnitMode.AUTO:
        divisors = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}
        suffixes = {"KB": "K", "MB": "M", "GB": "G"}
        divisor = divisors.get(unit_mode.value, 1)
        suffix = suffixes.get(unit_mode.value, "B")
    else:
        max_bps = max(download_bps, upload_bps)
        divisor, suffix = _compact_unit(max_bps)

    if divisor <= 1:
        return f"↓{download_bps:.0f}B ↑{upload_bps:.0f}B"

    dl_val = download_bps / divisor
    ul_val = upload_bps / divisor
    return f"↓{dl_val:.1f}{suffix} ↑{ul_val:.1f}{suffix}"


# ------------------------------------------------------------------
# Smart
# ------------------------------------------------------------------

def _format_smart(
    download_bps: float,
    upload_bps: float,
    unit_mode: UnitMode,
) -> str:
    """Smart display: show only directions with significant traffic.

    - Both ≥ 1 KB/s → show both (like DOWNLOAD_UPLOAD)
    - Only download ≥ 1 KB/s → download only
    - Only upload ≥ 1 KB/s → upload only
    - Both idle → show both (user sees idle state)
    """
    dl_active = download_bps >= _SMART_THRESHOLD_BPS
    ul_active = upload_bps >= _SMART_THRESHOLD_BPS

    if dl_active and not ul_active:
        return f"↓ {_speed(download_bps, unit_mode)}"

    if ul_active and not dl_active:
        return f"↑ {_speed(upload_bps, unit_mode)}"

    # Both active or both idle
    return _format_dual_speed(download_bps, upload_bps, unit_mode)
