"""Tests for app.cost.rates -- rate cards, resolution, pricing formulas."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.cost.enums import ChargeShape, MonthBasis, RateCardIssue, RateUnavailable, TierMode
from app.cost.rates import (
    SECONDS_PER_FIXED_MONTH,
    Rate,
    RateCard,
    RateCardSet,
    Tier,
    UnitConversion,
    price_quantity,
    resolve_rate,
    seconds_per_month,
    validate_rate_card_set,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 2, 1, tzinfo=UTC)
T2 = datetime(2026, 3, 1, tzinfo=UTC)


def _flat_rate(amount: str = "0.01") -> Rate:
    return Rate(meter="cpu_hours", unit="hour", currency="USD", unit_amount=Decimal(amount))


def _card(
    rates: dict[str, Rate], *, start: datetime = T0, end: datetime | None = T1, card_id: str = "c1"
) -> RateCard:
    return RateCard(
        card_id=card_id, version="v1", effective_from=start, effective_to=end, rates=rates
    )


class TestRateCard:
    def test_covers_within_range(self) -> None:
        card = _card({"cpu_hours": _flat_rate()})
        assert card.covers(T0)
        assert not card.covers(T1)

    def test_open_ended_card_covers_forever(self) -> None:
        card = _card({"cpu_hours": _flat_rate()}, end=None)
        assert card.covers(datetime(2099, 1, 1, tzinfo=UTC))


class TestRateCardSet:
    def test_conversion_factor_identity(self) -> None:
        rate_set = RateCardSet(cards=())
        assert rate_set.conversion_factor("token", "token") == Decimal(1)

    def test_conversion_factor_forward(self) -> None:
        conv = UnitConversion(from_unit="token", to_unit="1K-token", factor=Decimal("0.001"))
        rate_set = RateCardSet(cards=(), conversions=(conv,))
        assert rate_set.conversion_factor("token", "1K-token") == Decimal("0.001")

    def test_conversion_factor_reverse(self) -> None:
        conv = UnitConversion(from_unit="token", to_unit="1K-token", factor=Decimal("1000"))
        rate_set = RateCardSet(cards=(), conversions=(conv,))
        result = rate_set.conversion_factor("1K-token", "token")
        assert result == Decimal(1) / Decimal(1000)

    def test_conversion_factor_unknown_is_none(self) -> None:
        rate_set = RateCardSet(cards=())
        assert rate_set.conversion_factor("a", "b") is None

    def test_boundaries_within(self) -> None:
        card_a = _card({"cpu_hours": _flat_rate()}, start=T0, end=T1, card_id="a")
        card_b = _card({"cpu_hours": _flat_rate()}, start=T1, end=T2, card_id="b")
        rate_set = RateCardSet(cards=(card_a, card_b))
        boundaries = rate_set.boundaries_within(T0, T2)
        assert boundaries == (T1,)


class TestResolveRate:
    def test_no_card_for_instant(self) -> None:
        rate_set = RateCardSet(cards=(_card({"cpu_hours": _flat_rate()}),))
        result = resolve_rate(rate_set, "cpu_hours", T2)
        assert result.rate is None
        assert result.unavailable is RateUnavailable.NO_CARD_FOR_INSTANT

    def test_ambiguous_overlapping_cards(self) -> None:
        card_a = _card({"cpu_hours": _flat_rate()}, start=T0, end=T2, card_id="a")
        card_b = _card({"cpu_hours": _flat_rate()}, start=T0, end=T2, card_id="b")
        rate_set = RateCardSet(cards=(card_a, card_b))
        result = resolve_rate(rate_set, "cpu_hours", T0)
        assert result.unavailable is RateUnavailable.AMBIGUOUS_OVERLAPPING_CARDS

    def test_meter_not_in_card(self) -> None:
        rate_set = RateCardSet(cards=(_card({"cpu_hours": _flat_rate()}),))
        result = resolve_rate(rate_set, "gpu_hours", T0)
        assert result.unavailable is RateUnavailable.METER_NOT_IN_CARD

    def test_tier_mode_unspecified(self) -> None:
        tiered = Rate(
            meter="storage",
            unit="GB",
            currency="USD",
            tiers=(Tier(up_to=Decimal(100), unit_amount=Decimal("0.02")),),
        )
        rate_set = RateCardSet(cards=(_card({"storage": tiered}),))
        result = resolve_rate(rate_set, "storage", T0)
        assert result.unavailable is RateUnavailable.TIER_MODE_UNSPECIFIED

    def test_resolves_successfully(self) -> None:
        rate_set = RateCardSet(cards=(_card({"cpu_hours": _flat_rate()}),))
        result = resolve_rate(rate_set, "cpu_hours", T0)
        assert result.rate is not None
        assert result.card_id == "c1"


class TestValidateRateCardSet:
    def test_overlapping_ranges_detected(self) -> None:
        card_a = _card({"cpu_hours": _flat_rate()}, start=T0, end=T2, card_id="a")
        card_b = _card({"cpu_hours": _flat_rate()}, start=T1, end=None, card_id="b")
        issues = validate_rate_card_set(RateCardSet(cards=(card_a, card_b)))
        assert any(issue.issue is RateCardIssue.OVERLAPPING_EFFECTIVE_RANGES for issue in issues)

    def test_gap_in_coverage_detected(self) -> None:
        card_a = _card({"cpu_hours": _flat_rate()}, start=T0, end=T1, card_id="a")
        card_b = _card({"cpu_hours": _flat_rate()}, start=T2, end=None, card_id="b")
        issues = validate_rate_card_set(
            RateCardSet(cards=(card_a, card_b)), period=(T0, datetime(2026, 4, 1, tzinfo=UTC))
        )
        assert any(issue.issue is RateCardIssue.GAP_IN_COVERAGE for issue in issues)

    def test_currency_inconsistent_detected(self) -> None:
        usd_rate = Rate(meter="a", unit="u", currency="USD", unit_amount=Decimal("1"))
        eur_rate = Rate(meter="b", unit="u", currency="EUR", unit_amount=Decimal("1"))
        card = _card({"a": usd_rate, "b": eur_rate})
        issues = validate_rate_card_set(RateCardSet(cards=(card,)))
        assert any(issue.issue is RateCardIssue.CURRENCY_INCONSISTENT for issue in issues)

    def test_rate_underflow_detected(self) -> None:
        tiny_rate = Rate(meter="a", unit="u", currency="USD", unit_amount=Decimal("1E-13"))
        card = _card({"a": tiny_rate})
        issues = validate_rate_card_set(RateCardSet(cards=(card,)))
        assert any(issue.issue is RateCardIssue.RATE_UNDERFLOW for issue in issues)

    def test_tier_mode_missing_detected(self) -> None:
        tiered = Rate(
            meter="storage",
            unit="GB",
            currency="USD",
            tiers=(Tier(up_to=None, unit_amount=Decimal("0.02")),),
        )
        card = _card({"storage": tiered})
        issues = validate_rate_card_set(RateCardSet(cards=(card,)))
        assert any(issue.issue is RateCardIssue.TIER_MODE_MISSING for issue in issues)

    def test_non_monotonic_tiers_detected(self) -> None:
        tiered = Rate(
            meter="storage",
            unit="GB",
            currency="USD",
            tier_mode=TierMode.GRADUATED,
            tiers=(
                Tier(up_to=Decimal(100), unit_amount=Decimal("0.02")),
                Tier(up_to=Decimal(50), unit_amount=Decimal("0.01")),
            ),
        )
        card = _card({"storage": tiered})
        issues = validate_rate_card_set(RateCardSet(cards=(card,)))
        assert any(issue.issue is RateCardIssue.NON_MONOTONIC_TIERS for issue in issues)

    def test_unknown_unit_detected(self) -> None:
        card = _card({"cpu_hours": _flat_rate()})
        issues = validate_rate_card_set(RateCardSet(cards=(card,)), known_units=["GB"])
        assert any(issue.issue is RateCardIssue.UNKNOWN_UNIT for issue in issues)

    def test_clean_card_has_no_issues(self) -> None:
        card = _card({"cpu_hours": _flat_rate()})
        issues = validate_rate_card_set(RateCardSet(cards=(card,)), known_units=["hour"])
        assert issues == ()

    def test_empty_set_has_no_issues(self) -> None:
        assert validate_rate_card_set(RateCardSet(cards=())) == ()


class TestPriceQuantity:
    def test_flat_rate(self) -> None:
        priced = price_quantity(Decimal(10), _flat_rate("0.5"))
        assert priced.cost.amount == Decimal("5.0")

    def test_conversion_factor_applied(self) -> None:
        priced = price_quantity(Decimal(10), _flat_rate("1"), conversion_factor=Decimal("0.5"))
        assert priced.converted_quantity == Decimal("5.0")
        assert priced.cost.amount == Decimal("5.0")

    def test_graduated_tiers(self) -> None:
        rate = Rate(
            meter="storage",
            unit="GB",
            currency="USD",
            tier_mode=TierMode.GRADUATED,
            tiers=(
                Tier(up_to=Decimal(100), unit_amount=Decimal("0.10")),
                Tier(up_to=None, unit_amount=Decimal("0.05")),
            ),
        )
        priced = price_quantity(Decimal(150), rate)
        # 100 * 0.10 + 50 * 0.05 = 10 + 2.5 = 12.5
        assert priced.cost.amount == Decimal("12.500")

    def test_volume_tiers(self) -> None:
        rate = Rate(
            meter="storage",
            unit="GB",
            currency="USD",
            tier_mode=TierMode.VOLUME,
            tiers=(
                Tier(up_to=Decimal(100), unit_amount=Decimal("0.10")),
                Tier(up_to=None, unit_amount=Decimal("0.05")),
            ),
        )
        priced = price_quantity(Decimal(150), rate)
        # whole quantity at the tier it falls into: 150 * 0.05
        assert priced.cost.amount == Decimal("7.50")

    def test_volume_tier_exact_fallback(self) -> None:
        rate = Rate(
            meter="storage",
            unit="GB",
            currency="USD",
            tier_mode=TierMode.VOLUME,
            tiers=(Tier(up_to=Decimal(100), unit_amount=Decimal("0.10")),),
        )
        priced = price_quantity(Decimal(50), rate)
        assert priced.cost.amount == Decimal("5.00")

    def test_tiers_without_mode_raises(self) -> None:
        rate = Rate(
            meter="storage",
            unit="GB",
            currency="USD",
            tiers=(Tier(up_to=None, unit_amount=Decimal("0.10")),),
        )
        with pytest.raises(ValueError, match="tier_mode"):
            price_quantity(Decimal(10), rate)

    def test_no_amount_no_tiers_raises(self) -> None:
        rate = Rate(meter="storage", unit="GB", currency="USD")
        with pytest.raises(ValueError, match="neither a unit amount nor tiers"):
            price_quantity(Decimal(10), rate)

    def test_minimum_increment_applied(self) -> None:
        rate = Rate(
            meter="cpu_hours",
            unit="hour",
            currency="USD",
            unit_amount=Decimal("1"),
            minimum_increment=Decimal("1"),
        )
        priced = price_quantity(Decimal("0.3"), rate)
        assert priced.billable_quantity == Decimal("1")
        assert priced.cost.amount == Decimal("1")


class TestSecondsPerMonth:
    def test_fixed_basis(self) -> None:
        assert seconds_per_month(MonthBasis.FIXED_730H) == SECONDS_PER_FIXED_MONTH

    def test_calendar_basis_requires_period(self) -> None:
        with pytest.raises(ValueError, match="needs the period length"):
            seconds_per_month(MonthBasis.CALENDAR)

    def test_calendar_basis_with_period(self) -> None:
        result = seconds_per_month(MonthBasis.CALENDAR, Decimal(2_678_400))
        assert result == Decimal(2_678_400)


def test_charge_shape_enum_values() -> None:
    assert ChargeShape.PER_UNIT.value == "per_unit"
