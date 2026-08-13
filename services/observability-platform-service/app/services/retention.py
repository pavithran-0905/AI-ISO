"""Retention service: turns a stored policy into an
``app.retention.engine`` plan and records the outcome -- the actual
downsample and delete SQL against each raw table is a worker concern
(per-table age-cutoff deletes are mechanical; this module owns only the
part that is not, which is *whether* a delete is authorized at all).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.operations import RetentionPolicy
from app.repositories.operations import RetentionPolicyRepository
from app.retention.engine import RetentionPlan, plan_retention


class RetentionService:
    """Plans and records retention sweeps for one organization's policies."""

    def __init__(self, repo: RetentionPolicyRepository) -> None:
        self._repo = repo

    async def plan_for_policy(
        self,
        policy: RetentionPolicy,
        *,
        now: datetime,
        epoch: datetime,
        raw_downsampled_watermark: datetime | None,
        downsampled_coarsened_watermark: datetime | None,
    ) -> RetentionPlan:
        """The plan for one policy row, without executing it.

        Never mutates the row: recording that a sweep *happened* is a
        separate, explicit step (:meth:`record_sweep`) so a caller that
        only wants to preview a plan -- a dry run -- cannot accidentally
        mark one as applied.
        """
        spec = RetentionPolicyRepository.as_spec(policy)
        return plan_retention(
            spec,
            now=now,
            epoch=epoch,
            raw_downsampled_watermark=raw_downsampled_watermark,
            downsampled_coarsened_watermark=downsampled_coarsened_watermark,
        )

    async def record_sweep(
        self,
        organization_id: UUID,
        policy_id: UUID,
        *,
        applied_at: datetime,
        deleted_count: int,
    ) -> RetentionPolicy:
        return await self._repo.record_sweep(
            organization_id, policy_id, applied_at=applied_at, deleted_count=deleted_count
        )

    async def plan_all_enabled(
        self,
        organization_id: UUID,
        *,
        now: datetime,
        epoch: datetime,
        watermarks: dict[UUID, tuple[datetime | None, datetime | None]],
    ) -> list[tuple[RetentionPolicy, RetentionPlan]]:
        """Plans for every enabled policy, paired with the row it came from.

        ``watermarks`` is keyed by policy id because each signal
        kind/environment scope downsamples and coarsens independently --
        one policy's lagging downsampler must not stall another's raw
        deletion.
        """
        policies = await self._repo.list_enabled(organization_id)
        plans = []
        for policy in policies:
            raw_watermark, downsampled_watermark = watermarks.get(policy.id, (None, None))
            plan = await self.plan_for_policy(
                policy,
                now=now,
                epoch=epoch,
                raw_downsampled_watermark=raw_watermark,
                downsampled_coarsened_watermark=downsampled_watermark,
            )
            plans.append((policy, plan))
        return plans


__all__ = ["RetentionService"]
