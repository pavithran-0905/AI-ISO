"""License and subscription feature entitlement management.

Wires ``app.entitlements.engine``'s pure limit checking onto the
repositories that persist entitlement definitions.
"""

from __future__ import annotations

from uuid import UUID

from app.entitlements.engine import is_feature_entitled
from app.models.licenses import LicenseEntitlement
from app.models.subscriptions import SubscriptionFeature
from app.repositories.licenses import LicenseEntitlementRepository
from app.repositories.subscriptions import SubscriptionFeatureRepository


class LicenseEntitlementService:
    def __init__(self, repo: LicenseEntitlementRepository) -> None:
        self._repo = repo

    async def grant(
        self, organization_id: UUID, *, license_id: UUID, feature_key: str, limit_value: int | None
    ) -> LicenseEntitlement:
        return await self._repo.create(
            LicenseEntitlement(
                organization_id=organization_id,
                license_id=license_id,
                feature_key=feature_key,
                limit_value=limit_value,
            )
        )

    async def check(self, license_id: UUID, *, feature_key: str, current_usage: int) -> bool:
        entitlement = await self._repo.find_by_key(license_id, feature_key=feature_key)
        if entitlement is None:
            return False
        return is_feature_entitled(
            is_enabled=entitlement.is_enabled,
            limit_value=entitlement.limit_value,
            current_usage=current_usage,
        )


class SubscriptionFeatureService:
    def __init__(self, repo: SubscriptionFeatureRepository) -> None:
        self._repo = repo

    async def grant(
        self, organization_id: UUID, *, plan_id: UUID, feature_key: str, limit_value: int | None
    ) -> SubscriptionFeature:
        return await self._repo.create(
            SubscriptionFeature(
                organization_id=organization_id,
                plan_id=plan_id,
                feature_key=feature_key,
                limit_value=limit_value,
            )
        )

    async def check(self, plan_id: UUID, *, feature_key: str, current_usage: int) -> bool:
        feature = await self._repo.find_by_key(plan_id, feature_key=feature_key)
        if feature is None:
            return False
        return is_feature_entitled(
            is_enabled=feature.is_enabled,
            limit_value=feature.limit_value,
            current_usage=current_usage,
        )


__all__ = ["LicenseEntitlementService", "SubscriptionFeatureService"]
