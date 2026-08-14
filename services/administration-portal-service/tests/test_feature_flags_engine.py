"""Tests for app.feature_flags.engine: kill switch, schedule window,
deterministic rollout bucketing, and version constraints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.feature_flags.engine import (
    bucket_fraction,
    is_flag_enabled_for_target,
    is_within_schedule,
    satisfies_version_constraint,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestBucketFraction:
    def test_is_deterministic(self) -> None:
        assert bucket_fraction("tenant-1", flag_name="new-ui") == bucket_fraction(
            "tenant-1", flag_name="new-ui"
        )

    def test_differs_across_flags(self) -> None:
        a = bucket_fraction("tenant-1", flag_name="flag-a")
        b = bucket_fraction("tenant-1", flag_name="flag-b")
        assert a != b

    def test_within_range(self) -> None:
        for target in ("tenant-1", "tenant-2", "tenant-3", None):
            fraction = bucket_fraction(target, flag_name="new-ui")
            assert 0.0 <= fraction < 100.0

    def test_none_target_uses_fixed_key(self) -> None:
        assert bucket_fraction(None, flag_name="new-ui") == bucket_fraction(
            None, flag_name="new-ui"
        )


class TestIsWithinSchedule:
    def test_no_bounds_is_within(self) -> None:
        assert is_within_schedule(now=NOW, starts_at=None, ends_at=None)

    def test_before_start_is_not_within(self) -> None:
        assert not is_within_schedule(now=NOW, starts_at=NOW + timedelta(days=1), ends_at=None)

    def test_after_end_is_not_within(self) -> None:
        assert not is_within_schedule(now=NOW, starts_at=None, ends_at=NOW - timedelta(days=1))

    def test_within_bounds_is_within(self) -> None:
        assert is_within_schedule(
            now=NOW, starts_at=NOW - timedelta(days=1), ends_at=NOW + timedelta(days=1)
        )


class TestSatisfiesVersionConstraint:
    def test_none_current_version_always_satisfies(self) -> None:
        assert satisfies_version_constraint(None, min_version="1.0.0", max_version="2.0.0")

    def test_within_bounds(self) -> None:
        assert satisfies_version_constraint("1.5.0", min_version="1.0.0", max_version="2.0.0")

    def test_below_minimum_fails(self) -> None:
        assert not satisfies_version_constraint("0.9.0", min_version="1.0.0", max_version=None)

    def test_above_maximum_fails(self) -> None:
        assert not satisfies_version_constraint("2.1.0", min_version=None, max_version="2.0.0")

    def test_no_bounds_always_satisfies(self) -> None:
        assert satisfies_version_constraint("9.9.9", min_version=None, max_version=None)


class TestIsFlagEnabledForTarget:
    def test_killed_flag_is_always_disabled(self) -> None:
        assert not is_flag_enabled_for_target(
            is_enabled=True,
            is_killed=True,
            rollout_percentage=100.0,
            starts_at=None,
            ends_at=None,
            now=NOW,
            target_ref="t1",
            flag_name="x",
        )

    def test_disabled_flag_is_disabled(self) -> None:
        assert not is_flag_enabled_for_target(
            is_enabled=False,
            is_killed=False,
            rollout_percentage=100.0,
            starts_at=None,
            ends_at=None,
            now=NOW,
            target_ref="t1",
            flag_name="x",
        )

    def test_full_rollout_is_enabled(self) -> None:
        assert is_flag_enabled_for_target(
            is_enabled=True,
            is_killed=False,
            rollout_percentage=100.0,
            starts_at=None,
            ends_at=None,
            now=NOW,
            target_ref="t1",
            flag_name="x",
        )

    def test_zero_rollout_is_disabled(self) -> None:
        assert not is_flag_enabled_for_target(
            is_enabled=True,
            is_killed=False,
            rollout_percentage=0.0,
            starts_at=None,
            ends_at=None,
            now=NOW,
            target_ref="t1",
            flag_name="x",
        )

    def test_outside_schedule_is_disabled(self) -> None:
        assert not is_flag_enabled_for_target(
            is_enabled=True,
            is_killed=False,
            rollout_percentage=100.0,
            starts_at=NOW + timedelta(days=1),
            ends_at=None,
            now=NOW,
            target_ref="t1",
            flag_name="x",
        )

    def test_version_constraint_excludes_caller(self) -> None:
        assert not is_flag_enabled_for_target(
            is_enabled=True,
            is_killed=False,
            rollout_percentage=100.0,
            starts_at=None,
            ends_at=None,
            now=NOW,
            target_ref="t1",
            flag_name="x",
            current_version="0.5.0",
            min_version="1.0.0",
            max_version=None,
        )
