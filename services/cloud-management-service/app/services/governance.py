"""Governance policy creation and evaluation.

Wires ``app.governance.engine``'s pure tag/naming/quota evaluation onto
the repository that persists policies.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.governance.engine import (
    PolicyEvaluation,
    evaluate_naming_policy,
    evaluate_quota_policy,
    evaluate_tag_policy,
)
from app.models.enums import AuditAction, CloudPolicyStatus, CloudPolicyType
from app.models.operations import CloudPolicy
from app.repositories.operations import CloudPolicyRepository
from app.services.audit import AuditService


class CloudPolicyService:
    def __init__(self, repo: CloudPolicyRepository, *, audit: AuditService | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def create_policy(
        self,
        organization_id: UUID,
        *,
        name: str,
        policy_type: CloudPolicyType,
        definition: dict[str, object],
        scope_account_id: UUID | None,
        actor_id: str | None,
        now: datetime,
    ) -> CloudPolicy:
        policy = await self._repo.create(
            CloudPolicy(
                organization_id=organization_id,
                name=name,
                policy_type=policy_type,
                definition=definition,
                status=CloudPolicyStatus.DRAFT,
                scope_account_id=scope_account_id,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.POLICY_CHANGED,
                entity_type="cloud_policy",
                entity_id=policy.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Created {policy_type.value} policy {name!r}.",
            )
        return policy

    async def activate(self, policy: CloudPolicy) -> CloudPolicy:
        policy.status = CloudPolicyStatus.ACTIVE
        return await self._repo.update(policy)

    async def disable(self, policy: CloudPolicy) -> CloudPolicy:
        policy.status = CloudPolicyStatus.DISABLED
        return await self._repo.update(policy)

    def evaluate(
        self,
        policy: CloudPolicy,
        *,
        tags: dict[str, str] | None = None,
        name: str | None = None,
        current_count: int | None = None,
    ) -> PolicyEvaluation:
        """Evaluate *policy* against the given resource attributes.

        Raises:
            ValueError: If *policy*'s type requires an attribute that
                was not supplied.
        """
        policy_type = CloudPolicyType(policy.policy_type)
        if policy_type == CloudPolicyType.TAG:
            if tags is None:
                raise ValueError("tags is required to evaluate a TAG policy.")
            raw_keys = policy.definition.get("required_keys", [])
            required_keys = (
                frozenset(str(key) for key in raw_keys)
                if isinstance(raw_keys, list)
                else frozenset()
            )
            return evaluate_tag_policy(tags, required_keys=required_keys)
        if policy_type == CloudPolicyType.NAMING:
            if name is None:
                raise ValueError("name is required to evaluate a NAMING policy.")
            pattern = str(policy.definition.get("pattern", ".*"))
            return evaluate_naming_policy(name, pattern=pattern)
        if policy_type == CloudPolicyType.QUOTA:
            if current_count is None:
                raise ValueError("current_count is required to evaluate a QUOTA policy.")
            raw_max = policy.definition.get("max_count", 1)
            max_count = raw_max if isinstance(raw_max, int) else 1
            return evaluate_quota_policy(current_count=current_count, max_count=max_count)
        return PolicyEvaluation(
            is_compliant=True, detail=f"No automated evaluation for {policy_type.value}."
        )


__all__ = ["CloudPolicyService"]
