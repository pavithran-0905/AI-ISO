"""Tests for app.cost.money -- Decimal-based money arithmetic."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.cost.money import (
    CurrencyMismatchError,
    FxRate,
    Money,
    amount_exponent,
    apply_minimum_increment,
    split_money,
    sum_money,
    total_multi_currency,
    validate_currency,
)


class TestValidateCurrency:
    def test_normalises_case(self) -> None:
        assert validate_currency("usd") == "USD"

    def test_rejects_invalid_code(self) -> None:
        with pytest.raises(ValueError, match="ISO 4217"):
            validate_currency("US")


class TestAmountExponent:
    def test_default_two_places(self) -> None:
        assert amount_exponent("USD") == 2

    def test_zero_decimal_currency(self) -> None:
        assert amount_exponent("JPY") == 0

    def test_three_decimal_currency(self) -> None:
        assert amount_exponent("KWD") == 3


class TestMoney:
    def test_rejects_non_decimal_amount(self) -> None:
        with pytest.raises(TypeError, match="must be a Decimal"):
            Money(amount=1.5, currency="USD")  # type: ignore[arg-type]

    def test_measured_zero(self) -> None:
        money = Money.measured_zero("USD")
        assert money.is_zero

    def test_of_from_string(self) -> None:
        money = Money.of("10.50", "USD")
        assert money.amount == Decimal("10.50")

    def test_add_same_currency(self) -> None:
        total = Money.of("10", "USD") + Money.of("5", "USD")
        assert total.amount == Decimal("15")

    def test_add_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money.of("10", "USD") + Money.of("5", "EUR")

    def test_sub_same_currency(self) -> None:
        result = Money.of("10", "USD") - Money.of("3", "USD")
        assert result.amount == Decimal("7")

    def test_sub_different_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money.of("10", "USD") - Money.of("3", "EUR")

    def test_neg(self) -> None:
        assert (-Money.of("5", "USD")).amount == Decimal("-5")

    def test_scaled(self) -> None:
        result = Money.of("10", "USD").scaled(Decimal("1.5"))
        assert result.amount == Decimal("15.0")

    def test_quantized_default_exponent(self) -> None:
        money = Money.of("10.126", "USD")
        assert money.quantized() == Decimal("10.13")

    def test_quantized_explicit_exponent(self) -> None:
        money = Money.of("10.126", "USD")
        assert money.quantized(0) == Decimal("10")

    def test_minor_units(self) -> None:
        money = Money.of("10.50", "USD")
        assert money.minor_units() == 1050

    def test_str(self) -> None:
        assert str(Money.of("10.5", "USD")) == "10.50 USD"


class TestSumMoney:
    def test_all_priced(self) -> None:
        result = sum_money([Money.of("1", "USD"), Money.of("2", "USD")], "USD")
        assert result.total is not None
        assert result.total.amount == Decimal("3")
        assert result.counted == 2
        assert result.missing == 0
        assert not result.is_lower_bound

    def test_with_missing_is_lower_bound(self) -> None:
        result = sum_money([Money.of("1", "USD"), None], "USD")
        assert result.is_lower_bound
        assert result.missing == 1

    def test_nothing_priced_returns_none_total(self) -> None:
        result = sum_money([None, None], "USD")
        assert result.total is None

    def test_mismatched_currency_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            sum_money([Money.of("1", "EUR")], "USD")


class TestTotalMultiCurrency:
    def test_no_target_groups_only(self) -> None:
        result = total_multi_currency([Money.of("10", "USD"), Money.of("5", "EUR")])
        assert result.converted is None
        assert set(result.by_currency) == {"USD", "EUR"}
        assert not result.is_complete

    def test_with_target_and_matching_currency(self) -> None:
        result = total_multi_currency([Money.of("10", "USD")], target="USD")
        assert result.converted is not None
        assert result.converted.amount == Decimal("10")
        assert result.is_complete

    def test_conversion_with_fx_rate(self) -> None:
        rate = FxRate(
            base="EUR", quote="USD", rate=Decimal("1.1"), as_of=datetime.now(UTC), source="test"
        )
        result = total_multi_currency(
            [Money.of("10", "USD"), Money.of("10", "EUR")], target="USD", fx=[rate]
        )
        assert result.converted is not None
        assert result.converted.amount == Decimal("21.0")
        assert result.is_complete

    def test_unconvertible_currency_stays_named(self) -> None:
        result = total_multi_currency([Money.of("10", "GBP")], target="USD", fx=[])
        assert "GBP" in result.unconvertible
        assert not result.is_complete


class TestSplitMoney:
    def test_no_weights_raises(self) -> None:
        with pytest.raises(ValueError, match="no targets"):
            split_money(Money.of("10", "USD"), {})

    def test_negative_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="Negative weights"):
            split_money(Money.of("10", "USD"), {"a": Decimal("-1"), "b": Decimal("2")})

    def test_zero_weight_sum_raises(self) -> None:
        with pytest.raises(ValueError, match="sum to zero"):
            split_money(Money.of("10", "USD"), {"a": Decimal("0")})

    def test_even_split_is_exact(self) -> None:
        result = split_money(Money.of("10", "USD"), {"a": Decimal("1"), "b": Decimal("1")})
        assert result.exact
        assert result.parts["a"].amount == Decimal("5.00")
        assert result.parts["b"].amount == Decimal("5.00")

    def test_uneven_split_still_foots_via_largest_remainder(self) -> None:
        result = split_money(
            Money.of("10", "USD"),
            {"a": Decimal("1"), "b": Decimal("1"), "c": Decimal("1")},
        )
        assert result.exact
        total = sum((part.amount for part in result.parts.values()), Decimal(0))
        assert total == Decimal("10.00")

    def test_deterministic_tie_break_order(self) -> None:
        result_a = split_money(
            Money.of("10", "USD"), {"z": Decimal("1"), "a": Decimal("1"), "m": Decimal("1")}
        )
        result_b = split_money(
            Money.of("10", "USD"), {"z": Decimal("1"), "a": Decimal("1"), "m": Decimal("1")}
        )
        assert result_a.parts == result_b.parts


class TestApplyMinimumIncrement:
    def test_no_increment_returns_unchanged(self) -> None:
        assert apply_minimum_increment(Decimal("1.3"), None) == Decimal("1.3")

    def test_non_positive_increment_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            apply_minimum_increment(Decimal("1.0"), Decimal("0"))

    def test_rounds_up_to_increment(self) -> None:
        result = apply_minimum_increment(Decimal("1.3"), Decimal("1"))
        assert result == Decimal("2")

    def test_exact_multiple_unchanged(self) -> None:
        result = apply_minimum_increment(Decimal("4"), Decimal("2"))
        assert result == Decimal("4")
