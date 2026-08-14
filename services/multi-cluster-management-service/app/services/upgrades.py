"""Upgrade planning and execution.

Wires ``app.upgrades.engine``'s pure version-skew validation and
rollback decision onto the repositories that persist the version catalog
and upgrade executions, and publishes ``ClusterUpgraded``.
"""

from __future__ import annotations

from datetime import datetime

from app.events.domain_events import ClusterUpgradedEvent
from app.models.enums import AuditAction, UpgradeStatus, UpgradeStrategy
from app.models.fleet import Cluster
from app.models.operations import ClusterUpgrade
from app.repositories.fleet import ClusterRepository, ClusterVersionRepository
from app.repositories.operations import ClusterUpgradeRepository
from app.services.audit import AuditService
from app.types import EventPublisher
from app.upgrades.engine import UpgradePlanValidation, should_roll_back, validate_upgrade_plan

_SOURCE_SERVICE = "multi-cluster-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class UpgradePlanRefusedError(Exception):
    def __init__(self, validation: UpgradePlanValidation) -> None:
        super().__init__(validation.detail)
        self.validation = validation


class UpgradeService:
    def __init__(
        self,
        repo: ClusterUpgradeRepository,
        version_repo: ClusterVersionRepository,
        cluster_repo: ClusterRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._version_repo = version_repo
        self._cluster_repo = cluster_repo
        self._publish = publish
        self._audit = audit

    async def plan_upgrade(
        self,
        cluster: Cluster,
        *,
        to_version: str,
        strategy: UpgradeStrategy,
        max_skew: int,
        actor_id: str | None,
        now: datetime,
    ) -> ClusterUpgrade:
        """Validate and persist an upgrade plan for *cluster*.

        Raises:
            UpgradePlanRefusedError: If the target version is not a valid
                forward step within *max_skew* of the cluster's current
                catalog rank.
        """
        current_entry = await self._version_repo.find_by_type_and_version(
            cluster.cluster_type, cluster.kubernetes_version or ""
        )
        target_entry = await self._version_repo.find_by_type_and_version(
            cluster.cluster_type, to_version
        )
        from_rank = current_entry.skew_rank if current_entry is not None else 0
        to_rank = target_entry.skew_rank if target_entry is not None else 0

        validation = validate_upgrade_plan(from_rank, to_rank, max_skew=max_skew)
        if not validation.is_valid:
            raise UpgradePlanRefusedError(validation)

        upgrade = await self._repo.create(
            ClusterUpgrade(
                organization_id=cluster.organization_id,
                cluster_id=cluster.id,
                from_version=cluster.kubernetes_version or "unknown",
                to_version=to_version,
                strategy=strategy,
                status=UpgradeStatus.PLANNED,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                cluster.organization_id,
                action=AuditAction.UPGRADE_EXECUTED,
                entity_type="cluster_upgrade",
                entity_id=upgrade.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Planned upgrade of cluster {cluster.id!s} to {to_version}.",
            )
        return upgrade

    async def start_upgrade(self, upgrade: ClusterUpgrade, *, now: datetime) -> ClusterUpgrade:
        upgrade.status = UpgradeStatus.IN_PROGRESS
        upgrade.started_at = now
        return await self._repo.update(upgrade)

    async def complete_upgrade(
        self,
        upgrade: ClusterUpgrade,
        *,
        pre_validation_passed: bool,
        post_validation_passed: bool,
        now: datetime,
    ) -> ClusterUpgrade:
        """Finish an upgrade, marking it rolled back if post-validation
        explicitly failed."""
        upgrade.pre_validation_passed = pre_validation_passed
        upgrade.post_validation_passed = post_validation_passed
        upgrade.completed_at = now
        upgrade.duration_ms = (
            (now - upgrade.started_at).total_seconds() * 1000.0 if upgrade.started_at else None
        )
        upgrade.status = (
            UpgradeStatus.ROLLED_BACK
            if should_roll_back(
                pre_validation_passed=pre_validation_passed,
                post_validation_passed=post_validation_passed,
            )
            else UpgradeStatus.COMPLETED
        )
        await self._repo.update(upgrade)

        cluster = await self._cluster_repo.require_by_id(upgrade.cluster_id)
        if upgrade.status == UpgradeStatus.COMPLETED:
            cluster.kubernetes_version = upgrade.to_version
            await self._cluster_repo.update(cluster)

        await self._publish(
            ClusterUpgradedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=upgrade.organization_id,
                payload={
                    "cluster_id": str(upgrade.cluster_id),
                    "upgrade_id": str(upgrade.id),
                    "from_version": upgrade.from_version,
                    "to_version": upgrade.to_version,
                    "status": str(upgrade.status),
                },
            )
        )
        return upgrade

    async def fail_upgrade(
        self, upgrade: ClusterUpgrade, *, error_message: str, now: datetime
    ) -> ClusterUpgrade:
        upgrade.status = UpgradeStatus.FAILED
        upgrade.completed_at = now
        upgrade.error_message = error_message
        await self._repo.update(upgrade)
        await self._publish(
            ClusterUpgradedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=upgrade.organization_id,
                payload={
                    "cluster_id": str(upgrade.cluster_id),
                    "upgrade_id": str(upgrade.id),
                    "from_version": upgrade.from_version,
                    "to_version": upgrade.to_version,
                    "status": str(upgrade.status),
                },
            )
        )
        return upgrade


__all__ = ["UpgradePlanRefusedError", "UpgradeService"]
