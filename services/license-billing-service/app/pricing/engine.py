"""Promotion redemption validation and tiered pricing.

**A promotion past its redemption limit or outside its active window is
refused, never silently ignored or silently applied anyway.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class PromotionRefusal:
    NOT_YET_STARTED = "not_yet_started"
    ENDED = "ended"
    REDEMPTION_LIMIT_REACHED = "redemption_limit_reached"


@dataclass(frozen=True, slots=True)
class PromotionValidation:
    is_valid: bool
    refusal: str | None
    detail: str


def validate_promotion_redemption(
    *,
    now: datetime,
    starts_at: datetime | None,
    ends_at: datetime | None,
    max_redemptions: int | None,
    redemption_count: int,
) -> PromotionValidation:
    """Whether a promotion code may be redeemed right now.

    ``starts_at``/``ends_at`` of ``None`` mean no bound on that side.
    ``max_redemptions`` of ``None`` means unlimited redemptions.

    Raises:
        ValueError: On a negative *redemption_count*.
    """
    if redemption_count < 0:
        raise ValueError(f"redemption_count must be non-negative; got {redemption_count}.")
    if starts_at is not None and now < starts_at:
        return PromotionValidation(
            is_valid=False,
            refusal=PromotionRefusal.NOT_YET_STARTED,
            detail=f"This promotion starts at {starts_at.isoformat()}.",
        )
    if ends_at is not None and now > ends_at:
        return PromotionValidation(
            is_valid=False,
            refusal=PromotionRefusal.ENDED,
            detail=f"This promotion ended at {ends_at.isoformat()}.",
        )
    if max_redemptions is not None and redemption_count >= max_redemptions:
        return PromotionValidation(
            is_valid=False,
            refusal=PromotionRefusal.REDEMPTION_LIMIT_REACHED,
            detail=f"This promotion has reached its limit of {max_redemptions} redemption(s).",
        )
    return PromotionValidation(is_valid=True, refusal=None, detail="Promotion is redeemable.")


def compute_tiered_price(quantity: float, *, tiers: tuple[tuple[float, float], ...]) -> float:
    """Total price for *quantity* units under tiered pricing.

    *tiers* is an ascending sequence of ``(tier_size, unit_price)``
    pairs; each tier's ``unit_price`` applies to the units falling
    within that tier's size, and any remainder beyond the last tier's
    cumulative size is priced at the last tier's rate.

    Raises:
        ValueError: On a negative *quantity*, an empty *tiers*, or a
            non-positive tier size/price.
    """
    if quantity < 0:
        raise ValueError(f"quantity must be non-negative; got {quantity}.")
    if not tiers:
        raise ValueError("tiers must not be empty.")
    for tier_size, unit_price in tiers:
        if tier_size <= 0 or unit_price < 0:
            raise ValueError("Every tier size must be positive and unit price non-negative.")

    remaining = quantity
    total = 0.0
    for tier_size, unit_price in tiers:
        used = min(remaining, tier_size)
        total += used * unit_price
        remaining -= used
        if remaining <= 0:
            return total
    # Any quantity beyond the last tier's cumulative size is priced at
    # the last tier's rate rather than silently going unpriced.
    total += remaining * tiers[-1][1]
    return total


__all__ = [
    "PromotionRefusal",
    "PromotionValidation",
    "compute_tiered_price",
    "validate_promotion_redemption",
]
