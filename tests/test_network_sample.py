"""Tests for NetworkSample dataclass."""

from datetime import datetime, timezone

import pytest

from netpulse.core.network_sample import NetworkSample


class TestNetworkSampleConstruction:
    """Basic construction and field access."""

    def test_valid_construction(self) -> None:
        ts = datetime.now(timezone.utc)
        s = NetworkSample(
            timestamp=ts,
            download_bps=1000.0,
            upload_bps=500.0,
            total_download_bytes=1_000_000,
            total_upload_bytes=500_000,
        )
        assert s.download_bps == 1000.0
        assert s.upload_bps == 500.0
        assert s.total_download_bytes == 1_000_000
        assert s.total_upload_bytes == 500_000
        assert s.interface is None

    def test_with_interface(self) -> None:
        s = NetworkSample(
            timestamp=datetime.now(timezone.utc),
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=0,
            total_upload_bytes=0,
            interface="en0",
        )
        assert s.interface == "en0"

    def test_zero_speeds(self) -> None:
        s = NetworkSample(
            timestamp=datetime.now(timezone.utc),
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=0,
            total_upload_bytes=0,
        )
        assert s.download_bps == 0.0
        assert s.upload_bps == 0.0


class TestNetworkSampleValidation:
    """Validation and clamping behavior."""

    def test_negative_download_clamped_to_zero(self) -> None:
        s = NetworkSample(
            timestamp=datetime.now(timezone.utc),
            download_bps=-100.0,
            upload_bps=50.0,
            total_download_bytes=0,
            total_upload_bytes=0,
        )
        assert s.download_bps == 0.0

    def test_negative_upload_clamped_to_zero(self) -> None:
        s = NetworkSample(
            timestamp=datetime.now(timezone.utc),
            download_bps=50.0,
            upload_bps=-100.0,
            total_download_bytes=0,
            total_upload_bytes=0,
        )
        assert s.upload_bps == 0.0

    def test_both_negative_clamped(self) -> None:
        s = NetworkSample(
            timestamp=datetime.now(timezone.utc),
            download_bps=-1.0,
            upload_bps=-1.0,
            total_download_bytes=0,
            total_upload_bytes=0,
        )
        assert s.download_bps == 0.0
        assert s.upload_bps == 0.0


class TestNetworkSampleTimestamp:
    """Timestamp timezone handling."""

    def test_naive_timestamp_promoted_to_utc(self) -> None:
        naive = datetime(2024, 1, 1, 12, 0, 0)
        s = NetworkSample(
            timestamp=naive,
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=0,
            total_upload_bytes=0,
        )
        assert s.timestamp.tzinfo is not None
        assert s.timestamp.tzinfo == timezone.utc

    def test_aware_timestamp_preserved(self) -> None:
        aware = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        s = NetworkSample(
            timestamp=aware,
            download_bps=0.0,
            upload_bps=0.0,
            total_download_bytes=0,
            total_upload_bytes=0,
        )
        assert s.timestamp == aware


class TestNetworkSampleImmutability:
    """Frozen dataclass should reject attribute assignment."""

    def test_frozen(self) -> None:
        s = NetworkSample(
            timestamp=datetime.now(timezone.utc),
            download_bps=100.0,
            upload_bps=50.0,
            total_download_bytes=0,
            total_upload_bytes=0,
        )
        with pytest.raises(AttributeError):
            s.download_bps = 200.0  # type: ignore[misc]
