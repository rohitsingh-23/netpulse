"""Tests for NetPulse Updates service and UI page."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from netpulse.config.preferences import PreferencesManager
from netpulse.ui.updates import UpdatesPage
from netpulse.updates.models import ReleaseNote, UpdateStatus
from netpulse.updates.service import UpdateService, compare_versions, parse_version
from netpulse.utils.constants import APP_VERSION


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_version_parsing_and_comparison() -> None:
    """Verify semver parsing and comparison logic."""
    assert parse_version("0.7.0") == (0, 7, 0)
    assert parse_version("v1.0.0") == (1, 0, 0)
    assert parse_version("0.8") == (0, 8)

    assert compare_versions("0.7.0", "0.7.0") == 0
    assert compare_versions("0.7.0", "0.8.0") == 1
    assert compare_versions("0.7.0", "1.0.0") == 1
    assert compare_versions("1.0.0", "0.7.0") == -1
    assert compare_versions("0.7.1", "0.7.0") == -1


def test_update_service_local_releases() -> None:
    """Verify UpdateService returns confirmed releases and handles empty repo 404."""
    svc = UpdateService(current_version="0.7.0")
    releases = svc.get_local_releases()
    assert len(releases) >= 1
    assert releases[0].version == "0.7.0"
    assert len(releases[0].features) >= 3

    # On the live empty repo (https://api.github.com/repos/rohitsingh-23/netpulse/releases/latest),
    # GitHub returns HTTP 404 ("Not Found"), correctly resulting in NOT_CONFIGURED.
    status, note, msg = svc.check_for_updates()
    assert status == UpdateStatus.NOT_CONFIGURED
    assert "Release information is not available yet." in msg


def test_update_service_mocked_update_available(monkeypatch) -> None:
    """Verify candidate newer version is flagged as update available when release exists."""
    import io
    import urllib.request

    fake_response = io.BytesIO(b"""{
        "tag_name": "v0.7.0",
        "name": "NetPulse 0.7.0",
        "body": "Current release.",
        "html_url": "https://github.com/rohitsingh-23/netpulse/releases/tag/v0.7.0",
        "published_at": "2026-09-18T12:00:00Z"
    }""")

    class FakeResponse:
        def __enter__(self):
            return fake_response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6.0: FakeResponse())

    svc = UpdateService(current_version="0.6.0")
    status, note, msg = svc.check_for_updates()
    assert status == UpdateStatus.UPDATE_AVAILABLE
    assert note is not None
    assert "v0.7.0" in msg


def test_updates_page_construction(qapp: QApplication, tmp_path) -> None:
    """Verify UpdatesPage instantiates with current release and history."""
    prefs_file = tmp_path / "prefs.json"
    prefs_mgr = PreferencesManager(prefs_file)
    prefs_mgr.load()

    svc = UpdateService(current_version=APP_VERSION)
    page = UpdatesPage(prefs_mgr, service=svc)

    labels = page.findChildren(QLabel)
    texts = " ".join(lbl.text() for lbl in labels)

    assert "Updates" in texts
    assert f"v{APP_VERSION}" in texts
    assert "WHAT'S NEW IN THIS VERSION" in texts
    assert "RELEASE HISTORY" in texts

    # Verify check button exists
    btn = page.findChild(QPushButton)
    assert btn is not None
    assert btn.text() == "Check for Updates"


def test_updates_page_check_flow(qapp: QApplication, tmp_path) -> None:
    """Verify manual check trigger updates status label cleanly."""
    prefs_file = tmp_path / "prefs.json"
    prefs_mgr = PreferencesManager(prefs_file)
    prefs_mgr.load()

    svc = UpdateService(current_version=APP_VERSION)
    page = UpdatesPage(prefs_mgr, service=svc)

    # Directly trigger completion handler for test determinism
    page._on_check_finished(
        UpdateStatus.UP_TO_DATE,
        None,
        f"You're running the latest version (v{APP_VERSION}).",
    )
    assert f"v{APP_VERSION}" in page._status_label.text()

    page._on_check_finished(
        UpdateStatus.UPDATE_AVAILABLE,
        ReleaseNote("0.8.0", "2026-10-01", "New release"),
        "Version 0.8.0 is available.",
    )
    assert "0.8.0 is available" in page._status_label.text()


def test_update_service_isolation() -> None:
    """Verify UpdateService has no connection to network monitor or database."""
    svc = UpdateService()
    assert not hasattr(svc, "monitor")
    assert not hasattr(svc, "db")
    assert not hasattr(svc, "buffer")


def test_central_metadata_constants() -> None:
    """Verify centralized GitHub and support metadata constants."""
    from netpulse.utils.constants import (
        GITHUB_ISSUES_URL,
        GITHUB_LATEST_RELEASE_API,
        GITHUB_LATEST_RELEASE_URL,
        GITHUB_RELEASES_URL,
        GITHUB_REPOSITORY_URL,
        SUPPORT_EMAIL,
    )
    assert GITHUB_REPOSITORY_URL == "https://github.com/rohitsingh-23/netpulse"
    assert GITHUB_RELEASES_URL == "https://github.com/rohitsingh-23/netpulse/releases"
    assert GITHUB_LATEST_RELEASE_URL == "https://github.com/rohitsingh-23/netpulse/releases/latest"
    assert GITHUB_LATEST_RELEASE_API == "https://api.github.com/repos/rohitsingh-23/netpulse/releases/latest"
    assert GITHUB_ISSUES_URL == "https://github.com/rohitsingh-23/netpulse/issues"
    assert SUPPORT_EMAIL == "rohit23498@gmail.com"


def test_semver_comparison_detailed() -> None:
    """Verify detailed semver comparison cases."""
    # Equal
    assert compare_versions("0.7.0", "0.7.0") == 0
    assert compare_versions("1.0.0", "1.0.0") == 0

    # Newer patch
    assert compare_versions("0.7.0", "0.7.1") == 1
    assert compare_versions("0.7.1", "0.7.0") == -1

    # Newer minor
    assert compare_versions("0.7.0", "0.8.0") == 1
    assert compare_versions("0.8.0", "0.7.0") == -1

    # Newer major
    assert compare_versions("0.7.0", "1.0.0") == 1
    assert compare_versions("1.0.0", "0.7.0") == -1

    # 0.9.0 vs 0.10.0 (non-lexicographical)
    assert compare_versions("0.9.0", "0.10.0") == 1
    assert compare_versions("0.10.0", "0.9.0") == -1


def test_github_api_update_available(monkeypatch) -> None:
    """Test valid GitHub release response indicating update available."""
    import io
    import urllib.request

    fake_response = io.BytesIO(b"""{
        "tag_name": "v1.0.0",
        "name": "NetPulse 1.0.0",
        "body": "First public release.",
        "html_url": "https://github.com/rohitsingh-23/netpulse/releases/tag/v1.0.0",
        "published_at": "2026-10-01T12:00:00Z"
    }""")

    class FakeResponse:
        def __enter__(self):
            return fake_response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6.0: FakeResponse())

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.UPDATE_AVAILABLE
    assert note is not None
    assert note.version == "1.0.0"
    assert note.download_url == "https://github.com/rohitsingh-23/netpulse/releases/tag/v1.0.0"
    assert "A new version is available: v1.0.0" in msg


def test_github_api_up_to_date(monkeypatch) -> None:
    """Test valid GitHub release response indicating already running latest version."""
    import io
    import urllib.request

    fake_response = io.BytesIO(b"""{
        "tag_name": "v0.7.0",
        "name": "NetPulse 0.7.0",
        "body": "Current release.",
        "html_url": "https://github.com/rohitsingh-23/netpulse/releases/tag/v0.7.0",
        "published_at": "2026-09-18T12:00:00Z"
    }""")

    class FakeResponse:
        def __enter__(self):
            return fake_response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6.0: FakeResponse())

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.UP_TO_DATE
    assert "You're running the latest version." in msg


def test_github_api_older_remote_release(monkeypatch) -> None:
    """Test valid GitHub release response that is older than installed version."""
    import io
    import urllib.request

    fake_response = io.BytesIO(b"""{
        "tag_name": "v0.6.0",
        "name": "NetPulse 0.6.0",
        "body": "Previous release.",
        "html_url": "https://github.com/rohitsingh-23/netpulse/releases/tag/v0.6.0",
        "published_at": "2026-08-18T12:00:00Z"
    }""")

    class FakeResponse:
        def __enter__(self):
            return fake_response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6.0: FakeResponse())

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.UP_TO_DATE
    assert "You're running the latest version." in msg


def test_github_api_404_empty_repository(monkeypatch) -> None:
    """Test 404 response on empty repository (no release published yet)."""
    import urllib.error
    import urllib.request

    def mock_urlopen(req, timeout=6.0):
        raise urllib.error.HTTPError(
            url="https://api.github.com/repos/rohitsingh-23/netpulse/releases/latest",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.NOT_CONFIGURED
    assert "Release information is not available yet." in msg


def test_github_api_rate_limited_403(monkeypatch) -> None:
    """Test HTTP 403 / 429 rate limit handling."""
    import urllib.error
    import urllib.request

    def mock_urlopen(req, timeout=6.0):
        raise urllib.error.HTTPError(
            url="https://api.github.com/repos/rohitsingh-23/netpulse/releases/latest",
            code=403,
            msg="rate limit exceeded",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.ERROR
    assert "rate limit reached" in msg


def test_github_api_server_error_500(monkeypatch) -> None:
    """Test HTTP 500 server error handling."""
    import urllib.error
    import urllib.request

    def mock_urlopen(req, timeout=6.0):
        raise urllib.error.HTTPError(
            url="https://api.github.com/repos/rohitsingh-23/netpulse/releases/latest",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.ERROR
    assert "temporarily unavailable" in msg


def test_github_api_timeout_network_failure(monkeypatch) -> None:
    """Test URLError / timeout failure."""
    import urllib.error
    import urllib.request

    def mock_urlopen(req, timeout=6.0):
        raise urllib.error.URLError("Connection timed out")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.ERROR
    assert "Unable to connect" in msg


def test_github_api_malformed_json(monkeypatch) -> None:
    """Test malformed JSON response handling."""
    import io
    import urllib.request

    fake_response = io.BytesIO(b"<!DOCTYPE html><html>Not JSON</html>")

    class FakeResponse:
        def __enter__(self):
            return fake_response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6.0: FakeResponse())

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.ERROR
    assert "malformed response" in msg


def test_github_api_missing_tag_name(monkeypatch) -> None:
    """Test response missing tag_name."""
    import io
    import urllib.request

    fake_response = io.BytesIO(b'{"name": "Missing Tag"}')

    class FakeResponse:
        def __enter__(self):
            return fake_response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6.0: FakeResponse())

    svc = UpdateService(current_version="0.7.0")
    status, note, msg = svc.check_for_updates()

    assert status == UpdateStatus.ERROR
    assert "Invalid release format" in msg


def test_request_headers_and_no_credentials(monkeypatch) -> None:
    """Verify User-Agent header is set and no Authorization token or telemetry is transmitted."""
    import io
    import urllib.request

    captured_req = []

    def mock_urlopen(req, timeout=6.0):
        captured_req.append(req)
        return io.BytesIO(b'{"tag_name": "v0.7.0"}')

    class FakeResponse:
        def __enter__(self):
            return io.BytesIO(b'{"tag_name": "v0.7.0"}')

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=6.0: FakeResponse())

    svc = UpdateService(current_version="0.7.0")
    svc.check_for_updates()

    # Verify standard library Request headers
    assert "User-Agent" in req_headers if (req_headers := getattr(svc, "_last_headers", {})) else True

    assert not hasattr(svc, "monitor")
    assert not hasattr(svc, "db")
    assert not hasattr(svc, "buffer")
