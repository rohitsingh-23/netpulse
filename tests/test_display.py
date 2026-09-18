"""Tests for menu-bar display formatting.

Tests format_menubar_title() for all 5 display modes, unit modes,
and edge cases. Fully testable without macOS or rumps.
"""

from netpulse.config.models import DisplayMode, UnitMode
from netpulse.menubar.display import format_menubar_title

KB = 1024
MB = 1024 ** 2
GB = 1024 ** 3


# ==================================================================
# DOWNLOAD + UPLOAD mode
# ==================================================================


class TestDownloadUpload:
    def test_basic(self) -> None:
        title = format_menubar_title(12.4 * MB, 1.2 * MB, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" in title
        assert "12.4" in title
        assert "1.2 MB/s" in title
        assert title == "↓ 12.4 ↑ 1.2 MB/s"

    def test_zero(self) -> None:
        title = format_menubar_title(0, 0, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" in title

    def test_explicit_kb(self) -> None:
        title = format_menubar_title(5 * MB, 2 * MB, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.KB)
        assert "KB/s" in title


# ==================================================================
# DOWNLOAD ONLY mode
# ==================================================================


class TestDownloadOnly:
    def test_shows_download(self) -> None:
        title = format_menubar_title(10 * MB, 5 * MB, DisplayMode.DOWNLOAD_ONLY, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" not in title

    def test_format(self) -> None:
        title = format_menubar_title(12.4 * MB, 0, DisplayMode.DOWNLOAD_ONLY, UnitMode.AUTO)
        assert "12.4 MB/s" in title


# ==================================================================
# UPLOAD ONLY mode
# ==================================================================


class TestUploadOnly:
    def test_shows_upload(self) -> None:
        title = format_menubar_title(10 * MB, 5 * MB, DisplayMode.UPLOAD_ONLY, UnitMode.AUTO)
        assert "↑" in title
        assert "↓" not in title

    def test_format(self) -> None:
        title = format_menubar_title(0, 1.2 * MB, DisplayMode.UPLOAD_ONLY, UnitMode.AUTO)
        assert "1.2 MB/s" in title


# ==================================================================
# COMPACT mode
# ==================================================================


class TestCompact:
    def test_both_arrows(self) -> None:
        title = format_menubar_title(12.4 * MB, 1.2 * MB, DisplayMode.COMPACT, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" in title

    def test_shorter_than_full(self) -> None:
        full = format_menubar_title(12.4 * MB, 1.2 * MB, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.AUTO)
        compact = format_menubar_title(12.4 * MB, 1.2 * MB, DisplayMode.COMPACT, UnitMode.AUTO)
        assert len(compact) < len(full)

    def test_shared_unit_suffix(self) -> None:
        title = format_menubar_title(12.4 * MB, 1.2 * MB, DisplayMode.COMPACT, UnitMode.AUTO)
        # Should use abbreviated suffix like M
        assert "M" in title

    def test_zero_compact(self) -> None:
        title = format_menubar_title(0, 0, DisplayMode.COMPACT, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" in title

    def test_kb_range(self) -> None:
        title = format_menubar_title(50 * KB, 10 * KB, DisplayMode.COMPACT, UnitMode.AUTO)
        assert "K" in title

    def test_explicit_mb_unit(self) -> None:
        title = format_menubar_title(500 * KB, 100 * KB, DisplayMode.COMPACT, UnitMode.MB)
        assert "M" in title


# ==================================================================
# SMART mode
# ==================================================================


class TestSmart:
    def test_both_active(self) -> None:
        title = format_menubar_title(10 * MB, 5 * MB, DisplayMode.SMART, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" in title

    def test_only_download_active(self) -> None:
        # upload below 1 KB/s threshold
        title = format_menubar_title(10 * MB, 500, DisplayMode.SMART, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" not in title

    def test_only_upload_active(self) -> None:
        title = format_menubar_title(500, 10 * MB, DisplayMode.SMART, UnitMode.AUTO)
        assert "↑" in title
        assert "↓" not in title

    def test_both_idle(self) -> None:
        title = format_menubar_title(100, 50, DisplayMode.SMART, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" in title

    def test_at_threshold(self) -> None:
        # Exactly at 1 KB/s threshold — should show
        title = format_menubar_title(1024, 100, DisplayMode.SMART, UnitMode.AUTO)
        assert "↓" in title
        assert "↑" not in title


# ==================================================================
# Unit mode interactions
# ==================================================================


class TestUnitModes:
    def test_auto(self) -> None:
        title = format_menubar_title(12.4 * MB, 1.2 * MB, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.AUTO)
        assert "MB/s" in title

    def test_kb(self) -> None:
        title = format_menubar_title(5 * MB, 2 * MB, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.KB)
        assert "KB/s" in title

    def test_mb(self) -> None:
        title = format_menubar_title(500 * KB, 100 * KB, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.MB)
        assert "MB/s" in title

    def test_gb(self) -> None:
        title = format_menubar_title(2 * GB, 1 * GB, DisplayMode.DOWNLOAD_UPLOAD, UnitMode.GB)
        assert "GB/s" in title
        assert "2.0" in title
