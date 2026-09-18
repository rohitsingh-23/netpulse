"""Lightweight, isolated update service.

Pure service with zero connection to NetworkMonitor, DataBuffer, SampleAggregator, or SQLite.
Provides local release notes and version comparisons.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from netpulse.updates.models import ReleaseFeature, ReleaseNote, UpdateStatus
from netpulse.utils.constants import APP_VERSION


def parse_version(v_str: str) -> Tuple[int, ...]:
    """Parse semver string into a comparable tuple of integers."""
    cleaned = re.sub(r"[^\d.]", "", v_str.strip())
    parts = []
    for p in cleaned.split("."):
        if p.isdigit():
            parts.append(int(p))
    return tuple(parts) if parts else (0,)


def compare_versions(current: str, candidate: str) -> int:
    """Compare two version strings.

    Returns:
        1 if candidate > current (newer version available)
        0 if candidate == current
        -1 if candidate < current
    """
    v_curr = parse_version(current)
    v_cand = parse_version(candidate)

    # Pad with zeros to equalize lengths
    max_len = max(len(v_curr), len(v_cand))
    v_curr_padded = v_curr + (0,) * (max_len - len(v_curr))
    v_cand_padded = v_cand + (0,) * (max_len - len(v_cand))

    if v_cand_padded > v_curr_padded:
        return 1
    elif v_cand_padded < v_curr_padded:
        return -1
    return 0


class UpdateService:
    """Provides release metadata and update checks."""

    def __init__(self, current_version: str = APP_VERSION) -> None:
        self._current_version = current_version

    @property
    def current_version(self) -> str:
        return self._current_version

    def get_local_releases(self) -> List[ReleaseNote]:
        """Return chronological release history for NetPulse based on confirmed features."""
        return [
            ReleaseNote(
                version="0.7.0",
                release_date="2026-09-18",
                summary="Current release with integrated speed testing, animated mascot, and native notifications.",
                features=[
                    ReleaseFeature(
                        "In-Dashboard Speed Test",
                        "Added Cloudflare Edge speed testing for download, upload, ping, and jitter directly inside the dashboard.",
                    ),
                    ReleaseFeature(
                        "Animated Menu-Bar Lion Mascot",
                        "Custom lightweight animated lion companion reflecting real-time network activity and connection states.",
                    ),
                    ReleaseFeature(
                        "Native macOS Notifications",
                        "UserNotifications.framework integration with per-event rate-limiting and hysteresis.",
                    ),
                    ReleaseFeature(
                        "Independent Scrollable Pages",
                        "Dedicated vertical scroll areas for all dashboard tabs ensuring layout integrity on small screens.",
                    ),
                    ReleaseFeature(
                        "Data & Reset Coordinator",
                        "Granular management to reset statistics while preserving user preferences, or perform full factory resets.",
                    ),
                ],
            ),
        ]

    def check_for_updates(
        self,
        api_url: Optional[str] = None,
        timeout: float = 6.0,
    ) -> Tuple[UpdateStatus, Optional[ReleaseNote], str]:
        """Check for updates using the GitHub Releases API.

        Performs a non-blocking request with standard library urllib.
        Does not transmit authentication, telemetry, or user/system info.
        """
        import json
        import urllib.error
        import urllib.request
        from netpulse.utils.constants import GITHUB_LATEST_RELEASE_API, GITHUB_LATEST_RELEASE_URL

        target_api = api_url or GITHUB_LATEST_RELEASE_API

        req = urllib.request.Request(
            target_api,
            headers={
                "User-Agent": f"NetPulse/{self._current_version}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
                release_data = json.loads(data)

            tag_name = release_data.get("tag_name", "").strip()
            if not tag_name:
                return (
                    UpdateStatus.ERROR,
                    None,
                    "Invalid release format received from update service.",
                )

            # Clean tag (e.g. "v1.0.0" -> "1.0.0")
            candidate_version = tag_name.lstrip("vV")
            name = release_data.get("name") or f"NetPulse {candidate_version}"
            body = release_data.get("body") or "No release notes provided."
            html_url = release_data.get("html_url") or GITHUB_LATEST_RELEASE_URL
            published_at = release_data.get("published_at", "")[:10]

            remote_note = ReleaseNote(
                version=candidate_version,
                release_date=published_at,
                summary=body,
                download_url=html_url,
            )

            cmp_result = compare_versions(self._current_version, candidate_version)
            if cmp_result > 0:
                return (
                    UpdateStatus.UPDATE_AVAILABLE,
                    remote_note,
                    f"A new version is available: v{candidate_version}",
                )
            else:
                return (
                    UpdateStatus.UP_TO_DATE,
                    remote_note,
                    "You're running the latest version.",
                )

        except urllib.error.HTTPError as err:
            if err.code == 404:
                return (
                    UpdateStatus.NOT_CONFIGURED,
                    None,
                    "Release information is not available yet.",
                )
            elif err.code in (403, 429):
                return (
                    UpdateStatus.ERROR,
                    None,
                    "GitHub API rate limit reached. Please try again later.",
                )
            elif 500 <= err.code < 600:
                return (
                    UpdateStatus.ERROR,
                    None,
                    "Update server temporarily unavailable. Please try again later.",
                )
            else:
                return (
                    UpdateStatus.ERROR,
                    None,
                    f"Unable to check for updates (HTTP {err.code}).",
                )

        except urllib.error.URLError as err:
            return (
                UpdateStatus.ERROR,
                None,
                "Unable to connect to the update service. Please check your internet connection.",
            )

        except json.JSONDecodeError:
            return (
                UpdateStatus.ERROR,
                None,
                "Received malformed response from update service.",
            )

        except Exception as exc:
            return (
                UpdateStatus.ERROR,
                None,
                "Unable to check for updates. Please try again later.",
            )
