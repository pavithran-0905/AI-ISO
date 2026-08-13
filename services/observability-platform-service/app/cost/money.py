"""Money arithmetic for cost analytics.

**Float is disqualified here, for four separate reasons.** ``0.1`` is not
representable in binary64, so cent-level reconciliation against an
invoice fails by residues that print as ``$0.00`` and break ``==``.
Float addition is not associative, so summing four million usage rows
gives a *different total* when the rows arrive in a different partition
order -- two runs of the same report on the same data disagreeing in the
last cents, which by itself breaks the determinism this platform
promises. Model rates near 1.5e-7 multiplied by billions of tokens and
summed a million times accumulate an error nobody can state, so the
report cannot be audited. And ``round(x, 2)`` applies banker's rounding
to an already-wrong value while documenting nothing about the direction.

So: :class:`decimal.Decimal` throughout, unrounded until the presentation
boundary, with two distinct scales -- one for amounts and a much finer
one for unit rates.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import (
    ROUND_CEILING,
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
)

WORKING_CONTEXT = Context(
    prec=34,
    rounding=ROUND_HALF_EVEN,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)
"""IEEE decimal128 precision. Enough that a billion additions of
twelve-significant-digit line items never lose a minor unit. The traps
are deliberate: a silent NaN in a financial total is worse than a
traceback."""

RATE_MIN_DP = 12
"""Decimal places retained on unit rates. Quantizing a per-token price of
0.00000015 to two places gives 0.00, at which point every model-usage
cost in the platform is exactly zero -- and every test still passes,
because the fixtures were priced with the same broken rate."""

DEFAULT_AMOUNT_EXPONENT = 2

AMOUNT_EXPONENT: Mapping[str, int] = {
    # ISO 4217 minor units for the currencies that are not two-place.
    "JPY": 0,
    "KRW": 0,
    "CLP": 0,
    "ISK": 0,
    "VND": 0,
    "BHD": 3,
    "IQD": 3,
    "JOD": 3,
    "KWD": 3,
    "OMR": 3,
    "TND": 3,
}
"""Used **only** at the presentation boundary. Rounding to minor units
anywhere upstream destroys rate precision."""

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


class CurrencyMismatchError(ValueError):
    """Raised when two amounts in different currencies are combined.

    There is no implicit conversion anywhere in this module. A total that
    silently converted at an unstated rate on an unstated date cannot be
    reproduced tomorrow.
    """


def validate_currency(code: str) -> str:
    """Normalise and check an ISO 4217 alpha-3 code."""
    normalised = code.strip().upper()
    if not _CURRENCY_PATTERN.match(normalised):
        raise ValueError(f"{code!r} is not an ISO 4217 alpha-3 currency code.")
    return normalised


def amount_exponent(currency: str) -> int:
    """Minor-unit exponent for a currency."""
    return AMOUNT_EXPONENT.get(currency, DEFAULT_AMOUNT_EXPONENT)


@dataclass(frozen=True, slots=True)
class Money:
    """An amount in a stated currency, held unrounded.

    ``amount`` keeps full working precision all the way through the
    pipeline. :meth:`quantized` exists for display and for reconciling
    against an invoice, and is the only place rounding happens.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "currency", validate_currency(self.currency))
        if not isinstance(self.amount, Decimal):
            raise TypeError(
                f"Money.amount must be a Decimal, got {type(self.amount).__name__}. "
                "Floats are rejected at the constructor because a float that "
                "reaches here is already wrong."
            )

    @classmethod
    def measured_zero(cls, currency: str) -> Money:
        """Zero that was *observed*, as distinct from absent.

        Named at length so it cannot be typed by accident where ``None``
        was meant: "this project spent nothing" and "the collector was
        down" are different findings.
        """
        return cls(amount=Decimal(0), currency=currency)

    @classmethod
    def of(cls, amount: str | int | Decimal, currency: str) -> Money:
        """Build from a string or integer. Deliberately no float overload."""
        return cls(amount=Decimal(amount), currency=currency)

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot combine {self.currency} and {other.currency}; no implicit "
                "conversion exists. Supply an FxTable and convert explicitly."
            )

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(WORKING_CONTEXT.add(self.amount, other.amount), self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(WORKING_CONTEXT.subtract(self.amount, other.amount), self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def scaled(self, factor: Decimal) -> Money:
        return Money(WORKING_CONTEXT.multiply(self.amount, factor), self.currency)

    def quantized(self, exponent: int | None = None) -> Decimal:
        """Round to minor units for presentation or reconciliation."""
        places = amount_exponent(self.currency) if exponent is None else exponent
        return self.amount.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)

    def minor_units(self, exponent: int | None = None) -> int:
        places = amount_exponent(self.currency) if exponent is None else exponent
        return int(self.quantized(places).scaleb(places))

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    def __str__(self) -> str:
        return f"{self.quantized()} {self.currency}"


@dataclass(frozen=True, slots=True)
class MoneySum:
    """A total, and how much of the input it actually covers.

    ``sum(x or 0 for x in ...)`` is the single most common way this engine
    could lie: it turns "we could not price 40% of this" into a confident
    number. A sum over anything unpriced is a lower bound and says so in
    a field.
    """

    total: Money | None
    counted: int
    missing: int

    @property
    def is_lower_bound(self) -> bool:
        return self.missing > 0


def sum_money(items: Iterable[Money | None], currency: str) -> MoneySum:
    """Add up amounts, counting what could not be priced.

    Returns ``total=None`` only when nothing at all was priced -- which
    is different from a total of zero.
    """
    currency = validate_currency(currency)
    running = Decimal(0)
    counted = 0
    missing = 0
    for item in items:
        if item is None:
            missing += 1
            continue
        if item.currency != currency:
            raise CurrencyMismatchError(
                f"sum_money was given {item.currency} while summing {currency}."
            )
        running = WORKING_CONTEXT.add(running, item.amount)
        counted += 1
    return MoneySum(
        total=Money(running, currency) if counted else None,
        counted=counted,
        missing=missing,
    )


@dataclass(frozen=True, slots=True)
class FxRate:
    """One conversion, with the date and source that make it reproducible."""

    base: str
    quote: str
    rate: Decimal
    as_of: datetime
    source: str


@dataclass(frozen=True, slots=True)
class MultiCurrencyTotal:
    """Totals per currency, and a converted figure only if one is possible.

    A currency with no rate stays in ``by_currency`` and is named in
    ``unconvertible``. It is never dropped to make the grand total exist.
    """

    by_currency: Mapping[str, Money]
    converted: Money | None
    fx_rates_used: tuple[FxRate, ...]
    unconvertible: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return self.converted is not None and not self.unconvertible


def total_multi_currency(
    items: Sequence[Money],
    *,
    target: str | None = None,
    fx: Sequence[FxRate] = (),
) -> MultiCurrencyTotal:
    """Group by currency, converting only where a rate was supplied.

    A converted total without a stated FX as-of date is not
    reproducible: the same report re-run tomorrow silently re-prices
    history.
    """
    buckets: dict[str, Money] = {}
    for item in items:
        existing = buckets.get(item.currency)
        buckets[item.currency] = item if existing is None else existing + item

    if target is None:
        return MultiCurrencyTotal(
            by_currency=dict(sorted(buckets.items())),
            converted=None,
            fx_rates_used=(),
            unconvertible=tuple(sorted(buckets)),
        )

    target = validate_currency(target)
    lookup = {(rate.base, rate.quote): rate for rate in fx}
    running = Decimal(0)
    used: list[FxRate] = []
    unconvertible: list[str] = []

    for currency, money in sorted(buckets.items()):
        if currency == target:
            running = WORKING_CONTEXT.add(running, money.amount)
            continue
        rate = lookup.get((currency, target))
        if rate is None:
            unconvertible.append(currency)
            continue
        running = WORKING_CONTEXT.add(running, WORKING_CONTEXT.multiply(money.amount, rate.rate))
        used.append(rate)

    return MultiCurrencyTotal(
        by_currency=dict(sorted(buckets.items())),
        converted=Money(running, target),
        fx_rates_used=tuple(used),
        unconvertible=tuple(unconvertible),
    )


@dataclass(frozen=True, slots=True)
class SplitOutcome:
    """A total divided into parts that still add up to it.

    ``exact`` is returned rather than asserted: an assertion turns a data
    problem into a 500, and a caller can render a residual.
    """

    parts: Mapping[str, Money]
    exponent: int
    residual_minor_units: int

    @property
    def exact(self) -> bool:
        return self.residual_minor_units == 0


def split_money(
    total: Money, weights: Mapping[str, Decimal], *, exponent: int | None = None
) -> SplitOutcome:
    """Divide *total* by *weights* using largest remainder.

    Rounding each part independently drifts by up to n/2 minor units and
    the report stops footing against the invoice -- but with three
    fixture rows it always foots, so the test stays green. Largest
    remainder makes the sum exact by construction, in integer minor
    units.

    Raises:
        ValueError: On no targets, a negative weight, or a zero weight
            total. Each would produce a plausible-looking split that is
            arithmetically valid and economically meaningless.
    """
    if not weights:
        raise ValueError("Cannot split a total across no targets.")
    negatives = sorted(key for key, weight in weights.items() if weight < 0)
    if negatives:
        raise ValueError(
            f"Negative weights for {negatives}: a negative share yields negative "
            "allocations whose sum still equals the total, so the invariant check "
            "passes on nonsense."
        )
    denominator = sum(weights.values(), Decimal(0))
    if denominator == 0:
        raise ValueError(
            "The weights sum to zero; there is no proportional split. Falling back "
            "to an even split would fabricate the entire answer."
        )

    places = amount_exponent(total.currency) if exponent is None else exponent
    minor_total = total.minor_units(places)
    step = Decimal(1).scaleb(-places)

    raw: dict[str, Decimal] = {}
    base: dict[str, int] = {}
    for key, weight in weights.items():
        value = WORKING_CONTEXT.divide(
            WORKING_CONTEXT.multiply(Decimal(minor_total), weight), denominator
        )
        raw[key] = value
        base[key] = int(value.to_integral_value(rounding="ROUND_FLOOR"))

    remainder = minor_total - sum(base.values())
    # Ascending key breaks ties, so the same input always distributes the
    # same spare minor units -- an engine that hands the extra cent to a
    # different project on a re-run is not auditable.
    order = sorted(raw, key=lambda key: (-(raw[key] - base[key]), key))
    for key in order[: max(0, remainder)]:
        base[key] += 1

    parts = {
        key: Money(WORKING_CONTEXT.multiply(Decimal(units), step), total.currency)
        for key, units in base.items()
    }
    assigned = sum(base.values())
    return SplitOutcome(
        parts=parts,
        exponent=places,
        residual_minor_units=minor_total - assigned,
    )


def apply_minimum_increment(quantity: Decimal, increment: Decimal | None) -> Decimal:
    """Round a quantity up to a billing increment, when one is declared.

    ``None`` is the default because applying an increment the contract
    does not specify overcharges every line.
    """
    if increment is None:
        return quantity
    if increment <= 0:
        raise ValueError(f"A billing increment must be positive; got {increment}.")
    steps = WORKING_CONTEXT.divide(quantity, increment).to_integral_value(rounding=ROUND_CEILING)
    return WORKING_CONTEXT.multiply(steps, increment)


__all__ = [
    "AMOUNT_EXPONENT",
    "RATE_MIN_DP",
    "WORKING_CONTEXT",
    "CurrencyMismatchError",
    "FxRate",
    "Money",
    "MoneySum",
    "MultiCurrencyTotal",
    "SplitOutcome",
    "amount_exponent",
    "apply_minimum_increment",
    "split_money",
    "sum_money",
    "total_multi_currency",
    "validate_currency",
]
