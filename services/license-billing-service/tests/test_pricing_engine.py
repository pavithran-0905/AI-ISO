"""Tests for app.pricing.engine: promotion redemption validation and
tiered pricing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.pricing.engine import PromotionRefusal, compute_tiered_price, validate_promotion_redemption

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestValidatePromotionRedemption:
    def test_no_bounds_is_valid(self) -> None:
        result = validate_promotion_redemption(
            now=_NOW, starts_at=None, ends_at=None, max_redemptions=None, redemption_count=0
        )
        assert result.is_valid

    def test_not_yet_started(self) -> None:
        result = validate_promotion_redemption(
            now=_NOW,
            starts_at=_NOW + timedelta(days=1),
            ends_at=None,
            max_redemptions=None,
            redemption_count=0,
        )
        assert not result.is_valid
        assert result.refusal == PromotionRefusal.NOT_YET_STARTED

    def test_ended(self) -> None:
        result = validate_promotion_redemption(
            now=_NOW,
            starts_at=None,
            ends_at=_NOW - timedelta(days=1),
            max_redemptions=None,
            redemption_count=0,
        )
        assert not result.is_valid
        assert result.refusal == PromotionRefusal.ENDED

    def test_redemption_limit_reached(self) -> None:
        result = validate_promotion_redemption(
            now=_NOW, starts_at=None, ends_at=None, max_redemptions=5, redemption_count=5
        )
        assert not result.is_valid
        assert result.refusal == PromotionRefusal.REDEMPTION_LIMIT_REACHED

    def test_below_redemption_limit_is_valid(self) -> None:
        result = validate_promotion_redemption(
            now=_NOW, starts_at=None, ends_at=None, max_redemptions=5, redemption_count=4
        )
        assert result.is_valid

    def test_negative_redemption_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            validate_promotion_redemption(
                now=_NOW, starts_at=None, ends_at=None, max_redemptions=None, redemption_count=-1
            )


class TestComputeTieredPrice:
    _TIERS = ((10.0, 1.0), (10.0, 0.5))

    def test_within_first_tier(self) -> None:
        assert compute_tiered_price(5, tiers=self._TIERS) == 5.0

    def test_spans_two_tiers(self) -> None:
        assert compute_tiered_price(15, tiers=self._TIERS) == 10.0 + 5 * 0.5

    def test_beyond_last_tier_uses_last_rate(self) -> None:
        assert compute_tiered_price(25, tiers=self._TIERS) == 10.0 + 10 * 0.5 + 5 * 0.5

    def test_zero_quantity_is_zero(self) -> None:
        assert compute_tiered_price(0, tiers=self._TIERS) == 0.0

    def test_negative_quantity_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_tiered_price(-1, tiers=self._TIERS)

    def test_empty_tiers_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            compute_tiered_price(1, tiers=())

    def test_non_positive_tier_size_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            compute_tiered_price(1, tiers=((0.0, 1.0),))

    def test_negative_tier_price_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_tiered_price(1, tiers=((10.0, -1.0),))
