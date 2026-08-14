"""Tenant provisioning, lifecycle transitions, limits, usage, and
health.

Wires ``app.tenants.engine``'s pure transition table and limit
classification onto the repositories that persist tenants and their
per-tenant administrative records, publishing ``TenantCreated``/
``TenantUpdated``/``TenantDeleted``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import TenantCreatedEvent, TenantDeletedEvent, TenantUpdatedEvent
from app.models.enums import AuditAction, HealthCheckStatus, ProvisioningStatus, TenantStatus
from app.models.tenants import Tenant, TenantHealth, TenantLimit, TenantProvisioning, TenantUsage
from app.repositories.tenants import (
    TenantHealthRepository,
    TenantLimitRepository,
    TenantProvisioningRepository,
    TenantRepository,
    TenantUsageRepository,
)
from app.services.audit import AuditService
from app.tenants.engine import TransitionResult, classify_limit_status, validate_transition
from app.types import EventPublisher

_SOURCE_SERVICE = "administration-portal-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class TenantService:
    def __init__(
        self,
        tenant_repo: TenantRepository,
        provisioning_repo: TenantProvisioningRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._provisioning_repo = provisioning_repo
        self._publish = publish
        self._audit = audit

    async def provision(
        self,
        organization_id: UUID,
        *,
        organization_ref_id: UUID,
        name: str,
        actor_id: str | None,
        now: datetime,
    ) -> Tenant:
        tenant = await self._tenant_repo.create(
            Tenant(
                organization_id=organization_id, organization_ref_id=organization_ref_id, name=name
            )
        )
        await self._provisioning_repo.create(
            TenantProvisioning(
                organization_id=organization_id,
                tenant_id=tenant.id,
                status=ProvisioningStatus.IN_PROGRESS,
                requested_at=now,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.TENANT_OPERATION,
                entity_type="tenant",
                entity_id=tenant.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Provisioned tenant {name!r}.",
            )
        await self._publish(
            TenantCreatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "tenant_id": str(tenant.id),
                    "organization_ref_id": str(organization_ref_id),
                    "name": name,
                },
            )
        )
        return tenant

    async def transition(
        self, tenant: Tenant, *, target: TenantStatus, actor_id: str | None, now: datetime
    ) -> Tenant:
        """Move *tenant* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(tenant.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)

        tenant.status = target
        await self._tenant_repo.update(tenant)

        if self._audit is not None:
            await self._audit.record(
                tenant.organization_id,
                action=AuditAction.TENANT_OPERATION,
                entity_type="tenant",
                entity_id=tenant.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Tenant {tenant.id!s} moved to {target.value}.",
            )

        if target == TenantStatus.DELETING:
            await self._publish(
                TenantDeletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=tenant.organization_id,
                    payload={"tenant_id": str(tenant.id)},
                )
            )
        else:
            await self._publish(
                TenantUpdatedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=tenant.organization_id,
                    payload={"tenant_id": str(tenant.id), "status": target.value},
                )
            )
        return tenant


class TenantLimitService:
    def __init__(self, repo: TenantLimitRepository) -> None:
        self._repo = repo

    async def set_limit(
        self, organization_id: UUID, *, tenant_id: UUID, metric_key: str, limit_value: float
    ) -> TenantLimit:
        existing = await self._repo.find_by_metric(tenant_id, metric_key=metric_key)
        if existing is not None:
            existing.limit_value = limit_value
            return await self._repo.update(existing)
        return await self._repo.create(
            TenantLimit(
                organization_id=organization_id,
                tenant_id=tenant_id,
                metric_key=metric_key,
                limit_value=limit_value,
            )
        )

    def classify(self, limit: TenantLimit, *, used_value: float, warning_fraction: float) -> str:
        return classify_limit_status(
            used_value, limit.limit_value, warning_fraction=warning_fraction
        )


class TenantUsageService:
    def __init__(self, repo: TenantUsageRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        tenant_id: UUID,
        metric_key: str,
        used_value: float,
        now: datetime,
    ) -> TenantUsage:
        return await self._repo.create(
            TenantUsage(
                organization_id=organization_id,
                tenant_id=tenant_id,
                metric_key=metric_key,
                used_value=used_value,
                recorded_at=now,
            )
        )


class TenantHealthService:
    def __init__(self, repo: TenantHealthRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        tenant_id: UUID,
        status: HealthCheckStatus,
        now: datetime,
        detail: str | None = None,
    ) -> TenantHealth:
        return await self._repo.create(
            TenantHealth(
                organization_id=organization_id,
                tenant_id=tenant_id,
                status=status,
                checked_at=now,
                detail=detail,
            )
        )


__all__ = [
    "TenantHealthService",
    "TenantLimitService",
    "TenantService",
    "TenantUsageService",
    "TransitionRefusedError",
]
