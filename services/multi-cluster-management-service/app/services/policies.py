"""Policy creation, target resolution, and drift detection.

Wires ``app.policies.engine``'s pure target resolution and drift
detection onto the repository that persists policies, and publishes
``PolicyApplied``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import PolicyAppliedEvent
from app.models.enums import AuditAction, PolicyPropagationStatus, PolicyType
from app.models.operations import ClusterPolicy
from app.policies.engine import TargetResolution, detect_drift, resolve_targets
from app.repositories.fleet import ClusterRepository
from app.repositories.operations import ClusterPolicyRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "multi-cluster-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PolicyTargetRefusedError(Exception):
    def __init__(self, resolution: TargetResolution) -> None:
        super().__init__(resolution.detail)
        self.resolution = resolution


class PolicyService:
    def __init__(
        self,
        repo: ClusterPolicyRepository,
        cluster_repo: ClusterRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._cluster_repo = cluster_repo
        self._publish = publish
        self._audit = audit

    async def create_policy(
        self,
        organization_id: UUID,
        *,
        name: str,
        policy_type: PolicyType,
        definition: dict[str, object],
        cluster_id: UUID | None,
        group_id: UUID | None,
        group_member_ids: list[UUID],
        actor_id: str | None,
        now: datetime,
    ) -> ClusterPolicy:
        """Create a policy, refusing one that names no target.

        Raises:
            PolicyTargetRefusedError: If neither *cluster_id* nor *group_id*
                is given.
        """
        resolution = resolve_targets(
            cluster_id=cluster_id, group_id=group_id, cluster_ids_in_group=group_member_ids
        )
        if not resolution.is_resolved:
            raise PolicyTargetRefusedError(resolution)

        policy = await self._repo.create(
            ClusterPolicy(
                organization_id=organization_id,
                cluster_id=cluster_id,
                group_id=group_id,
                name=name,
                policy_type=policy_type,
                definition=definition,
                propagation_status=PolicyPropagationStatus.PENDING,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.POLICY_UPDATED,
                entity_type="cluster_policy",
                entity_id=policy.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Created {policy_type.value} policy {name!r}, targeting "
                f"{len(resolution.target_cluster_ids)} cluster(s).",
            )
        return policy

    async def mark_applied(self, policy: ClusterPolicy, *, now: datetime) -> ClusterPolicy:
        policy.propagation_status = PolicyPropagationStatus.APPLIED
        policy.applied_at = now
        policy.last_checked_at = now
        await self._repo.update(policy)
        await self._publish(
            PolicyAppliedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=policy.organization_id,
                payload={
                    "policy_id": str(policy.id),
                    "target_cluster_ids": ([str(policy.cluster_id)] if policy.cluster_id else []),
                    "status": str(policy.propagation_status),
                },
            )
        )
        return policy

    async def mark_failed(self, policy: ClusterPolicy, *, now: datetime) -> ClusterPolicy:
        policy.propagation_status = PolicyPropagationStatus.FAILED
        policy.last_checked_at = now
        return await self._repo.update(policy)

    async def check_drift(
        self,
        policy: ClusterPolicy,
        *,
        live_state_hash: str | None,
        desired_hash: str,
        now: datetime,
    ) -> ClusterPolicy:
        """Recheck one applied policy for drift, updating its status if
        drifted."""
        policy.last_checked_at = now
        # ``==``, never ``is`` -- see app/services/placement.py's identical
        # note on why identity comparison against a possibly-freshly-loaded
        # ORM attribute is unreliable.
        if policy.propagation_status == PolicyPropagationStatus.APPLIED and detect_drift(
            desired_hash, live_state_hash
        ):
            policy.propagation_status = PolicyPropagationStatus.DRIFTED
        await self._repo.update(policy)
        return policy


__all__ = ["PolicyService", "PolicyTargetRefusedError"]
