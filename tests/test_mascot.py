"""Unit tests for the NetPulse lion mascot animation controller and asset loader."""

from __future__ import annotations

import time
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from netpulse.config.models import AppPreferences
from netpulse.config.preferences import PreferencesManager
from netpulse.ui.mascot import (
    LionMascotController,
    MascotAssetLoader,
    MascotFrame,
    MascotSpeedThresholds,
    MascotState,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QCoreApplication / QApplication instance exists for QTimer/QPixmap."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def asset_loader(qapp) -> MascotAssetLoader:
    return MascotAssetLoader()


@pytest.fixture
def thresholds() -> MascotSpeedThresholds:
    return MascotSpeedThresholds(
        idle_threshold_bps=10 * 1024.0,       # 10 KB/s
        low_threshold_bps=300 * 1024.0,      # 300 KB/s
        medium_threshold_bps=2.0 * 1024 * 1024.0,  # 2 MB/s
        spike_min_jump_bps=1.5 * 1024 * 1024.0,
        spike_ratio_multiplier=3.0,
        roar_cooldown_seconds=10.0,
        yawn_cooldown_seconds=5.0,
        yawn_cycle_interval=5,
    )


@pytest.fixture
def controller(qapp, asset_loader, thresholds) -> LionMascotController:
    return LionMascotController(
        enabled=True,
        thresholds=thresholds,
        asset_loader=asset_loader,
    )


class TestAssetLoadingAndCaching:
    def test_all_state_directories_loaded(self, asset_loader: MascotAssetLoader):
        for state in MascotState:
            frames = asset_loader.get_frames(state)
            assert len(frames) > 0, f"Expected frames for {state}"
            for f in frames:
                assert isinstance(f, MascotFrame)
                assert f.state == state
                assert f.pixmap is not None
                assert not f.pixmap.isNull()

    def test_idle_yawn_frames_cached(self, asset_loader: MascotAssetLoader):
        yawn_frames = asset_loader.get_frames(MascotState.IDLE, substate="yawn")
        assert len(yawn_frames) >= 4
        for f in yawn_frames:
            assert f.state == MascotState.IDLE
            assert f.substate == "yawn"
            assert not f.pixmap.isNull()


class TestIdleState:
    def test_zero_speed_is_idle(self, controller: LionMascotController):
        controller.update_speed(0.0, 0.0)
        assert controller.target_state == MascotState.IDLE
        assert controller.current_state == MascotState.IDLE

    def test_idle_breathing_and_blinking(self, controller: LionMascotController):
        controller.update_speed(0.0, 0.0)
        initial_frame = controller.current_frame
        assert initial_frame is not None

        # Step through idle frames
        controller.advance_frame()
        frame1 = controller.current_frame
        assert frame1.index != initial_frame.index or frame1 != initial_frame

    def test_infrequent_yawn_trigger(self, controller: LionMascotController):
        controller.update_speed(0.0, 0.0)
        t = 100.0

        # Advance enough ticks to reach yawn_cycle_interval
        for _ in range(controller.thresholds.yawn_cycle_interval):
            controller.advance_frame(now=t)

        # Should enter yawn substate
        assert controller._substate == "yawn"
        assert controller.current_frame.substate == "yawn"

        # Complete yawn sequence
        yawn_len = len(controller._loader.get_frames(MascotState.IDLE, substate="yawn"))
        for _ in range(yawn_len):
            controller.advance_frame(now=t)

        # Returns to normal idle
        assert controller._substate is None
        assert controller.current_state == MascotState.IDLE


class TestLowActivityState:
    def test_low_speed_mapping(self, controller: LionMascotController):
        # 50 KB/s is between 10 KB/s and 300 KB/s
        controller.update_speed(30 * 1024.0, 20 * 1024.0)
        assert controller.target_state == MascotState.LOW
        controller.advance_frame()
        assert controller.current_state == MascotState.LOW
        assert controller.current_frame.state == MascotState.LOW


class TestMediumActivityState:
    def test_medium_speed_mapping(self, controller: LionMascotController):
        # 1 MB/s is between 300 KB/s and 2 MB/s
        controller.update_speed(500 * 1024.0, 500 * 1024.0)
        assert controller.target_state == MascotState.WALK
        controller.advance_frame()
        assert controller.current_state == MascotState.WALK
        assert controller.current_frame.state == MascotState.WALK


class TestHighActivityState:
    def test_high_speed_mapping_and_timer_interval(self, controller: LionMascotController):
        # 5 MB/s is > 2 MB/s
        controller.update_speed(3.0 * 1024 * 1024.0, 2.0 * 1024 * 1024.0)
        assert controller.target_state == MascotState.RUN
        controller.advance_frame()
        assert controller.current_state == MascotState.RUN

        # Check that higher activity increases speed (lower timer interval)
        interval_5mb = controller._compute_timer_interval(MascotState.RUN)
        controller.update_speed(30.0 * 1024 * 1024.0, 20.0 * 1024 * 1024.0)
        interval_50mb = controller._compute_timer_interval(MascotState.RUN)
        assert interval_50mb <= interval_5mb


class TestSpikeAndRoarCooldown:
    def test_traffic_spike_triggers_roar(self, controller: LionMascotController):
        t0 = 100.0
        # Start at steady 500 KB/s
        controller.update_speed(300 * 1024.0, 200 * 1024.0, now=t0)
        controller.advance_frame(now=t0)
        assert controller.current_state == MascotState.WALK

        # Sudden jump from 500 KB/s to 4 MB/s (delta = 3.5 MB/s > 1.5 MB/s, ratio 8x > 3x)
        controller.update_speed(3.0 * 1024 * 1024.0, 1.0 * 1024 * 1024.0, now=t0 + 1.0)
        assert controller.current_state == MascotState.ROAR
        assert controller._is_playing_one_shot is True

        # Roar plays all frames and reverts to RUN
        roar_frames_count = len(controller._loader.get_frames(MascotState.ROAR))
        for _ in range(roar_frames_count):
            controller.advance_frame(now=t0 + 1.0)

        assert controller.current_state == MascotState.RUN
        assert controller._is_playing_one_shot is False

    def test_roar_cooldown_prevents_repeated_roars(self, controller: LionMascotController):
        t0 = 200.0
        # First spike
        controller.update_speed(100 * 1024.0, 100 * 1024.0, now=t0)
        controller.advance_frame(now=t0)
        controller.update_speed(3.0 * 1024 * 1024.0, 2.0 * 1024 * 1024.0, now=t0 + 1.0)
        assert controller.current_state == MascotState.ROAR

        # Complete roar
        for _ in range(4):
            controller.advance_frame(now=t0 + 1.0)
        assert controller.current_state == MascotState.RUN

        # Another immediate spike during cooldown period (within 10s)
        controller.update_speed(50 * 1024.0, 50 * 1024.0, now=t0 + 2.0)
        controller.update_speed(5.0 * 1024 * 1024.0, 5.0 * 1024 * 1024.0, now=t0 + 3.0)
        # Should NOT roar because cooldown has not elapsed
        assert controller.current_state != MascotState.ROAR
        assert controller.target_state == MascotState.RUN


class TestDisconnectedAndReconnect:
    def test_disconnect_state(self, controller: LionMascotController):
        # Connected and running
        controller.update_speed(3.0 * 1024 * 1024.0, 2.0 * 1024 * 1024.0)
        controller.advance_frame()
        assert controller.current_state == MascotState.RUN

        # Disconnect network
        controller.update_connection(is_connected=False)
        assert controller.is_connected is False
        assert controller.current_state == MascotState.DISCONNECTED
        assert controller.current_frame.state == MascotState.DISCONNECTED

        # Traffic during disconnected state does not trigger running
        controller.update_speed(5.0 * 1024 * 1024.0, 5.0 * 1024 * 1024.0)
        assert controller.current_state == MascotState.DISCONNECTED

    def test_reconnect_transition(self, controller: LionMascotController):
        controller.update_connection(is_connected=False)
        assert controller.current_state == MascotState.DISCONNECTED

        # Reconnect
        controller.update_connection(is_connected=True)
        assert controller.current_state == MascotState.RECONNECT
        assert controller._is_playing_one_shot is True

        # Advance frames through reconnect sequence
        reconn_frames = len(controller._loader.get_frames(MascotState.RECONNECT))
        for _ in range(reconn_frames):
            controller.advance_frame()

        assert controller._is_playing_one_shot is False
        assert controller.current_state in (MascotState.IDLE, MascotState.LOW, MascotState.WALK, MascotState.RUN)


class TestStateTransitions:
    def test_smooth_transition_idle_to_walk_and_back(self, controller: LionMascotController):
        controller.update_speed(0.0, 0.0)
        assert controller.current_state == MascotState.IDLE

        # Traffic begins
        controller.update_speed(500 * 1024.0, 500 * 1024.0)
        assert controller.target_state == MascotState.WALK
        # Next frame advances smoothly into walk
        controller.advance_frame()
        assert controller.current_state == MascotState.WALK

        # Traffic stops
        controller.update_speed(0.0, 0.0)
        assert controller.target_state == MascotState.IDLE
        controller.advance_frame()
        assert controller.current_state == MascotState.IDLE


class TestMascotPreferences:
    def test_disabled_mascot_stops_animation_and_clears_frame(self, controller: LionMascotController):
        assert controller.enabled is True
        assert controller.current_frame is not None

        callback_frames = []
        controller._on_frame_changed_cb = lambda f: callback_frames.append(f)

        controller.set_enabled(False)
        assert controller.enabled is False
        assert controller.current_frame is None
        assert not controller._timer.isActive()
        assert callback_frames[-1] is None

        # Re-enable
        controller.set_enabled(True)
        assert controller.enabled is True
        assert controller.current_frame is not None
        assert controller._timer.isActive()

    def test_preference_persistence(self, tmp_path: Path):
        mgr = PreferencesManager(path=tmp_path / "prefs.json")
        prefs = mgr.load()
        assert prefs.enable_mascot is True

        mgr.update(enable_mascot=False)
        mgr2 = PreferencesManager(path=tmp_path / "prefs.json")
        prefs2 = mgr2.load()
        assert prefs2.enable_mascot is False
