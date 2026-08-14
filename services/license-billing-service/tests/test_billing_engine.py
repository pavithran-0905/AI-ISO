"""Tests for app.billing.engine: invoice line item and subtotal
calculation, and discount application."""

from __future__ import annotations

import pytest

from app.billing.engine import (
    InvoiceLineItem,
    apply_fixed_discount,
    apply_percentage_discount,
    compute_invoice_subtotal,
    compute_line_item_amount,
)


class TestComputeLineItemAmount:
    def test_multiplies_quantity_and_price(self) -> None:
        assert compute_line_item_amount(3, 10.0) == 30.0

    def test_negative_quantity_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_line_item_amount(-1, 10.0)

    def test_negative_price_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_line_item_amount(1, -10.0)


class TestComputeInvoiceSubtotal:
    def test_sums_line_items(self) -> None:
        items = [
            InvoiceLineItem(quantity=2, unit_price=10.0),
            InvoiceLineItem(quantity=1, unit_price=5.0),
        ]
        assert compute_invoice_subtotal(items) == 25.0

    def test_empty_items_is_zero(self) -> None:
        assert compute_invoice_subtotal([]) == 0.0


class TestApplyPercentageDiscount:
    def test_applies_percentage(self) -> None:
        assert apply_percentage_discount(100.0, percentage=10.0) == 90.0

    def test_zero_percent_is_unchanged(self) -> None:
        assert apply_percentage_discount(100.0, percentage=0.0) == 100.0

    def test_full_percentage_zeroes_out(self) -> None:
        assert apply_percentage_discount(100.0, percentage=100.0) == 0.0

    def test_negative_subtotal_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            apply_percentage_discount(-1.0, percentage=10.0)

    def test_out_of_range_percentage_raises(self) -> None:
        with pytest.raises(ValueError, match="0, 100"):
            apply_percentage_discount(100.0, percentage=150.0)


class TestApplyFixedDiscount:
    def test_subtracts_amount(self) -> None:
        assert apply_fixed_discount(100.0, amount=30.0) == 70.0

    def test_never_goes_negative(self) -> None:
        assert apply_fixed_discount(10.0, amount=100.0) == 0.0

    def test_negative_subtotal_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            apply_fixed_discount(-1.0, amount=10.0)

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            apply_fixed_discount(10.0, amount=-1.0)
