"""Tests for configuration models."""

from netpulse.config.models import (
    AppPreferences,
    DisplayMode,
    UnitMode,
    VALID_INTERVALS,
    DEFAULT_INTERVAL,
    DISPLAY_MODE_LABELS,
    UNIT_MODE_LABELS,
    INTERVAL_LABELS,
)


class TestDisplayMode:
    def test_all_values(self) -> None:
        modes = [m.value for m in DisplayMode]
        assert "download_upload" in modes
        assert "download_only" in modes
        assert "upload_only" in modes
        assert "compact" in modes
        assert "smart" in modes

    def test_from_string(self) -> None:
        assert DisplayMode("download_upload") == DisplayMode.DOWNLOAD_UPLOAD
        assert DisplayMode("compact") == DisplayMode.COMPACT

    def test_labels_complete(self) -> None:
        for mode in DisplayMode:
            assert mode in DISPLAY_MODE_LABELS


class TestUnitMode:
    def test_all_values(self) -> None:
        modes = [m.value for m in UnitMode]
        assert "auto" in modes
        assert "KB" in modes
        assert "MB" in modes
        assert "GB" in modes

    def test_labels_complete(self) -> None:
        for mode in UnitMode:
            assert mode in UNIT_MODE_LABELS


class TestAppPreferencesDefaults:
    def test_defaults(self) -> None:
        prefs = AppPreferences()
        assert prefs.display_mode == DisplayMode.DOWNLOAD_UPLOAD
        assert prefs.unit_mode == UnitMode.AUTO
        assert prefs.sample_interval == DEFAULT_INTERVAL
        assert prefs.enable_mascot is True

    def test_custom_values(self) -> None:
        prefs = AppPreferences(
            display_mode=DisplayMode.COMPACT,
            unit_mode=UnitMode.MB,
            sample_interval=2.0,
        )
        assert prefs.display_mode == DisplayMode.COMPACT
        assert prefs.unit_mode == UnitMode.MB
        assert prefs.sample_interval == 2.0


class TestAppPreferencesValidation:
    def test_invalid_interval_corrected(self) -> None:
        prefs = AppPreferences(sample_interval=3.0)  # not in VALID_INTERVALS
        assert prefs.sample_interval == DEFAULT_INTERVAL

    def test_valid_intervals(self) -> None:
        for interval in VALID_INTERVALS:
            prefs = AppPreferences(sample_interval=interval)
            assert prefs.sample_interval == interval

    def test_interval_labels_complete(self) -> None:
        for interval in VALID_INTERVALS:
            assert interval in INTERVAL_LABELS


class TestAppearanceMode:
    def test_all_values(self) -> None:
        from netpulse.config.models import AppearanceMode, APPEARANCE_MODE_LABELS
        modes = [m.value for m in AppearanceMode]
        assert "system" in modes
        assert "light" in modes
        assert "dark" in modes
        for mode in AppearanceMode:
            assert mode in APPEARANCE_MODE_LABELS
