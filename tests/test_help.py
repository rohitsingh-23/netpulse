"""Tests for the NetPulse Help page."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from netpulse.config.preferences import PreferencesManager
from netpulse.ui.help import HelpPage
from netpulse.utils.constants import APP_VERSION


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_help_page_construction(qapp: QApplication, tmp_path) -> None:
    """Verify HelpPage instantiates with all required sections and correct version."""
    prefs_file = tmp_path / "prefs.json"
    prefs_mgr = PreferencesManager(prefs_file)
    prefs_mgr.load()

    page = HelpPage(prefs_mgr)

    # Collect all QLabel text content
    labels = page.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]
    combined = " ".join(texts)

    # Verify major sections exist
    assert "Help" in combined
    assert "1. GETTING STARTED" in combined
    assert "2. NETWORK MONITORING" in combined
    assert "3. SPEED TEST" in combined
    assert "4. NOTIFICATIONS" in combined
    assert "5. PRIVACY & DATA" in combined
    assert "6. DATA & STORAGE" in combined
    assert "7. TROUBLESHOOTING" in combined
    assert "8. ABOUT NETPULSE" in combined

    # Verify version display is accurate and not hardcoded
    assert f"v{APP_VERSION}" in combined

    # Verify key privacy topics
    assert "Local Storage Only" in combined
    assert "Zero Telemetry" in combined
    assert "Location Permission" in combined or "Location permission" in combined
    assert "Reset Statistics & History" in combined
    assert "Reset All NetPulse Data" in combined

    # Verify support contact and GitHub links
    assert "Need help?" in combined
    assert "rohit23498@gmail.com" in combined
    assert "Source Code" in combined
    assert "Report a Bug" in combined
    assert "https://github.com/rohitsingh-23/netpulse" in combined
    assert "https://github.com/rohitsingh-23/netpulse/issues" in combined
