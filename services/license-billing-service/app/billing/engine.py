"""Invoice total calculation.

**An invoice total is the sum of its line items, discounted, never
independently entered.** A total that could disagree with its own line
items is a total nobody can trust; this engine only ever derives one
from the other.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

_MAX_PERCENTAGE = 100.0


@dataclass(frozen=True, slots=True)
class InvoiceLineItem:
    quantity: float
    unit_price: float


def compute_line_item_amount(quantity: float, unit_price: float) -> float:
    """The amount for one line item.

    Raises:
        ValueError: On a negative *quantity* or *unit_price*.
    """
    if quantity < 0 or unit_price < 0:
        raise ValueError("quantity and unit_price must both be non-negative.")
    return quantity * unit_price


def compute_invoice_subtotal(items: Sequence[InvoiceLineItem]) -> float:
    """The sum of every line item's amount, before discount."""
    return sum(compute_line_item_amount(item.quantity, item.unit_price) for item in items)


def apply_percentage_discount(subtotal: float, *, percentage: float) -> float:
    """The subtotal after applying a percentage discount.

    Raises:
        ValueError: On a negative *subtotal*, or a *percentage* outside
            ``[0, 100]``.
    """
    if subtotal < 0:
        raise ValueError(f"subtotal must be non-negative; got {subtotal}.")
    if not 0.0 <= percentage <= _MAX_PERCENTAGE:
        raise ValueError(f"percentage must be within [0, 100]; got {percentage}.")
    return subtotal * (1.0 - percentage / _MAX_PERCENTAGE)


def apply_fixed_discount(subtotal: float, *, amount: float) -> float:
    """The subtotal after applying a fixed-amount discount, never
    going negative.

    Raises:
        ValueError: On a negative *subtotal* or *amount*.
    """
    if subtotal < 0 or amount < 0:
        raise ValueError("subtotal and amount must both be non-negative.")
    return max(0.0, subtotal - amount)


__all__ = [
    "InvoiceLineItem",
    "apply_fixed_discount",
    "apply_percentage_discount",
    "compute_invoice_subtotal",
    "compute_line_item_amount",
]
