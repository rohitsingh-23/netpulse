"""Data models for software updates and release notes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class UpdateStatus(Enum):
    """Status of an update check."""

    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    CHECKING = "checking"
    ERROR = "error"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class ReleaseFeature:
    """A single feature or enhancement in a release."""

    title: str
    description: str


@dataclass(frozen=True)
class ReleaseNote:
    """Release note metadata for a given application version."""

    version: str
    release_date: str
    summary: str
    features: List[ReleaseFeature] = field(default_factory=list)
    download_url: Optional[str] = None
