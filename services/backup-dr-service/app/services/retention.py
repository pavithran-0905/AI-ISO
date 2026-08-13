"""Backup retention: turns a stored policy into an
``app.retention.engine`` plan and applies it -- tiering and deletion,
with immutability and legal hold enforced as an absolute veto.

Planning and execution are kept as separate methods, exactly as every
other AI-IOS retention service does: a caller previewing a plan (a dry
run) must not be able to accidentally apply it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.backup import BackupArchive, BackupRetention
from app.repositories.backup import BackupArchiveRepository, BackupRetentionRepository
from app.retention.engine import ArchiveRecord, RetentionPlan, RetentionPolicySpec, plan_retention


def _as_spec(policy: BackupRetention) -> RetentionPolicySpec:
    return RetentionPolicySpec(
        retention_days=policy.retention_days,
        archive_after_days=policy.archive_after_days,
        is_enabled=policy.is_enabled,
    )


def _to_record(row: BackupArchive) -> ArchiveRecord:
    return ArchiveRecord(
        archive_id=str(row.id),
        archived_at=row.archived_at,
        tier=row.tier,
        immutability_state=row.immutability_state,
        retention_lock_until=row.retention_lock_until,
        legal_hold=row.legal_hold,
    )


class RetentionService:
    """Plans and applies retention sweeps for one organization's
    archives."""

    def __init__(
        self, policy_repo: BackupRetentionRepository, archive_repo: BackupArchiveRepository
    ) -> None:
        self._policy_repo = policy_repo
        self._archive_repo = archive_repo

    def plan_for_policy(
        self, policy: BackupRetention, archives: list[BackupArchive], *, now: datetime
    ) -> RetentionPlan:
        """The plan for one policy against a set of archives, without
        executing it."""
        return plan_retention(_as_spec(policy), [_to_record(a) for a in archives], now=now)

    async def apply_plan(
        self, plan: RetentionPlan, archives_by_id: dict[str, BackupArchive]
    ) -> int:
        """Execute a previously-computed plan, returning the count of
        archives deleted (tier changes are not counted -- they are not
        destructive and a caller cares about how many bytes actually
        left storage)."""
        for tier_action in plan.tier_actions:
            archive = archives_by_id[tier_action.archive_id]
            archive.tier = tier_action.to_tier
            await self._archive_repo.update(archive)
        for delete_action in plan.delete_actions:
            archive = archives_by_id[delete_action.archive_id]
            archive.is_deleted_from_storage = True
            await self._archive_repo.update(archive)
        return len(plan.delete_actions)

    async def record_sweep(
        self, organization_id: UUID, policy_id: UUID, *, applied_at: datetime, deleted_count: int
    ) -> BackupRetention:
        policy = await self._policy_repo.require_by_id(policy_id)
        policy.last_applied_at = applied_at
        policy.last_purged_count = deleted_count
        return await self._policy_repo.update(policy)


__all__ = ["RetentionService"]
