"""Service catalog item creation and approval workflow.

Wires ``app.catalog.engine``'s pure transition table onto the
repository that persists catalog items.
"""

from __future__ import annotations

from uuid import UUID

from app.catalog.engine import TransitionResult, validate_transition
from app.models.enums import CatalogItemStatus, CloudResourceType
from app.models.operations import CloudCatalogItem
from app.repositories.operations import CloudCatalogRepository


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class CloudCatalogService:
    def __init__(self, repo: CloudCatalogRepository) -> None:
        self._repo = repo

    async def create_item(
        self,
        organization_id: UUID,
        *,
        name: str,
        description: str | None,
        resource_type: CloudResourceType,
        version_label: str,
        template: dict[str, object],
    ) -> CloudCatalogItem:
        return await self._repo.create(
            CloudCatalogItem(
                organization_id=organization_id,
                name=name,
                description=description,
                resource_type=resource_type,
                status=CatalogItemStatus.DRAFT,
                version_label=version_label,
                template=template,
            )
        )

    async def transition(
        self, item: CloudCatalogItem, *, target: CatalogItemStatus
    ) -> CloudCatalogItem:
        """Move *item* to *target*, raising
        :class:`TransitionRefusedError` if the transition is not
        allowed."""
        result = validate_transition(item.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        item.status = target
        return await self._repo.update(item)


__all__ = ["CloudCatalogService", "TransitionRefusedError"]
