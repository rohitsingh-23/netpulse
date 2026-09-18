"""Speed and byte formatting utilities for NetPulse.

Uses binary units throughout: 1 KB = 1024 bytes.
"""

from __future__ import annotations

from netpulse.utils.constants import BINARY_UNITS, BYTES_PER_UNIT


def format_speed(bps: float, unit: str = "auto") -> str:
    """Format bytes-per-second into a human-readable speed string.

    Args:
        bps: Speed in bytes per second. Negative values clamped to 0.
        unit: Target unit — ``"auto"``, ``"B"``, ``"KB"``, ``"MB"``,
              ``"GB"``, or ``"TB"``.

    Returns:
        Formatted string such as ``"12.4 MB/s"``.
    """
    if bps < 0:
        bps = 0.0

    if unit != "auto":
        unit_upper = unit.upper().rstrip("/S")
        if unit_upper in BINARY_UNITS:
            idx = BINARY_UNITS.index(unit_upper)
            value = bps / (BYTES_PER_UNIT ** idx) if idx > 0 else bps
            if idx == 0:
                return f"{value:.0f} B/s"
            return f"{value:.1f} {BINARY_UNITS[idx]}/s"

    # Auto mode — pick the largest unit that keeps value >= 1
    if bps < BYTES_PER_UNIT:
        return f"{bps:.0f} B/s"

    value = float(bps)
    for unit_name in BINARY_UNITS[1:]:
        value /= BYTES_PER_UNIT
        if value < BYTES_PER_UNIT:
            return f"{value:.1f} {unit_name}/s"

    # Overflow into largest unit
    return f"{value:.1f} {BINARY_UNITS[-1]}/s"


def format_bytes(total_bytes: int | float) -> str:
    """Format a byte count into a human-readable string.

    Args:
        total_bytes: Total bytes. Negative values clamped to 0.

    Returns:
        Formatted string such as ``"8.42 GB"``.
    """
    if total_bytes < 0:
        total_bytes = 0

    if total_bytes < BYTES_PER_UNIT:
        return f"{int(total_bytes)} B"

    value = float(total_bytes)
    for unit_name in BINARY_UNITS[1:]:
        value /= BYTES_PER_UNIT
        if value < BYTES_PER_UNIT:
            return f"{value:.2f} {unit_name}"

    return f"{value:.2f} {BINARY_UNITS[-1]}"
