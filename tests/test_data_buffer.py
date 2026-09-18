"""Tests for DataBuffer."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from netpulse.core.data_buffer import DataBuffer
from netpulse.core.network_sample import NetworkSample


def _sample(
    ts: Optional[datetime] = None,
    dl: float = 0.0,
    ul: float = 0.0,
) -> NetworkSample:
    """Helper to create a sample with minimal boilerplate."""
    if ts is None:
        ts = datetime.now(timezone.utc)
    return NetworkSample(
        timestamp=ts,
        download_bps=dl,
        upload_bps=ul,
        total_download_bytes=0,
        total_upload_bytes=0,
    )


class TestEmptyBuffer:
    def test_empty_length(self) -> None:
        buf = DataBuffer(max_duration=60)
        assert len(buf) == 0

    def test_empty_latest(self) -> None:
        buf = DataBuffer(max_duration=60)
        assert buf.latest() is None

    def test_empty_get_samples(self) -> None:
        buf = DataBuffer(max_duration=60)
        assert buf.get_samples() == []


class TestAppendAndAccess:
    def test_append_single(self) -> None:
        buf = DataBuffer(max_duration=60)
        s = _sample(dl=100.0)
        buf.append(s)
        assert len(buf) == 1
        assert buf.latest() is s

    def test_append_multiple(self) -> None:
        buf = DataBuffer(max_duration=60)
        samples = [_sample(dl=float(i)) for i in range(5)]
        for s in samples:
            buf.append(s)
        assert len(buf) == 5
        assert buf.get_samples() == samples
        assert buf.latest() is samples[-1]

    def test_get_samples_returns_copy(self) -> None:
        buf = DataBuffer(max_duration=60)
        buf.append(_sample())
        s1 = buf.get_samples()
        s2 = buf.get_samples()
        assert s1 == s2
        assert s1 is not s2


class TestTimeBasedEviction:
    def test_old_samples_evicted(self) -> None:
        buf = DataBuffer(max_duration=2)
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=5)
        buf.append(_sample(ts=old_ts, dl=1.0))
        buf.append(_sample(dl=2.0))
        samples = buf.get_samples()
        assert len(samples) == 1
        assert samples[0].download_bps == 2.0

    def test_all_samples_evicted(self) -> None:
        buf = DataBuffer(max_duration=1)
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=5)
        buf.append(_sample(ts=old_ts))
        assert buf.get_samples() == []

    def test_recent_samples_kept(self) -> None:
        buf = DataBuffer(max_duration=60)
        samples = [_sample(dl=float(i)) for i in range(3)]
        for s in samples:
            buf.append(s)
        assert len(buf.get_samples()) == 3


class TestClear:
    def test_clear_empties_buffer(self) -> None:
        buf = DataBuffer(max_duration=60)
        for i in range(3):
            buf.append(_sample(dl=float(i)))
        buf.clear()
        assert len(buf) == 0
        assert buf.latest() is None
        assert buf.get_samples() == []


class TestMaxDuration:
    def test_max_duration_property(self) -> None:
        buf = DataBuffer(max_duration=120)
        assert buf.max_duration == 120


class TestThreadSafety:
    def test_concurrent_append_and_read(self) -> None:
        buf = DataBuffer(max_duration=60)
        errors: list[Exception] = []

        def writer() -> None:
            try:
                for i in range(100):
                    buf.append(_sample(dl=float(i)))
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for _ in range(100):
                    buf.get_samples()
                    buf.latest()
                    len(buf)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread safety errors: {errors}"
