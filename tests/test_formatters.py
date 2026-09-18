"""Tests for formatting utilities.

Covers format_speed (auto + explicit units) and format_bytes,
including edge cases: 0, negative, boundary values, very large.
"""

import pytest

from netpulse.utils.formatters import format_bytes, format_speed

KB = 1024
MB = 1024 ** 2
GB = 1024 ** 3
TB = 1024 ** 4


class TestFormatSpeedAuto:
    """Auto unit selection."""

    def test_zero(self) -> None:
        assert format_speed(0) == "0 B/s"

    def test_bytes_range(self) -> None:
        assert format_speed(500) == "500 B/s"

    def test_one_kb(self) -> None:
        assert format_speed(KB) == "1.0 KB/s"

    def test_one_mb(self) -> None:
        assert format_speed(MB) == "1.0 MB/s"

    def test_one_gb(self) -> None:
        assert format_speed(GB) == "1.0 GB/s"

    def test_one_tb(self) -> None:
        assert format_speed(TB) == "1.0 TB/s"

    def test_fractional_mb(self) -> None:
        bps = 12.4 * MB
        assert format_speed(bps) == "12.4 MB/s"

    def test_auto_upgrades_at_boundary(self) -> None:
        # 1024 KB/s should display as 1.0 MB/s, not 1024.0 KB/s
        assert format_speed(MB) == "1.0 MB/s"

    def test_sub_kb(self) -> None:
        assert format_speed(1023) == "1023 B/s"

    def test_very_large(self) -> None:
        result = format_speed(TB * 10)
        assert "TB/s" in result


class TestFormatSpeedExplicitUnit:
    """Explicit unit selection."""

    def test_explicit_kb(self) -> None:
        assert format_speed(2 * KB, unit="KB") == "2.0 KB/s"

    def test_explicit_mb(self) -> None:
        assert format_speed(5 * MB, unit="MB") == "5.0 MB/s"

    def test_explicit_b(self) -> None:
        assert format_speed(500, unit="B") == "500 B/s"

    def test_explicit_gb(self) -> None:
        assert format_speed(2 * GB, unit="GB") == "2.0 GB/s"


class TestFormatSpeedNegative:
    """Negative input clamped to 0."""

    def test_negative_clamped(self) -> None:
        assert format_speed(-100) == "0 B/s"

    def test_negative_large(self) -> None:
        assert format_speed(-MB) == "0 B/s"


class TestFormatBytes:
    """Byte count formatting."""

    def test_zero(self) -> None:
        assert format_bytes(0) == "0 B"

    def test_bytes_range(self) -> None:
        assert format_bytes(500) == "500 B"

    def test_one_kb(self) -> None:
        assert format_bytes(KB) == "1.00 KB"

    def test_one_mb(self) -> None:
        assert format_bytes(MB) == "1.00 MB"

    def test_one_gb(self) -> None:
        assert format_bytes(GB) == "1.00 GB"

    def test_one_tb(self) -> None:
        assert format_bytes(TB) == "1.00 TB"

    def test_fractional_gb(self) -> None:
        b = int(8.42 * GB)
        result = format_bytes(b)
        assert "GB" in result
        # Allow minor floating-point variance
        assert result.startswith("8.4")

    def test_negative_clamped(self) -> None:
        assert format_bytes(-100) == "0 B"

    def test_just_under_kb(self) -> None:
        assert format_bytes(1023) == "1023 B"

    def test_very_large(self) -> None:
        result = format_bytes(TB * 5)
        assert "TB" in result
