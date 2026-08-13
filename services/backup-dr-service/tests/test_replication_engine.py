"""Tests for app.replication.engine: lag classification and bandwidth allocation."""

from __future__ import annotations

import pytest

from app.models.enums import ReplicationStatus
from app.replication.engine import LagSeverity, allocate_bandwidth, assess_lag

WARNING = 300.0
CRITICAL = 1_800.0


class TestAssessLag:
    def test_none_lag_is_syncing_never_healthy_or_lagging(self) -> None:
        result = assess_lag(
            None, warning_threshold_seconds=WARNING, critical_threshold_seconds=CRITICAL
        )
        assert result.status is ReplicationStatus.SYNCING
        assert result.severity == LagSeverity.WARNING
        assert result.lag_seconds is None

    def test_below_warning_is_healthy(self) -> None:
        result = assess_lag(
            10.0, warning_threshold_seconds=WARNING, critical_threshold_seconds=CRITICAL
        )
        assert result.status is ReplicationStatus.IN_SYNC
        assert result.severity == LagSeverity.HEALTHY

    def test_at_warning_threshold_is_warning(self) -> None:
        result = assess_lag(
            WARNING, warning_threshold_seconds=WARNING, critical_threshold_seconds=CRITICAL
        )
        assert result.status is ReplicationStatus.LAGGING
        assert result.severity == LagSeverity.WARNING

    def test_between_warning_and_critical_is_warning(self) -> None:
        result = assess_lag(
            600.0, warning_threshold_seconds=WARNING, critical_threshold_seconds=CRITICAL
        )
        assert result.status is ReplicationStatus.LAGGING

    def test_at_critical_threshold_is_critical(self) -> None:
        result = assess_lag(
            CRITICAL, warning_threshold_seconds=WARNING, critical_threshold_seconds=CRITICAL
        )
        assert result.status is ReplicationStatus.STALLED
        assert result.severity == LagSeverity.CRITICAL

    def test_above_critical_is_critical(self) -> None:
        result = assess_lag(
            5_000.0, warning_threshold_seconds=WARNING, critical_threshold_seconds=CRITICAL
        )
        assert result.status is ReplicationStatus.STALLED

    def test_invalid_threshold_ordering_raises(self) -> None:
        with pytest.raises(ValueError, match="must exceed"):
            assess_lag(10.0, warning_threshold_seconds=100.0, critical_threshold_seconds=100.0)

    def test_critical_below_warning_raises(self) -> None:
        with pytest.raises(ValueError, match="must exceed"):
            assess_lag(10.0, warning_threshold_seconds=200.0, critical_threshold_seconds=100.0)


class TestAllocateBandwidth:
    def test_even_split(self) -> None:
        result = allocate_bandwidth(100.0, 4)
        assert result.per_job_mbps == 25.0
        assert result.job_count == 4
        assert result.total_mbps == 100.0

    def test_single_job_gets_full_budget(self) -> None:
        result = allocate_bandwidth(50.0, 1)
        assert result.per_job_mbps == 50.0

    def test_zero_total_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            allocate_bandwidth(0.0, 1)

    def test_negative_total_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            allocate_bandwidth(-10.0, 1)

    def test_zero_jobs_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            allocate_bandwidth(100.0, 0)
