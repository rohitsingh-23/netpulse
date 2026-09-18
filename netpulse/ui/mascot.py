"""Lightweight animated lion mascot controller and asset system for NetPulse macOS menu bar.

Organizes frames by state, preloads/caches all assets in memory, dynamically maps
network traffic to animation states and running speeds, handles roar spikes and
reconnection transitions with hysteresis, and exposes rendered NSImage/QPixmap/QIcon
for zero-overhead menu bar display.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap

try:
    import AppKit
    _APPKIT_AVAILABLE = True
except ImportError:
    _APPKIT_AVAILABLE = False

from netpulse.utils.log import get_logger

logger = get_logger("mascot")


class MascotState(Enum):
    """Animation states for the lion mascot."""

    IDLE = "idle"
    LOW = "low"
    WALK = "walk"
    RUN = "run"
    ROAR = "roar"
    DISCONNECTED = "disconnected"
    RECONNECT = "reconnect"


@dataclass
class MascotSpeedThresholds:
    """Configurable bandwidth thresholds for mascot animation states."""

    idle_threshold_bps: float = 10 * 1024.0             # < 10 KB/s -> IDLE
    low_threshold_bps: float = 300 * 1024.0            # 10 - 300 KB/s -> LOW
    medium_threshold_bps: float = 2.0 * 1024.0 * 1024.0 # 300 KB/s - 2 MB/s -> WALK
    # > 2 MB/s -> RUN

    # Traffic spike detection
    spike_min_jump_bps: float = 1.5 * 1024.0 * 1024.0   # Minimum jump of 1.5 MB/s
    spike_ratio_multiplier: float = 3.0                 # AND current >= 3x previous
    roar_cooldown_seconds: float = 15.0                 # Minimum seconds between roars
    yawn_cooldown_seconds: float = 30.0                 # Minimum seconds between yawns
    yawn_cycle_interval: int = 50                       # Idle frame count before considering yawn


@dataclass
class MascotFrame:
    """Cached representation of a single animation frame."""

    state: MascotState
    index: int
    filepath: str
    image: QImage
    _pixmap: Optional[QPixmap] = None
    nsimage: Optional[Any] = None
    substate: Optional[str] = None

    @property
    def pixmap(self) -> QPixmap:
        if self._pixmap is None or self._pixmap.isNull():
            self._pixmap = QPixmap.fromImage(self.image)
        return self._pixmap


class MascotAssetLoader:
    """Loads and preloads animation frames from the resources directory.

    Decoupled from specific artwork: scans state directories for PNG files
    and pre-caches QPixmap and NSImage objects to avoid runtime decoding.
    """

    def __init__(self, mascot_dir: Optional[Path] = None) -> None:
        if mascot_dir is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self._mascot_dir = base_dir / "resources" / "mascot"
        else:
            self._mascot_dir = mascot_dir

        self._frames: Dict[MascotState, List[MascotFrame]] = {}
        self._idle_yawn_frames: List[MascotFrame] = []
        self._load_assets()

    @property
    def mascot_dir(self) -> Path:
        return self._mascot_dir

    def _load_assets(self) -> None:
        """Scan directory and preload all frames into memory."""
        for state in MascotState:
            state_dir = self._mascot_dir / state.value
            if not state_dir.exists():
                logger.warning("Mascot state directory not found: %s", state_dir)
                self._frames[state] = []
                continue

            png_files = sorted(
                [f for f in state_dir.glob("*.png") if not f.name.startswith(".")],
                key=lambda p: p.name,
            )

            frames: List[MascotFrame] = []
            for idx, p in enumerate(png_files):
                if state == MascotState.IDLE and p.name.startswith("yawn_"):
                    # Handled separately for infrequent yawn substate
                    continue

                frame = self._create_frame(p, state, idx)
                frames.append(frame)

            self._frames[state] = frames

        # Load yawn substate frames for idle
        idle_dir = self._mascot_dir / MascotState.IDLE.value
        if idle_dir.exists():
            yawn_files = sorted(
                [f for f in idle_dir.glob("yawn_*.png") if not f.name.startswith(".")],
                key=lambda p: p.name,
            )
            for idx, p in enumerate(yawn_files):
                frame = self._create_frame(p, MascotState.IDLE, idx, substate="yawn")
                self._idle_yawn_frames.append(frame)

        logger.debug(
            "Mascot assets loaded: %s states, %d idle frames, %d yawn frames",
            len(self._frames),
            len(self._frames.get(MascotState.IDLE, [])),
            len(self._idle_yawn_frames),
        )

    def _create_frame(
        self,
        path: Path,
        state: MascotState,
        index: int,
        substate: Optional[str] = None,
    ) -> MascotFrame:
        """Create and cache image and NSImage for a single frame."""
        image = QImage(str(path))
        pixmap = None
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is not None:
            pixmap = QPixmap.fromImage(image)

        nsimage = None
        if _APPKIT_AVAILABLE:
            try:
                # Create NSImage from file and configure for crisp Retina status bar (26.125x19 pt: lion occupies ~90% of menu bar height)
                nsimage = AppKit.NSImage.alloc().initByReferencingFile_(str(path))
                if nsimage:
                    nsimage.setSize_(AppKit.NSMakeSize(26.125, 19.0))
                    nsimage.setTemplate_(False)
            except Exception:
                logger.exception("Failed to create NSImage for %s", path)

        return MascotFrame(
            state=state,
            index=index,
            filepath=str(path),
            image=image,
            _pixmap=pixmap,
            nsimage=nsimage,
            substate=substate,
        )

    def get_frames(self, state: MascotState, substate: Optional[str] = None) -> List[MascotFrame]:
        """Return cached frames for a state and optional substate."""
        if state == MascotState.IDLE and substate == "yawn":
            return self._idle_yawn_frames
        return self._frames.get(state, [])


class LionMascotController(QObject):
    """Animation controller for the macOS menu-bar lion mascot.

    Responsibilities:
    - Preloads and caches animation frames
    - Manages animation states and transitions
    - Controls running animation speed dynamically
    - Detects traffic spikes and handles roar cooldown
    - Handles network connection / disconnection transitions
    - Advances frames using a low-CPU timer
    - Exposes current frame as NSImage, QPixmap, and QIcon
    """

    frame_changed = Signal(object)

    def __init__(
        self,
        enabled: bool = True,
        thresholds: Optional[MascotSpeedThresholds] = None,
        asset_loader: Optional[MascotAssetLoader] = None,
        on_frame_changed: Optional[Callable[[MascotFrame], None]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._enabled = enabled
        self._thresholds = thresholds or MascotSpeedThresholds()
        self._loader = asset_loader or MascotAssetLoader()
        self._on_frame_changed_cb = on_frame_changed

        self._state = MascotState.IDLE
        self._target_state = MascotState.IDLE
        self._substate: Optional[str] = None
        self._frame_index = 0

        self._is_connected = True
        self._activity_bps = 0.0
        self._prev_activity_bps = 0.0

        self._last_roar_time = -999.0
        self._last_yawn_time = -999.0
        self._idle_tick_count = 0
        self._is_playing_one_shot = False

        # Lightweight animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.advance_frame)

        # Initial frame
        self._current_frame: Optional[MascotFrame] = None
        self._select_current_frame()

        if self._enabled:
            self._start_timer_for_state(self._state)

    # ------------------------------------------------------------------
    # Public Properties
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def current_state(self) -> MascotState:
        return self._state

    @property
    def target_state(self) -> MascotState:
        return self._target_state

    @property
    def current_frame(self) -> Optional[MascotFrame]:
        return self._current_frame

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def thresholds(self) -> MascotSpeedThresholds:
        return self._thresholds

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the mascot animation."""
        if self._enabled == enabled:
            return

        self._enabled = enabled
        if not self._enabled:
            self._timer.stop()
            self._current_frame = None
            if self._on_frame_changed_cb:
                self._on_frame_changed_cb(None)
            self.frame_changed.emit(None)
        else:
            self._select_current_frame()
            self._start_timer_for_state(self._state)
            self._notify_frame()

    def update_speed(
        self,
        download_bps: float,
        upload_bps: float,
        now: Optional[float] = None,
    ) -> None:
        """Process latest bandwidth sample from NetworkMonitor / UIBridge.

        Combined activity determines the animation state and running speed.
        """
        if now is None:
            now = time.monotonic()

        activity = max(0.0, download_bps) + max(0.0, upload_bps)
        self._activity_bps = activity

        if not self._is_connected:
            self._target_state = MascotState.DISCONNECTED
            self._prev_activity_bps = activity
            return

        # 1. Map steady-state activity to target state
        if activity < self._thresholds.idle_threshold_bps:
            target = MascotState.IDLE
        elif activity < self._thresholds.low_threshold_bps:
            target = MascotState.LOW
        elif activity < self._thresholds.medium_threshold_bps:
            target = MascotState.WALK
        else:
            target = MascotState.RUN

        self._target_state = target

        # 2. Check for traffic spike / roar condition (sudden jump from prior non-zero traffic)
        is_spike = (
            self._prev_activity_bps > 0
            and activity >= self._thresholds.medium_threshold_bps
            and (activity - self._prev_activity_bps) >= self._thresholds.spike_min_jump_bps
            and activity >= (self._thresholds.spike_ratio_multiplier * max(self._prev_activity_bps, 100_000.0))
            and (now - self._last_roar_time) >= self._thresholds.roar_cooldown_seconds
        )

        if is_spike and not self._is_playing_one_shot:
            self._last_roar_time = now
            self._trigger_one_shot(MascotState.ROAR)
            self._prev_activity_bps = activity
            return

        self._prev_activity_bps = activity

        # If not playing a one-shot, update timer interval (e.g. running speed scaling)
        if not self._is_playing_one_shot and self._enabled:
            self._adjust_timer_interval()

    def update_connection(self, is_connected: bool) -> None:
        """Update connection status from NetworkContext."""
        was_connected = self._is_connected
        self._is_connected = is_connected

        if not is_connected:
            self._substate = None
            self._is_playing_one_shot = False
            self._target_state = MascotState.DISCONNECTED
            self._state = MascotState.DISCONNECTED
            self._frame_index = 0
            self._select_current_frame()
            if self._enabled:
                self._start_timer_for_state(MascotState.DISCONNECTED)
            self._notify_frame()
        elif not was_connected and is_connected:
            # Transition from disconnected to reconnected: trigger one-shot wake-up
            if self._activity_bps < self._thresholds.idle_threshold_bps:
                self._target_state = MascotState.IDLE
            elif self._activity_bps < self._thresholds.low_threshold_bps:
                self._target_state = MascotState.LOW
            elif self._activity_bps < self._thresholds.medium_threshold_bps:
                self._target_state = MascotState.WALK
            else:
                self._target_state = MascotState.RUN

            self._trigger_one_shot(MascotState.RECONNECT)

    def advance_frame(self, now: Optional[float] = None) -> None:
        """Step animation by one frame. Safe to call manually in unit tests."""
        if not self._enabled:
            return

        if now is None:
            now = time.monotonic()

        frames = self._loader.get_frames(self._state, self._substate)
        if not frames:
            return

        # Handling one-shot states (ROAR and RECONNECT)
        if self._is_playing_one_shot:
            self._frame_index += 1
            if self._frame_index >= len(frames):
                # Completed one-shot sequence: return to target state
                self._is_playing_one_shot = False
                self._state = self._target_state
                self._substate = None
                self._frame_index = 0
                self._start_timer_for_state(self._state)
            self._select_current_frame()
            self._notify_frame()
            return

        # Handling IDLE state (breathing, blinking, and infrequent yawning)
        if self._state == MascotState.IDLE:
            if self._substate == "yawn":
                self._frame_index += 1
                if self._frame_index >= len(frames):
                    # Finished yawning, return to normal idle loop
                    self._substate = None
                    self._frame_index = 0
                    self._idle_tick_count = 0
                    self._last_yawn_time = now
            else:
                self._frame_index = (self._frame_index + 1) % len(frames)
                self._idle_tick_count += 1

                # Check if it is time for an infrequent yawn
                if (
                    self._idle_tick_count >= self._thresholds.yawn_cycle_interval
                    and (now - self._last_yawn_time) >= self._thresholds.yawn_cooldown_seconds
                ):
                    yawn_frames = self._loader.get_frames(MascotState.IDLE, substate="yawn")
                    if yawn_frames:
                        self._substate = "yawn"
                        self._frame_index = 0

            # If speed increased away from IDLE, transition out smoothly
            if self._target_state != MascotState.IDLE and self._substate != "yawn":
                self._state = self._target_state
                self._substate = None
                self._frame_index = 0
                self._start_timer_for_state(self._state)

            self._select_current_frame()
            self._notify_frame()
            return

        # Normal states: LOW, WALK, RUN, DISCONNECTED
        if self._state != self._target_state:
            # Smooth transition on next tick
            self._state = self._target_state
            self._substate = None
            self._frame_index = 0
            self._start_timer_for_state(self._state)
        else:
            self._frame_index = (self._frame_index + 1) % len(frames)

        self._select_current_frame()
        self._notify_frame()

    def get_current_nsimage(self) -> Optional[Any]:
        """Return the pre-cached NSImage of the current frame (macOS only)."""
        if self._current_frame:
            return self._current_frame.nsimage
        return None

    def get_current_pixmap(self) -> Optional[QPixmap]:
        """Return the pre-cached QPixmap of the current frame."""
        if self._current_frame:
            return self._current_frame.pixmap
        return None

    def get_current_icon(self) -> Optional[QIcon]:
        """Return a QIcon for the current frame."""
        if self._current_frame and self._current_frame.pixmap:
            return QIcon(self._current_frame.pixmap)
        return None

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _trigger_one_shot(self, state: MascotState) -> None:
        """Trigger a non-looping one-shot animation (ROAR or RECONNECT)."""
        self._is_playing_one_shot = True
        self._state = state
        self._substate = None
        self._frame_index = 0
        self._select_current_frame()
        if self._enabled:
            self._start_timer_for_state(state)
        self._notify_frame()

    def _select_current_frame(self) -> None:
        frames = self._loader.get_frames(self._state, self._substate)
        if frames and 0 <= self._frame_index < len(frames):
            self._current_frame = frames[self._frame_index]
        elif frames:
            self._frame_index = 0
            self._current_frame = frames[0]
        else:
            self._current_frame = None

    def _notify_frame(self) -> None:
        if self._on_frame_changed_cb:
            self._on_frame_changed_cb(self._current_frame)
        self.frame_changed.emit(self._current_frame)

    def _start_timer_for_state(self, state: MascotState) -> None:
        interval_ms = self._compute_timer_interval(state)
        self._timer.start(interval_ms)

    def _adjust_timer_interval(self) -> None:
        interval_ms = self._compute_timer_interval(self._state)
        if self._timer.interval() != interval_ms:
            self._timer.setInterval(interval_ms)

    def _compute_timer_interval(self, state: MascotState) -> int:
        """Return timer interval in milliseconds for the given state.

        Low frame rates for idle/sleep to conserve CPU; running speed increases
        dynamically as traffic surges.
        """
        if state == MascotState.IDLE:
            return 400
        if state == MascotState.LOW:
            return 300
        if state == MascotState.WALK:
            return 160
        if state == MascotState.RUN:
            # Dynamic speed scaling: 2 MB/s ~ 130ms down to 50 MB/s+ ~ 55ms
            extra_mb = max(0.0, (self._activity_bps - self._thresholds.medium_threshold_bps) / 1_048_576.0)
            reduction = min(75.0, extra_mb * 2.5)
            return max(55, int(130 - reduction))
        if state == MascotState.ROAR:
            return 120
        if state == MascotState.DISCONNECTED:
            return 700
        if state == MascotState.RECONNECT:
            return 150
        return 250
