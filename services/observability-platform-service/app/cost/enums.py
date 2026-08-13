"""Vocabulary for cost analytics.

Almost every member here exists because the numeric or boolean encoding
of the same idea loses a distinction that costs money. "Not measured" and
"measured as zero" are the recurring pair: one is a broken collector and
the other is an idle service, they land in different queues, and
``0`` cannot tell them apart.
"""

from __future__ import annotations

from enum import StrEnum


class CostSource(StrEnum):
    """Where a cost figure came from.

    An imported invoice line is authoritative and a metered estimate is
    not; mixing them without a label produces a report nobody can
    reconcile.
    """

    METERED = "metered"
    IMPORTED_INVOICE = "imported_invoice"
    ESTIMATED = "estimated"


class MeterBasis(StrEnum):
    """Whether a usage record describes an interval or an instant.

    Decides whether a record may be split at a price change. Prorating
    "1 request" across a boundary into 0.4 and 0.6 requests is
    arithmetically tidy and factually false.
    """

    CUMULATIVE_OVER_INTERVAL = "cumulative_over_interval"
    POINT_EVENT = "point_event"


class TierMode(StrEnum):
    """How tiered pricing accumulates.

    Graduated charges each tier's rate on the quantity falling inside it;
    volume charges one rate on the whole quantity. Identical inputs give
    materially different totals, so there is no default -- an unset value
    leaves the line unpriced rather than silently picking one.
    """

    GRADUATED = "graduated"
    VOLUME = "volume"


class ChargeShape(StrEnum):
    """Whether a rate is per-event or per-period.

    Needed because average cost per request falls as volume rises purely
    from fixed cost, so a cost-per-request line trending down reads as an
    efficiency win when nothing improved.
    """

    PER_UNIT = "per_unit"
    RECURRING = "recurring"


class MonthBasis(StrEnum):
    """What a "month" means when integrating storage.

    ``FIXED_730H`` is the provider convention (2,628,000 seconds).
    Assuming 30 days instead overstates every storage figure by 1.39%,
    permanently and invisibly, so this is declared on the card rather than
    chosen by the code.
    """

    FIXED_730H = "fixed_730h"
    CALENDAR = "calendar"


class RateUnavailable(StrEnum):
    """Why a usage line could not be priced."""

    NO_CARD_FOR_INSTANT = "no_card_for_instant"
    METER_NOT_IN_CARD = "meter_not_in_card"
    AMBIGUOUS_OVERLAPPING_CARDS = "ambiguous_overlapping_cards"
    """Two cards claim the same instant. An error rather than "pick the
    first": which one is first depends on load order, and an engine whose
    answer changes across a config reload is not auditable."""
    UNIT_MISMATCH_NO_CONVERSION = "unit_mismatch_no_conversion"
    TIER_MODE_UNSPECIFIED = "tier_mode_unspecified"


class RateCardIssue(StrEnum):
    """Pre-flight problems in a set of rate cards."""

    OVERLAPPING_EFFECTIVE_RANGES = "overlapping_effective_ranges"
    GAP_IN_COVERAGE = "gap_in_coverage"
    RATE_UNDERFLOW = "rate_underflow"
    """A non-zero rate that quantizes to zero. A per-token price of
    0.00000015 rounded to two decimal places is 0.00 -- every model-usage
    cost in the platform becomes exactly zero and every test still
    passes."""
    NON_MONOTONIC_TIERS = "non_monotonic_tiers"
    TIER_MODE_MISSING = "tier_mode_missing"
    CURRENCY_INCONSISTENT = "currency_inconsistent"
    UNKNOWN_UNIT = "unknown_unit"


class UnattributedReason(StrEnum):
    """Why a cost has no owner."""

    NO_LABELS = "no_labels"
    UNKNOWN_RESOURCE = "unknown_resource"
    SHARED_INFRASTRUCTURE = "shared_infrastructure"
    LABEL_VALUE_UNMAPPED = "label_value_unmapped"


class AllocationMethod(StrEnum):
    """How shared cost is spread, when spreading is asked for at all."""

    EVEN = "even"
    BY_DRIVER = "by_driver"
    NONE = "none"


class AllocationCaveat(StrEnum):
    """Reasons to distrust an allocation that still went ahead.

    Data rather than prose so a report can filter on them.
    """

    DRIVER_NOT_CAUSAL = "driver_not_causal"
    DRIVER_PERIOD_MISMATCH = "driver_period_mismatch"
    DRIVER_COVERAGE_PARTIAL = "driver_coverage_partial"
    DRIVER_INCLUDES_ALLOCATED_COST = "driver_includes_allocated_cost"
    SINGLE_CONSUMER_DOMINATES = "single_consumer_dominates"
    """One key receives nearly everything, at which point the cost is
    really direct and should be attributed rather than allocated."""
    SMALL_DRIVER_BASE = "small_driver_base"
    """Allocating a large sum across a handful of driver units is
    arithmetic, not economics."""


class AllocationFailure(StrEnum):
    """Reasons an allocation was refused outright."""

    ZERO_DRIVER_TOTAL = "zero_driver_total"
    """Refused rather than falling back to an even split, which
    fabricates the entire answer while looking like a policy."""
    NEGATIVE_DRIVER = "negative_driver"
    """A negative weight produces negative allocations whose sum still
    equals the total, so the invariant check passes on nonsense."""
    NO_TARGETS = "no_targets"
    CYCLIC_ALLOCATION = "cyclic_allocation"
    MIXED_CURRENCY = "mixed_currency"


class UnitCostUnavailable(StrEnum):
    """Why a cost-per-unit figure does not exist."""

    ZERO_DENOMINATOR = "zero_denominator"
    """Cost with no work done. Returning 0.0 says the work was free and
    returning infinity says something absurd; what is true is "$412 of
    spend, zero requests", which is idle spend -- the single most
    actionable cost finding there is."""
    DENOMINATOR_NOT_MEASURED = "denominator_not_measured"
    """A different queue entirely from ZERO_DENOMINATOR: one is a broken
    collector, the other is an idle service."""
    DENOMINATOR_PARTIAL_COVERAGE = "denominator_partial_coverage"
    NUMERATOR_PARTIAL = "numerator_partial"
    SCOPE_MISMATCH = "scope_mismatch"
    """Cost summed over prod and staging divided by prod-only request
    counts is wrong by a factor nobody can see."""
    MIXED_CURRENCY = "mixed_currency"
    NO_BASELINE = "no_baseline"


class ReportStatus(StrEnum):
    """Whether a cost report is complete enough to act on."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class CostChangeDriver(StrEnum):
    """What moved a cost between two periods.

    Kept separate because "we used 40% more" and "the price went up 40%"
    need different people to act.
    """

    VOLUME = "volume"
    PRICE = "price"
    MIX = "mix"
    NEW_RESOURCE = "new_resource"
    REMOVED_RESOURCE = "removed_resource"
    UNEXPLAINED = "unexplained"


__all__ = [
    "AllocationCaveat",
    "AllocationFailure",
    "AllocationMethod",
    "ChargeShape",
    "CostChangeDriver",
    "CostSource",
    "MeterBasis",
    "MonthBasis",
    "RateCardIssue",
    "RateUnavailable",
    "ReportStatus",
    "TierMode",
    "UnattributedReason",
    "UnitCostUnavailable",
]
