"""Cluster credential registration and validation.

Wires ``app.registration.engine``'s pure credential validation onto the
repository that persists credentials, and publishes ``ClusterValidated``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import ClusterValidatedEvent
from app.models.enums import AuditAction, RegistrationMethod
from app.models.fleet import ClusterCredential
from app.registration.engine import validate_credential
from app.repositories.fleet import ClusterCredentialRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "multi-cluster-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CredentialService:
    def __init__(
        self,
        repo: ClusterCredentialRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def register_credential(
        self,
        organization_id: UUID,
        *,
        cluster_id: UUID,
        method: RegistrationMethod,
        credential_ref: str,
        expires_at: datetime | None,
        actor_id: str | None,
        now: datetime,
    ) -> ClusterCredential:
        validation = validate_credential(credential_ref, expires_at=expires_at, now=now)
        credential = await self._repo.create(
            ClusterCredential(
                organization_id=organization_id,
                cluster_id=cluster_id,
                method=method,
                credential_ref=credential_ref,
                expires_at=expires_at,
                is_valid=validation.is_valid,
                last_validated_at=now,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.CREDENTIAL_CHANGED,
                entity_type="cluster_credential",
                entity_id=credential.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Registered {method.value} credential for cluster {cluster_id!s}.",
            )
        await self._publish(
            ClusterValidatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "cluster_id": str(cluster_id),
                    "is_valid": validation.is_valid,
                    "detail": validation.detail,
                },
            )
        )
        return credential

    async def revalidate(
        self, credential: ClusterCredential, *, now: datetime
    ) -> ClusterCredential:
        """Recheck an existing credential's expiry against *now*."""
        validation = validate_credential(
            credential.credential_ref, expires_at=credential.expires_at, now=now
        )
        credential.is_valid = validation.is_valid
        credential.last_validated_at = now
        await self._repo.update(credential)
        await self._publish(
            ClusterValidatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=credential.organization_id,
                payload={
                    "cluster_id": str(credential.cluster_id),
                    "is_valid": validation.is_valid,
                    "detail": validation.detail,
                },
            )
        )
        return credential


__all__ = ["CredentialService"]
