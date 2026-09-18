"""Data models for internet speed test results and execution state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SpeedTestStage(Enum):
    """Stages of an internet speed test execution."""

    IDLE = "idle"
    FINDING_SERVER = "finding_server"
    TESTING_LATENCY = "testing_latency"
    TESTING_DOWNLOAD = "testing_download"
    TESTING_UPLOAD = "testing_upload"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class SpeedTestProgress:
    """Real-time progress update emitted during a speed test."""

    stage: SpeedTestStage
    message: str
    current_speed_mbps: Optional[float] = None
    percent: float = 0.0  # 0.0 to 1.0


@dataclass
class SpeedTestResult:
    """Final summary of a completed internet speed test."""

    timestamp: datetime
    download_mbps: float
    upload_mbps: float
    latency_ms: float
    jitter_ms: float
    packet_loss_pct: Optional[float] = None  # None if unavailable
    server_location: str = "Cloudflare Edge"
