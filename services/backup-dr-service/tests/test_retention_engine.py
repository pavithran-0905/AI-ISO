"""Tests for app.retention.engine: policy validation, deletability, sweep planning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import ImmutabilityState, RetentionTier
from app.retention.engine import (
    ArchiveRecord,
    RetentionPolicySpec,
    RetentionVeto,
    is_deletable,
    plan_retention,
)

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _archive(
    archive_id: str,
    archived_at: datetime,
    *,
    tier: RetentionTier = RetentionTier.HOT,
    immutability_state: ImmutabilityState = ImmutabilityState.NONE,
    retention_lock_until: datetime | None = None,
    legal_hold: bool = False,
) -> ArchiveRecord:
    return ArchiveRecord(
        archive_id=archive_id,
        archived_at=archived_at,
        tier=tier,
        immutability_state=immutability_state,
        retention_lock_until=retention_lock_until,
        legal_hold=legal_hold,
    )


class TestRetentionPolicySpec:
    def test_valid_policy(self) -> None:
        spec = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        assert spec.retention_days == 90

    def test_archive_after_equal_retention_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly before"):
            RetentionPolicySpec(retention_days=30, archive_after_days=30)

    def test_archive_after_greater_than_retention_raises(self) -> None:
        with pytest.raises(ValueError, match="strictly before"):
            RetentionPolicySpec(retention_days=30, archive_after_days=60)


class TestIsDeletable:
    def test_no_blockers_is_deletable(self) -> None:
        archive = _archive("a1", NOW)
        deletable, reason = is_deletable(archive, now=NOW)
        assert deletable
        assert reason is None

    def test_legal_hold_blocks_unconditionally(self) -> None:
        archive = _archive("a1", NOW, legal_hold=True)
        deletable, reason = is_deletable(archive, now=NOW)
        assert not deletable
        assert reason == RetentionVeto.LEGAL_HOLD

    def test_legal_hold_outranks_expired_lock(self) -> None:
        archive = _archive(
            "a1",
            NOW,
            legal_hold=True,
            retention_lock_until=NOW - timedelta(days=1),
        )
        deletable, reason = is_deletable(archive, now=NOW)
        assert not deletable
        assert reason == RetentionVeto.LEGAL_HOLD

    def test_active_retention_lock_blocks(self) -> None:
        archive = _archive("a1", NOW, retention_lock_until=NOW + timedelta(days=1))
        deletable, reason = is_deletable(archive, now=NOW)
        assert not deletable
        assert reason == RetentionVeto.RETENTION_LOCKED

    def test_expired_retention_lock_does_not_block(self) -> None:
        archive = _archive("a1", NOW, retention_lock_until=NOW - timedelta(days=1))
        deletable, _reason = is_deletable(archive, now=NOW)
        assert deletable

    def test_lock_expiring_exactly_now_does_not_block(self) -> None:
        archive = _archive("a1", NOW, retention_lock_until=NOW)
        deletable, _reason = is_deletable(archive, now=NOW)
        assert deletable


class TestPlanRetention:
    def test_disabled_policy_is_noop(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30, is_enabled=False)
        plan = plan_retention(policy, [_archive("a1", NOW - timedelta(days=200))], now=NOW)
        assert plan.is_noop
        assert plan.refused == "disabled"

    def test_young_archive_untouched(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        plan = plan_retention(policy, [_archive("a1", NOW - timedelta(days=1))], now=NOW)
        assert plan.is_noop
        assert plan.vetoed == ()

    def test_archive_past_archive_after_days_tiers_to_archive(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        archive = _archive("a1", NOW - timedelta(days=40), tier=RetentionTier.HOT)
        plan = plan_retention(policy, [archive], now=NOW)
        assert len(plan.tier_actions) == 1
        assert plan.tier_actions[0].to_tier == RetentionTier.ARCHIVE
        assert plan.delete_actions == ()

    def test_non_hot_tier_past_archive_cutoff_not_re_tiered(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        archive = _archive("a1", NOW - timedelta(days=40), tier=RetentionTier.ARCHIVE)
        plan = plan_retention(policy, [archive], now=NOW)
        assert plan.tier_actions == ()

    def test_archive_past_retention_days_deleted(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        archive = _archive("a1", NOW - timedelta(days=100))
        plan = plan_retention(policy, [archive], now=NOW)
        assert len(plan.delete_actions) == 1
        assert plan.delete_actions[0].archive_id == "a1"

    def test_deletable_archive_not_also_tiered(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        archive = _archive("a1", NOW - timedelta(days=100))
        plan = plan_retention(policy, [archive], now=NOW)
        assert plan.tier_actions == ()

    def test_legal_hold_vetoes_deletion(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        archive = _archive("a1", NOW - timedelta(days=100), legal_hold=True)
        plan = plan_retention(policy, [archive], now=NOW)
        assert plan.delete_actions == ()
        assert len(plan.vetoed) == 1
        assert plan.vetoed[0].reason == RetentionVeto.LEGAL_HOLD

    def test_retention_lock_vetoes_deletion(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        archive = _archive(
            "a1", NOW - timedelta(days=100), retention_lock_until=NOW + timedelta(days=10)
        )
        plan = plan_retention(policy, [archive], now=NOW)
        assert plan.delete_actions == ()
        assert len(plan.vetoed) == 1
        assert plan.vetoed[0].reason == RetentionVeto.RETENTION_LOCKED

    def test_mixed_batch(self) -> None:
        policy = RetentionPolicySpec(retention_days=90, archive_after_days=30)
        archives = [
            _archive("young", NOW - timedelta(days=1)),
            _archive("to-archive", NOW - timedelta(days=40)),
            _archive("to-delete", NOW - timedelta(days=100)),
            _archive("vetoed", NOW - timedelta(days=100), legal_hold=True),
        ]
        plan = plan_retention(policy, archives, now=NOW)
        assert len(plan.tier_actions) == 1
        assert len(plan.delete_actions) == 1
        assert len(plan.vetoed) == 1
