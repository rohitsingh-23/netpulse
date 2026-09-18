"""Tests for SpeedCalculator.

Covers normal calculation, counter resets, sleep/wake gaps,
zero/negative elapsed, zero traffic, and custom max_measurement_gap.
"""

import pytest

from netpulse.core.speed_calculator import CounterSnapshot, SpeedCalculator


class TestNormalCalculation:
    """Standard speed calculations with valid inputs."""

    def setup_method(self) -> None:
        self.calc = SpeedCalculator(max_measurement_gap=10.0)

    def test_one_second_interval(self) -> None:
        prev = CounterSnapshot(100.0, bytes_received=1_000_000, bytes_sent=500_000)
        curr = CounterSnapshot(101.0, bytes_received=2_000_000, bytes_sent=700_000)
        result = self.calc.calculate(prev, curr)
        assert result is not None
        assert result.download_bps == 1_000_000.0
        assert result.upload_bps == 200_000.0
        assert result.elapsed == 1.0

    def test_two_second_interval(self) -> None:
        prev = CounterSnapshot(100.0, 1_000_000, 500_000)
        curr = CounterSnapshot(102.0, 3_000_000, 900_000)
        result = self.calc.calculate(prev, curr)
        assert result is not None
        assert result.download_bps == 1_000_000.0
        assert result.upload_bps == 200_000.0
        assert result.elapsed == 2.0

    def test_fractional_interval(self) -> None:
        prev = CounterSnapshot(100.0, 0, 0)
        curr = CounterSnapshot(100.5, 512, 256)
        result = self.calc.calculate(prev, curr)
        assert result is not None
        assert result.download_bps == pytest.approx(1024.0)
        assert result.upload_bps == pytest.approx(512.0)

    def test_large_traffic(self) -> None:
        prev = CounterSnapshot(100.0, 0, 0)
        curr = CounterSnapshot(101.0, 1_073_741_824, 536_870_912)  # 1 GB / 512 MB
        result = self.calc.calculate(prev, curr)
        assert result is not None
        assert result.download_bps == pytest.approx(1_073_741_824.0)


class TestZeroTraffic:
    """No network activity should produce zero speeds, not None."""

    def test_zero_traffic(self) -> None:
        calc = SpeedCalculator(max_measurement_gap=10.0)
        prev = CounterSnapshot(100.0, 1_000_000, 500_000)
        curr = CounterSnapshot(101.0, 1_000_000, 500_000)
        result = calc.calculate(prev, curr)
        assert result is not None
        assert result.download_bps == 0.0
        assert result.upload_bps == 0.0


class TestElapsedEdgeCases:
    """Zero and negative elapsed time."""

    def setup_method(self) -> None:
        self.calc = SpeedCalculator(max_measurement_gap=10.0)

    def test_zero_elapsed_returns_none(self) -> None:
        prev = CounterSnapshot(100.0, 1000, 500)
        curr = CounterSnapshot(100.0, 2000, 600)
        assert self.calc.calculate(prev, curr) is None

    def test_negative_elapsed_returns_none(self) -> None:
        prev = CounterSnapshot(101.0, 1000, 500)
        curr = CounterSnapshot(100.0, 2000, 600)
        assert self.calc.calculate(prev, curr) is None


class TestCounterReset:
    """Counter resets must return None (no false traffic spike)."""

    def setup_method(self) -> None:
        self.calc = SpeedCalculator(max_measurement_gap=10.0)

    def test_download_counter_reset(self) -> None:
        prev = CounterSnapshot(100.0, 10_000_000, 500_000)
        curr = CounterSnapshot(101.0, 1_000, 600_000)
        assert self.calc.calculate(prev, curr) is None

    def test_upload_counter_reset(self) -> None:
        prev = CounterSnapshot(100.0, 1_000_000, 10_000_000)
        curr = CounterSnapshot(101.0, 2_000_000, 1_000)
        assert self.calc.calculate(prev, curr) is None

    def test_both_counters_reset(self) -> None:
        prev = CounterSnapshot(100.0, 10_000_000, 10_000_000)
        curr = CounterSnapshot(101.0, 100, 100)
        assert self.calc.calculate(prev, curr) is None


class TestSleepWake:
    """Large time gaps should be discarded to avoid misleading averages."""

    def setup_method(self) -> None:
        self.calc = SpeedCalculator(max_measurement_gap=10.0)

    def test_large_gap_returns_none(self) -> None:
        prev = CounterSnapshot(100.0, 1_000_000, 500_000)
        curr = CounterSnapshot(200.0, 2_000_000, 600_000)  # 100s gap
        assert self.calc.calculate(prev, curr) is None

    def test_gap_just_over_threshold(self) -> None:
        prev = CounterSnapshot(100.0, 1000, 500)
        curr = CounterSnapshot(110.1, 2000, 600)  # 10.1s > 10s
        assert self.calc.calculate(prev, curr) is None

    def test_gap_just_under_threshold(self) -> None:
        prev = CounterSnapshot(100.0, 1000, 500)
        curr = CounterSnapshot(109.9, 2000, 600)  # 9.9s < 10s
        result = self.calc.calculate(prev, curr)
        assert result is not None

    def test_gap_at_exact_threshold(self) -> None:
        """Exactly at max_measurement_gap — still valid (not > threshold)."""
        prev = CounterSnapshot(100.0, 1000, 500)
        curr = CounterSnapshot(110.0, 2000, 600)
        result = self.calc.calculate(prev, curr)
        assert result is not None


class TestCustomMaxGap:
    """Custom max_measurement_gap configuration."""

    def test_smaller_custom_gap(self) -> None:
        calc = SpeedCalculator(max_measurement_gap=5.0)
        prev = CounterSnapshot(100.0, 1000, 500)
        curr = CounterSnapshot(106.0, 2000, 600)
        assert calc.calculate(prev, curr) is None

    def test_larger_custom_gap(self) -> None:
        calc = SpeedCalculator(max_measurement_gap=60.0)
        prev = CounterSnapshot(100.0, 1000, 500)
        curr = CounterSnapshot(150.0, 2000, 600)  # 50s < 60s
        result = calc.calculate(prev, curr)
        assert result is not None
