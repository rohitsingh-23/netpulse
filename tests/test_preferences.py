"""Tests for PreferencesManager.

Uses pytest tmp_path to avoid touching the user's real preferences.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from netpulse.config.models import (
    AppPreferences,
    DisplayMode,
    UnitMode,
    DEFAULT_INTERVAL,
)
from netpulse.config.preferences import PreferencesManager


class TestDefaultsWhenNoFile:
    def test_load_returns_defaults(self, tmp_path: Path) -> None:
        mgr = PreferencesManager(path=tmp_path / "prefs.json")
        prefs = mgr.load()
        assert prefs.display_mode == DisplayMode.DOWNLOAD_UPLOAD
        assert prefs.unit_mode == UnitMode.AUTO
        assert prefs.sample_interval == DEFAULT_INTERVAL


class TestSaveAndLoad:
    def test_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        mgr = PreferencesManager(path=path)
        mgr.load()
        from netpulse.config.models import AppearanceMode
        mgr.update(
            display_mode=DisplayMode.COMPACT,
            unit_mode=UnitMode.MB,
            sample_interval=2.0,
            appearance=AppearanceMode.DARK,
            enable_mascot=False,
        )

        # Load in a fresh manager
        mgr2 = PreferencesManager(path=path)
        prefs = mgr2.load()
        assert prefs.display_mode == DisplayMode.COMPACT
        assert prefs.unit_mode == UnitMode.MB
        assert prefs.sample_interval == 2.0
        assert prefs.appearance == AppearanceMode.DARK
        assert prefs.enable_mascot is False

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "prefs.json"
        mgr = PreferencesManager(path=path)
        mgr.load()
        mgr.save()
        assert path.exists()


class TestPartialPreferences:
    def test_missing_display_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text(json.dumps({"unit_mode": "MB", "sample_interval": 2.0}))
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs.display_mode == DisplayMode.DOWNLOAD_UPLOAD  # default
        assert prefs.unit_mode == UnitMode.MB
        assert prefs.sample_interval == 2.0

    def test_missing_unit_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text(json.dumps({"display_mode": "compact"}))
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs.display_mode == DisplayMode.COMPACT
        assert prefs.unit_mode == UnitMode.AUTO  # default

    def test_empty_object(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text("{}")
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs.display_mode == DisplayMode.DOWNLOAD_UPLOAD
        assert prefs.unit_mode == UnitMode.AUTO
        assert prefs.sample_interval == DEFAULT_INTERVAL


class TestCorruptedPreferences:
    def test_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text("not valid json {{{")
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs == AppPreferences()

    def test_json_array_instead_of_object(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text("[1, 2, 3]")
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs == AppPreferences()

    def test_invalid_display_mode_value(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text(json.dumps({"display_mode": "nonexistent"}))
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs.display_mode == DisplayMode.DOWNLOAD_UPLOAD

    def test_invalid_unit_mode_value(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text(json.dumps({"unit_mode": "TB"}))
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs.unit_mode == UnitMode.AUTO

    def test_invalid_interval_value(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text(json.dumps({"sample_interval": 99.9}))
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs.sample_interval == DEFAULT_INTERVAL

    def test_interval_string_value(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        path.write_text(json.dumps({"sample_interval": "not_a_number"}))
        mgr = PreferencesManager(path=path)
        prefs = mgr.load()
        assert prefs.sample_interval == DEFAULT_INTERVAL


class TestUpdate:
    def test_update_single_field(self, tmp_path: Path) -> None:
        mgr = PreferencesManager(path=tmp_path / "prefs.json")
        mgr.load()
        mgr.update(display_mode=DisplayMode.UPLOAD_ONLY)
        assert mgr.preferences.display_mode == DisplayMode.UPLOAD_ONLY
        # Other fields unchanged
        assert mgr.preferences.unit_mode == UnitMode.AUTO

    def test_update_multiple_fields(self, tmp_path: Path) -> None:
        mgr = PreferencesManager(path=tmp_path / "prefs.json")
        mgr.load()
        mgr.update(
            display_mode=DisplayMode.SMART,
            unit_mode=UnitMode.GB,
            sample_interval=5.0,
        )
        assert mgr.preferences.display_mode == DisplayMode.SMART
        assert mgr.preferences.unit_mode == UnitMode.GB
        assert mgr.preferences.sample_interval == 5.0

    def test_update_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "prefs.json"
        mgr = PreferencesManager(path=path)
        mgr.load()
        mgr.update(unit_mode=UnitMode.KB)

        mgr2 = PreferencesManager(path=path)
        prefs = mgr2.load()
        assert prefs.unit_mode == UnitMode.KB

    def test_update_invalid_interval_corrected(self, tmp_path: Path) -> None:
        mgr = PreferencesManager(path=tmp_path / "prefs.json")
        mgr.load()
        mgr.update(sample_interval=7.0)
        assert mgr.preferences.sample_interval == DEFAULT_INTERVAL
