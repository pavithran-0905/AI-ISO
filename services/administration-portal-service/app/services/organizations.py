"""Organization creation and lifecycle.

Wires ``app.organizations.engine``'s pure transition table onto the
repository that persists an organization's ``status``.
"""

from __future__ import annotations

from uuid import UUID

from app.models.enums import OrganizationStatus
from app.models.tenants import Organization
from app.organizations.engine import TransitionResult, validate_transition
from app.repositories.tenants import OrganizationRepository


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class OrganizationService:
    def __init__(self, repo: OrganizationRepository) -> None:
        self._repo = repo

    async def create_organization(
        self, organization_id: UUID, *, name: str, external_ref: str | None = None
    ) -> Organization:
        return await self._repo.create(
            Organization(organization_id=organization_id, name=name, external_ref=external_ref)
        )

    async def transition(
        self, organization: Organization, *, target: OrganizationStatus
    ) -> Organization:
        """Move *organization* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(organization.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        organization.status = target
        return await self._repo.update(organization)


__all__ = ["OrganizationService", "TransitionRefusedError"]
