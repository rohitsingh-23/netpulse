"""Application-wide constants for NetPulse.

Centralizes magic numbers and default configuration values.
"""

from typing import List

APP_NAME: str = "NetPulse"
APP_VERSION: str = "0.7.0"
APP_BUNDLE_ID: str = "com.netpulse.app"

# Repository & Support Metadata
GITHUB_REPOSITORY_URL: str = "https://github.com/rohitsingh-23/netpulse"
GITHUB_RELEASES_URL: str = "https://github.com/rohitsingh-23/netpulse/releases"
GITHUB_LATEST_RELEASE_URL: str = "https://github.com/rohitsingh-23/netpulse/releases/latest"
GITHUB_LATEST_RELEASE_API: str = "https://api.github.com/repos/rohitsingh-23/netpulse/releases/latest"
GITHUB_ISSUES_URL: str = "https://github.com/rohitsingh-23/netpulse/issues"
SUPPORT_EMAIL: str = "rohit23498@gmail.com"


# Python version target
PYTHON_MIN_VERSION: str = "3.9"

# Network monitoring
DEFAULT_SAMPLE_INTERVAL: float = 1.0  # seconds between samples
MAX_MEASUREMENT_GAP: float = 10.0  # seconds — skip speed calc if gap exceeds this

# Time to keep data in memory (in seconds).
# Phase 3 requires up to 1 hour (3600 seconds) for the network graph.
DEFAULT_BUFFER_DURATION: int = 3600

# Formatting — binary units (1 KB = 1024 bytes)
BINARY_UNITS: List[str] = ["B", "KB", "MB", "GB", "TB"]
BYTES_PER_UNIT: int = 1024

# Storage & Persistence
DB_NAME: str = "netpulse.db"
STORAGE_FLUSH_INTERVAL: float = 60.0  # seconds between database batch writes
