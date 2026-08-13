"""Tests for app.retention.engine -- retention planning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import SignalKind
from app.retention.engine import (
    RetentionPolicySpec,
    RetentionRefusal,
    compute_cutoffs,
    plan_retention,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)
EPOCH = datetime(2020, 1, 1, tzinfo=UTC)


def _policy(**overrides: object) -> RetentionPolicySpec:
    defaults: dict[str, object] = {
        "signal_kind": SignalKind.METRIC,
        "environment": "production",
        "raw_days": 7,
        "downsampled_days": 30,
        "coarse_days": 395,
        "downsample_interval": timedelta(minutes=5),
    }
    defaults.update(overrides)
    return RetentionPolicySpec(**defaults)  # type: ignore[arg-type]


class TestRetentionPolicySpec:
    def test_inverted_tiers_raises(self) -> None:
        with pytest.raises(ValueError, match="non-decreasing"):
            _policy(raw_days=30, downsampled_days=7, coarse_days=395)

    def test_non_positive_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="downsample_interval"):
            _policy(downsample_interval=timedelta(0))

    def test_valid_policy(self) -> None:
        policy = _policy()
        assert policy.is_enabled


class TestComputeCutoffs:
    def test_naive_now_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            compute_cutoffs(_policy(), now=datetime(2026, 1, 1))

    def test_computes_three_cutoffs(self) -> None:
        cutoffs = compute_cutoffs(_policy(), now=NOW)
        assert cutoffs.raw_cutoff == NOW - timedelta(days=7)
        assert cutoffs.downsampled_cutoff == NOW - timedelta(days=30)
        assert cutoffs.coarse_cutoff == NOW - timedelta(days=395)


class TestPlanRetention:
    def test_disabled_policy_refuses(self) -> None:
        plan = plan_retention(
            _policy(is_enabled=False),
            now=NOW,
            epoch=EPOCH,
            raw_downsampled_watermark=None,
            downsampled_coarsened_watermark=None,
        )
        assert plan.refused == RetentionRefusal.DISABLED
        assert plan.is_noop
        assert plan.cutoffs is None

    def test_no_watermark_refuses_raw_delete_but_downsamples(self) -> None:
        plan = plan_retention(
            _policy(),
            now=NOW,
            epoch=EPOCH,
            raw_downsampled_watermark=None,
            downsampled_coarsened_watermark=None,
        )
        assert plan.refused is None
        assert len(plan.downsample_actions) == 1
        raw_deletes = [a for a in plan.delete_actions if a.resolution == "raw"]
        assert raw_deletes == []  # no watermark => no raw deletion authorized

    def test_watermark_authorizes_raw_delete_up_to_watermark(self) -> None:
        watermark = NOW - timedelta(days=10)  # older than raw_cutoff (7d)
        plan = plan_retention(
            _policy(),
            now=NOW,
            epoch=EPOCH,
            raw_downsampled_watermark=watermark,
            downsampled_coarsened_watermark=None,
        )
        raw_deletes = [a for a in plan.delete_actions if a.resolution == "raw"]
        assert len(raw_deletes) == 1
        assert raw_deletes[0].older_than == min(NOW - timedelta(days=7), watermark)

    def test_watermark_ahead_of_cutoff_bounds_at_cutoff(self) -> None:
        # Watermark is more recent than raw_cutoff: bound is the cutoff.
        watermark = NOW - timedelta(days=1)
        plan = plan_retention(
            _policy(),
            now=NOW,
            epoch=EPOCH,
            raw_downsampled_watermark=watermark,
            downsampled_coarsened_watermark=None,
        )
        raw_deletes = [a for a in plan.delete_actions if a.resolution == "raw"]
        assert len(raw_deletes) == 1
        assert raw_deletes[0].older_than == NOW - timedelta(days=7)

    def test_downsampled_delete_authorized_by_coarsened_watermark(self) -> None:
        watermark = NOW - timedelta(days=40)
        plan = plan_retention(
            _policy(),
            now=NOW,
            epoch=EPOCH,
            raw_downsampled_watermark=NOW - timedelta(days=10),
            downsampled_coarsened_watermark=watermark,
        )
        downsampled_deletes = [a for a in plan.delete_actions if a.resolution == "downsampled"]
        assert len(downsampled_deletes) == 1

    def test_coarse_delete_always_authorized_when_past_epoch(self) -> None:
        plan = plan_retention(
            _policy(),
            now=NOW,
            epoch=EPOCH,
            raw_downsampled_watermark=None,
            downsampled_coarsened_watermark=None,
        )
        coarse_deletes = [a for a in plan.delete_actions if a.resolution == "coarse"]
        assert len(coarse_deletes) == 1
        assert coarse_deletes[0].older_than == NOW - timedelta(days=395)

    def test_no_downsample_action_when_already_caught_up(self) -> None:
        # Watermark already at (or past) the aligned raw cutoff.
        watermark = NOW
        plan = plan_retention(
            _policy(),
            now=NOW,
            epoch=EPOCH,
            raw_downsampled_watermark=watermark,
            downsampled_coarsened_watermark=None,
        )
        assert plan.downsample_actions == ()

    def test_recent_now_near_epoch_produces_noop(self) -> None:
        near_epoch = EPOCH + timedelta(hours=1)
        plan = plan_retention(
            _policy(),
            now=near_epoch,
            epoch=EPOCH,
            raw_downsampled_watermark=None,
            downsampled_coarsened_watermark=None,
        )
        assert plan.is_noop
