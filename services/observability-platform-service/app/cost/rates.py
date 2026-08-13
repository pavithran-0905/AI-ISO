"""Rate cards, resolution, and the pricing formulas.

**A hard-coded price is wrong for five independent reasons**, and this
module exists to make each impossible. A constant cannot price usage that
straddles a price change. Deploying a new constant retroactively restates
last quarter, so a signed-off finance number becomes unreproducible and
nobody can tell whether the figure moved because usage grew or because
someone edited a literal. With one global constant every cost change is
100% volume effect, so a list-price rise is invisible and gets
investigated as a usage regression. Prices are not global -- negotiated
discounts, committed-use tiers, regions, environments and currencies all
vary. And a price is a finance-owned fact: auditing a chargeback should
not require reading a diff.

The sixth reason is the one that matters most here: a hard-coded rate
makes every unit test pass while making every report wrong, because the
fixture and the code share the constant.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from itertools import pairwise

from app.cost.enums import (
    ChargeShape,
    MonthBasis,
    RateCardIssue,
    RateUnavailable,
    TierMode,
)
from app.cost.money import (
    RATE_MIN_DP,
    WORKING_CONTEXT,
    Money,
    apply_minimum_increment,
    validate_currency,
)

SECONDS_PER_FIXED_MONTH = Decimal(2_628_000)
"""730 hours -- the provider convention. Assuming 30 days (2,592,000)
instead divides byte-seconds by a smaller month and so **overstates**
every storage figure by 2628000/2592000 - 1 = 1.39%, permanently and
invisibly."""


@dataclass(frozen=True, slots=True)
class Tier:
    """One band of a tiered price.

    ``up_to`` is ``None`` for the final, unbounded band.
    """

    up_to: Decimal | None
    unit_amount: Decimal


@dataclass(frozen=True, slots=True)
class Rate:
    """What one unit of one meter costs."""

    meter: str
    unit: str
    currency: str
    unit_amount: Decimal | None = None
    tiers: tuple[Tier, ...] = ()
    tier_mode: TierMode | None = None
    charge_shape: ChargeShape = ChargeShape.PER_UNIT
    minimum_increment: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "currency", validate_currency(self.currency))


@dataclass(frozen=True, slots=True)
class UnitConversion:
    """A declared factor between two unit strings.

    Declared, never inferred. ``token`` to ``1K-token`` is 1000x, ``GB``
    to ``GiB`` is 1.074x, ``second`` to ``hour`` is 3600x -- each
    produces a plausible number, and a fixture that shares the code's
    assumption cannot detect any of them.
    """

    from_unit: str
    to_unit: str
    factor: Decimal


@dataclass(frozen=True, slots=True)
class RateCard:
    """A priced catalogue valid over a stated interval."""

    card_id: str
    version: str
    effective_from: datetime
    effective_to: datetime | None
    rates: Mapping[str, Rate]
    month_basis: MonthBasis = MonthBasis.FIXED_730H
    checksum: str | None = None
    scope: Mapping[str, str] = field(default_factory=dict)

    def covers(self, instant: datetime) -> bool:
        if instant < self.effective_from:
            return False
        return self.effective_to is None or instant < self.effective_to


@dataclass(frozen=True, slots=True)
class RateCardSet:
    """Every card that might apply, with conversions between units."""

    cards: tuple[RateCard, ...]
    conversions: tuple[UnitConversion, ...] = ()

    def conversion_factor(self, from_unit: str, to_unit: str) -> Decimal | None:
        """The declared factor, or ``None``. Never a guess."""
        if from_unit == to_unit:
            return Decimal(1)
        for conversion in self.conversions:
            if conversion.from_unit == from_unit and conversion.to_unit == to_unit:
                return conversion.factor
            if conversion.from_unit == to_unit and conversion.to_unit == from_unit:
                return WORKING_CONTEXT.divide(Decimal(1), conversion.factor)
        return None

    def boundaries_within(self, start: datetime, end: datetime) -> tuple[datetime, ...]:
        """Every effective-from inside ``[start, end)``.

        These are where a usage record must be split so each part is
        priced by the card that was actually in force.
        """
        return tuple(
            sorted(
                {card.effective_from for card in self.cards if start < card.effective_from < end}
            )
        )


@dataclass(frozen=True, slots=True)
class RateResolution:
    """Which rate applies, or precisely why none does."""

    rate: Rate | None
    card_id: str | None = None
    card_version: str | None = None
    card_checksum: str | None = None
    unavailable: RateUnavailable | None = None


def resolve_rate(cards: RateCardSet, meter: str, at: datetime) -> RateResolution:
    """Find the rate in force at the instant of the usage.

    By the instant, never "the newest card". Overlapping ranges are an
    error rather than a first-match: which card comes first depends on
    load order, and an engine whose answer changes across a config reload
    cannot be audited.
    """
    matching = [card for card in cards.cards if card.covers(at)]
    if not matching:
        return RateResolution(rate=None, unavailable=RateUnavailable.NO_CARD_FOR_INSTANT)
    if len(matching) > 1:
        return RateResolution(rate=None, unavailable=RateUnavailable.AMBIGUOUS_OVERLAPPING_CARDS)

    card = matching[0]
    rate = card.rates.get(meter)
    if rate is None:
        return RateResolution(
            rate=None,
            card_id=card.card_id,
            card_version=card.version,
            card_checksum=card.checksum,
            unavailable=RateUnavailable.METER_NOT_IN_CARD,
        )
    if rate.tiers and rate.tier_mode is None:
        return RateResolution(
            rate=None,
            card_id=card.card_id,
            card_version=card.version,
            card_checksum=card.checksum,
            unavailable=RateUnavailable.TIER_MODE_UNSPECIFIED,
        )
    return RateResolution(
        rate=rate,
        card_id=card.card_id,
        card_version=card.version,
        card_checksum=card.checksum,
    )


@dataclass(frozen=True, slots=True)
class CardIssue:
    """One problem found in a rate card set, with enough detail to fix it."""

    issue: RateCardIssue
    card_id: str | None
    meter: str | None
    detail: str


def _range_end(card: RateCard) -> str:
    """How a card's open or closed end reads in an issue message."""
    return card.effective_to.isoformat() if card.effective_to else "forever"


def validate_rate_card_set(
    cards: RateCardSet,
    *,
    period: tuple[datetime, datetime] | None = None,
    known_units: Sequence[str] = (),
) -> tuple[CardIssue, ...]:
    """Pure pre-flight over a card set.

    Runs before any pricing so a broken catalogue is a configuration
    error rather than a quietly wrong report.
    """
    issues: list[CardIssue] = []
    ordered = sorted(cards.cards, key=lambda card: (card.effective_from, card.card_id))

    for earlier, later in pairwise(ordered):
        if earlier.effective_to is None or earlier.effective_to > later.effective_from:
            issues.append(
                CardIssue(
                    issue=RateCardIssue.OVERLAPPING_EFFECTIVE_RANGES,
                    card_id=later.card_id,
                    meter=None,
                    detail=(
                        f"{earlier.card_id} runs to {_range_end(earlier)} but "
                        f"{later.card_id} starts at "
                        f"{later.effective_from.isoformat()}."
                    ),
                )
            )
        elif period is not None and earlier.effective_to < later.effective_from:
            issues.append(
                CardIssue(
                    issue=RateCardIssue.GAP_IN_COVERAGE,
                    card_id=later.card_id,
                    meter=None,
                    detail=(
                        f"Nothing prices usage between "
                        f"{earlier.effective_to.isoformat()} and "
                        f"{later.effective_from.isoformat()}."
                    ),
                )
            )

    currencies = {rate.currency for card in cards.cards for rate in card.rates.values()}
    if len(currencies) > 1:
        issues.append(
            CardIssue(
                issue=RateCardIssue.CURRENCY_INCONSISTENT,
                card_id=None,
                meter=None,
                detail=f"The set mixes {sorted(currencies)} with no conversion policy.",
            )
        )

    underflow = Decimal(1).scaleb(-RATE_MIN_DP)
    for card in cards.cards:
        for meter, rate in sorted(card.rates.items()):
            issues.extend(_rate_issues(card, meter, rate, underflow, known_units))

    return tuple(issues)


def _rate_issues(
    card: RateCard,
    meter: str,
    rate: Rate,
    underflow: Decimal,
    known_units: Sequence[str],
) -> list[CardIssue]:
    """Per-rate checks, split out to keep the set-level pass readable."""
    issues: list[CardIssue] = []
    amounts = [rate.unit_amount, *(tier.unit_amount for tier in rate.tiers)]
    for amount in amounts:
        if amount is not None and amount != 0 and abs(amount) < underflow:
            issues.append(
                CardIssue(
                    issue=RateCardIssue.RATE_UNDERFLOW,
                    card_id=card.card_id,
                    meter=meter,
                    detail=(
                        f"{amount} vanishes at {RATE_MIN_DP} decimal places; every "
                        "line priced with it would come out as exactly zero."
                    ),
                )
            )
            break

    if rate.tiers and rate.tier_mode is None:
        issues.append(
            CardIssue(
                issue=RateCardIssue.TIER_MODE_MISSING,
                card_id=card.card_id,
                meter=meter,
                detail=(
                    "Graduated and volume pricing give materially different totals "
                    "from the same inputs, so there is no safe default."
                ),
            )
        )

    boundaries = [tier.up_to for tier in rate.tiers]
    finite = [value for value in boundaries if value is not None]
    if finite != sorted(finite) or any(value is None for value in boundaries[:-1]):
        issues.append(
            CardIssue(
                issue=RateCardIssue.NON_MONOTONIC_TIERS,
                card_id=card.card_id,
                meter=meter,
                detail=f"Tier boundaries {boundaries} are not ascending with an open top.",
            )
        )

    if known_units and rate.unit not in known_units:
        issues.append(
            CardIssue(
                issue=RateCardIssue.UNKNOWN_UNIT,
                card_id=card.card_id,
                meter=meter,
                detail=f"Unit {rate.unit!r} is not declared by any meter.",
            )
        )
    return issues


@dataclass(frozen=True, slots=True)
class PricedQuantity:
    """A quantity priced by a rate, with the conversion made explicit."""

    cost: Money
    billable_quantity: Decimal
    converted_quantity: Decimal
    conversion_factor: Decimal


def price_quantity(
    quantity: Decimal, rate: Rate, *, conversion_factor: Decimal = Decimal(1)
) -> PricedQuantity:
    """Apply a rate to a quantity.

    Graduated charges each band's rate on the part of the quantity inside
    it; volume charges one band's rate on the whole quantity. The two are
    genuinely different contracts, which is why :class:`Rate` refuses to
    default one.

    Raises:
        ValueError: When a rate has neither a flat amount nor tiers, or
            has tiers without a mode -- both of which should have been
            caught by :func:`validate_rate_card_set` before any usage
            reached here.
    """
    converted = WORKING_CONTEXT.multiply(quantity, conversion_factor)
    billable = apply_minimum_increment(converted, rate.minimum_increment)

    if rate.tiers:
        if rate.tier_mode is None:
            raise ValueError(
                f"Rate for {rate.meter!r} has tiers but no tier_mode; graduated and "
                "volume pricing are different contracts."
            )
        amount = (
            _graduated(billable, rate.tiers)
            if rate.tier_mode is TierMode.GRADUATED
            else _volume(billable, rate.tiers)
        )
    elif rate.unit_amount is not None:
        amount = WORKING_CONTEXT.multiply(billable, rate.unit_amount)
    else:
        raise ValueError(f"Rate for {rate.meter!r} has neither a unit amount nor tiers.")

    return PricedQuantity(
        cost=Money(amount, rate.currency),
        billable_quantity=billable,
        converted_quantity=converted,
        conversion_factor=conversion_factor,
    )


def _graduated(quantity: Decimal, tiers: Sequence[Tier]) -> Decimal:
    """Sum of each tier's rate over the quantity falling inside that tier."""
    total = Decimal(0)
    previous = Decimal(0)
    for tier in tiers:
        ceiling = quantity if tier.up_to is None else min(quantity, tier.up_to)
        span = ceiling - previous
        if span > 0:
            total = WORKING_CONTEXT.add(total, WORKING_CONTEXT.multiply(span, tier.unit_amount))
        if tier.up_to is not None:
            previous = tier.up_to
            if quantity <= tier.up_to:
                break
    return total


def _volume(quantity: Decimal, tiers: Sequence[Tier]) -> Decimal:
    """One tier's rate applied to the whole quantity."""
    for tier in tiers:
        if tier.up_to is None or quantity <= tier.up_to:
            return WORKING_CONTEXT.multiply(quantity, tier.unit_amount)
    return WORKING_CONTEXT.multiply(quantity, tiers[-1].unit_amount)


def seconds_per_month(basis: MonthBasis, period_seconds: Decimal | None = None) -> Decimal:
    """How many seconds a "month" contains under the declared basis.

    Raises:
        ValueError: When a calendar basis is requested without the actual
            period length, rather than falling back to a fixed figure and
            mislabelling it.
    """
    if basis is MonthBasis.FIXED_730H:
        return SECONDS_PER_FIXED_MONTH
    if period_seconds is None:
        raise ValueError(
            "A calendar month basis needs the period length; substituting the "
            "fixed 730-hour figure would misprice by up to 1.4% under a label "
            "saying otherwise."
        )
    return period_seconds


__all__ = [
    "SECONDS_PER_FIXED_MONTH",
    "CardIssue",
    "PricedQuantity",
    "Rate",
    "RateCard",
    "RateCardSet",
    "RateResolution",
    "Tier",
    "UnitConversion",
    "price_quantity",
    "resolve_rate",
    "seconds_per_month",
    "validate_rate_card_set",
]
