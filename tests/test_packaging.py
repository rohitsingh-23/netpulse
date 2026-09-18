"""Tests validating packaging metadata, Info.plist properties, and user-data isolation."""

import plistlib
from pathlib import Path
import pytest

from netpulse.config.preferences import _default_prefs_dir
from netpulse.utils.constants import APP_BUNDLE_ID, APP_NAME, APP_VERSION


def test_user_data_directory_outside_app_bundle():
    """Verify preferences and database paths remain in ~/Library/Application Support/."""
    prefs_dir = _default_prefs_dir()
    assert "Contents/Resources" not in str(prefs_dir)
    assert ".app" not in str(prefs_dir)
    assert str(prefs_dir).endswith(f"Library/Application Support/{APP_NAME}")


def test_packaging_metadata_consistency():
    """Verify version and bundle id consistency across constants."""
    assert APP_VERSION == "0.7.0"
    assert APP_NAME == "NetPulse"
    assert APP_BUNDLE_ID == "com.netpulse.app"


def test_info_plist_if_built():
    """If dist/NetPulse.app exists, verify Info.plist contains all required macOS privacy keys."""
    plist_path = Path("dist/NetPulse.app/Contents/Info.plist")
    if not plist_path.exists():
        pytest.skip("dist/NetPulse.app not built yet")

    with open(plist_path, "rb") as f:
        data = plistlib.load(f)

    assert data.get("CFBundleIdentifier") == "com.netpulse.app"
    assert data.get("CFBundleName") == "NetPulse"
    assert data.get("CFBundleShortVersionString") == "0.7.0"
    assert "NSLocationWhenInUseUsageDescription" in data
    assert "NSLocationUsageDescription" in data
    assert len(data["NSLocationWhenInUseUsageDescription"]) > 10
