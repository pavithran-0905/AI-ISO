"""Discount and promotion management.

Wires ``app.pricing.engine``'s pure redemption validation onto the
repositories that persist discounts and promotions.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.billing import Discount, Promotion
from app.models.enums import DiscountType
from app.pricing.engine import PromotionValidation, validate_promotion_redemption
from app.repositories.billing import DiscountRepository, PromotionRepository


class DiscountService:
    def __init__(self, repo: DiscountRepository) -> None:
        self._repo = repo

    async def create_discount(
        self, organization_id: UUID, *, name: str, discount_type: DiscountType, value: float
    ) -> Discount:
        return await self._repo.create(
            Discount(
                organization_id=organization_id, name=name, discount_type=discount_type, value=value
            )
        )

    async def disable(self, discount: Discount) -> Discount:
        discount.is_enabled = False
        return await self._repo.update(discount)


class PromotionRefusedError(Exception):
    def __init__(self, validation: PromotionValidation) -> None:
        super().__init__(validation.detail)
        self.validation = validation


class PromotionService:
    def __init__(self, repo: PromotionRepository) -> None:
        self._repo = repo

    async def create_promotion(
        self,
        organization_id: UUID,
        *,
        code: str,
        discount_id: UUID,
        starts_at: datetime | None,
        ends_at: datetime | None,
        max_redemptions: int | None,
    ) -> Promotion:
        return await self._repo.create(
            Promotion(
                organization_id=organization_id,
                code=code,
                discount_id=discount_id,
                starts_at=starts_at,
                ends_at=ends_at,
                max_redemptions=max_redemptions,
            )
        )

    async def redeem(self, promotion: Promotion, *, now: datetime) -> Promotion:
        """Redeem *promotion*, raising :class:`PromotionRefusedError` if
        it is not currently redeemable."""
        validation = validate_promotion_redemption(
            now=now,
            starts_at=promotion.starts_at,
            ends_at=promotion.ends_at,
            max_redemptions=promotion.max_redemptions,
            redemption_count=promotion.redemption_count,
        )
        if not validation.is_valid:
            raise PromotionRefusedError(validation)
        promotion.redemption_count += 1
        return await self._repo.update(promotion)


__all__ = ["DiscountService", "PromotionRefusedError", "PromotionService"]
