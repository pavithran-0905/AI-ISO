"""Attribution, allocation, rollups, and unit economics.

The central arithmetic, stated once because everything here follows from
it: with total ``T`` split into attributed ``A`` and unattributed ``U``, a
project's true share lies between ``cost_i / T`` and ``(cost_i + U) / T``,
so the interval is **exactly ``U / T`` wide**. At 30% unattributed, every
project's share is a thirty-percentage-point-wide band, and any ranking
whose gaps are narrower than that is not supported by the data.

That is not a footnote. It is a returned field, because reporting the
attributed 70% as "the total" understates every project's true share by
up to 1/0.7 and nothing downstream can recover the error.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from app.cost.enums import (
    AllocationCaveat,
    AllocationFailure,
    AllocationMethod,
    ReportStatus,
    UnattributedReason,
    UnitCostUnavailable,
)
from app.cost.money import (
    WORKING_CONTEXT,
    CurrencyMismatchError,
    Money,
    split_money,
)

MATERIALLY_UNATTRIBUTED = Decimal("0.05")
"""Advisory threshold on the unattributed fraction. Five points because
that *is* the share-interval width, and it is narrower than the gaps
between projects that anyone acts on."""

DOMINANT_CONSUMER_SHARE = Decimal("0.90")
"""Above this, a "shared" cost is really direct and wants attributing
rather than allocating."""


@dataclass(frozen=True, slots=True)
class Dimensions:
    """The one owner tuple a usage record resolves to.

    Every record produces exactly one of these, and department and
    organization views are *projections* of it. Re-matching rules per
    level is how a resource ends up counted in two departments and the
    department totals exceed the organization total.
    """

    organization_id: str
    department_id: str | None = None
    project_id: str | None = None
    environment: str | None = None
    service: str | None = None

    def project_to_department(self) -> Dimensions:
        return Dimensions(organization_id=self.organization_id, department_id=self.department_id)

    def project_to_organization(self) -> Dimensions:
        return Dimensions(organization_id=self.organization_id)


@dataclass(frozen=True, slots=True)
class ShareBounds:
    """What fraction of the total a cost could be responsible for.

    The width is the unattributed fraction, exactly. A point estimate
    here would be a fabrication dressed as precision.
    """

    lower: Decimal
    upper: Decimal

    @property
    def is_exact(self) -> bool:
        return self.lower == self.upper

    @property
    def width(self) -> Decimal:
        return self.upper - self.lower


def share_bounds(cost: Money, total: Money, unattributed: Money) -> ShareBounds:
    """Bounds on one cost's share of a total.

    Raises:
        CurrencyMismatchError: On mixed currencies, which would make the
            ratio meaningless rather than merely wrong.
    """
    if not (cost.currency == total.currency == unattributed.currency):
        raise CurrencyMismatchError(
            "Share bounds need one currency; got "
            f"{cost.currency}, {total.currency}, {unattributed.currency}."
        )
    if total.amount == 0:
        return ShareBounds(lower=Decimal(0), upper=Decimal(0))
    lower = WORKING_CONTEXT.divide(cost.amount, total.amount)
    upper = WORKING_CONTEXT.divide(
        WORKING_CONTEXT.add(cost.amount, unattributed.amount), total.amount
    )
    return ShareBounds(lower=lower, upper=upper)


@dataclass(frozen=True, slots=True)
class CoverageStatement:
    """Everything that qualifies a cost total, in one place."""

    attributed_cost: Money
    unattributed_cost: Money
    unattributed_by_reason: Mapping[UnattributedReason, Money]
    unpriced_quantity_by_meter: Mapping[str, Decimal]
    observed_fraction: Decimal | None
    duplicates_dropped: int
    conflicting_duplicates: int

    @property
    def total_cost(self) -> Money:
        """Unattributed cost is *inside* the headline number."""
        return self.attributed_cost + self.unattributed_cost

    @property
    def unattributed_fraction(self) -> Decimal:
        total = self.total_cost
        if total.amount == 0:
            return Decimal(0)
        return WORKING_CONTEXT.divide(self.unattributed_cost.amount, total.amount)

    @property
    def total_is_lower_bound(self) -> bool:
        """Unpriced usage is a *quantity*, never money.

        Adding a fabricated price for it is exactly the failure being
        prevented, so it stays out of the total and makes the total a
        lower bound instead.
        """
        return bool(self.unpriced_quantity_by_meter)

    @property
    def materially_unattributed(self) -> bool:
        return self.unattributed_fraction >= MATERIALLY_UNATTRIBUTED

    @property
    def report_status(self) -> ReportStatus:
        complete = (
            self.unattributed_cost.is_zero
            and not self.unpriced_quantity_by_meter
            and self.observed_fraction == Decimal(1)
        )
        return ReportStatus.COMPLETE if complete else ReportStatus.PARTIAL


@dataclass(frozen=True, slots=True)
class AllocationOutcome:
    """A spread of shared cost, or a refusal to spread it."""

    allocated: Mapping[str, Money] | None
    unallocated: Money
    method: AllocationMethod
    driver_meter: str | None
    driver_totals: Mapping[str, Decimal]
    caveats: tuple[AllocationCaveat, ...]
    failure: AllocationFailure | None
    exact: bool


def allocate_shared(
    shared: Money,
    drivers: Mapping[str, Decimal],
    *,
    method: AllocationMethod,
    driver_meter: str | None = None,
    min_driver_base: Decimal = Decimal(0),
    driver_period_matches: bool = True,
    driver_includes_allocated_cost: bool = False,
    exponent: int | None = None,
) -> AllocationOutcome:
    """Spread a shared cost across consumers, or decline with a reason.

    Never automatic: unattributed cost is not silently spread, because
    spreading *is* allocation and allocation is a policy the caller opts
    into.

    A zero driver total is refused rather than falling back to an even
    split -- the fallback fabricates the whole answer while looking like
    a policy.
    """
    if method is AllocationMethod.NONE:
        return _allocation_failure(shared, method, driver_meter, drivers, None)
    if not drivers:
        return _allocation_failure(
            shared, method, driver_meter, drivers, AllocationFailure.NO_TARGETS
        )
    if any(weight < 0 for weight in drivers.values()):
        return _allocation_failure(
            shared, method, driver_meter, drivers, AllocationFailure.NEGATIVE_DRIVER
        )

    weights = (
        {key: Decimal(1) for key in drivers} if method is AllocationMethod.EVEN else dict(drivers)
    )
    base = sum(weights.values(), Decimal(0))
    if base == 0:
        return _allocation_failure(
            shared, method, driver_meter, drivers, AllocationFailure.ZERO_DRIVER_TOTAL
        )

    outcome = split_money(shared, weights, exponent=exponent)
    caveats: list[AllocationCaveat] = []
    driver_base = sum(drivers.values(), Decimal(0))
    if driver_base < min_driver_base:
        caveats.append(AllocationCaveat.SMALL_DRIVER_BASE)
    if not driver_period_matches:
        caveats.append(AllocationCaveat.DRIVER_PERIOD_MISMATCH)
    if driver_includes_allocated_cost:
        caveats.append(AllocationCaveat.DRIVER_INCLUDES_ALLOCATED_COST)
    if method is AllocationMethod.BY_DRIVER and driver_base > 0:
        top = max(drivers.values())
        if WORKING_CONTEXT.divide(top, driver_base) >= DOMINANT_CONSUMER_SHARE:
            caveats.append(AllocationCaveat.SINGLE_CONSUMER_DOMINATES)

    return AllocationOutcome(
        allocated=outcome.parts,
        unallocated=Money.measured_zero(shared.currency),
        method=method,
        driver_meter=driver_meter,
        driver_totals=dict(drivers),
        caveats=tuple(caveats),
        failure=None,
        exact=outcome.exact,
    )


def _allocation_failure(
    shared: Money,
    method: AllocationMethod,
    driver_meter: str | None,
    drivers: Mapping[str, Decimal],
    failure: AllocationFailure | None,
) -> AllocationOutcome:
    """A refusal that still keeps the money in the total."""
    return AllocationOutcome(
        allocated=None,
        unallocated=shared,
        method=method,
        driver_meter=driver_meter,
        driver_totals=dict(drivers),
        caveats=(),
        failure=failure,
        exact=False,
    )


def allocation_order(steps: Mapping[str, Sequence[str]]) -> tuple[str, ...] | None:
    """Topologically order multi-step allocations, or ``None`` on a cycle.

    Department to project to sub-project is legitimate; a cycle inflates
    monotonically on every re-run, which looks like genuine cost growth.
    """
    permanent: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return False
        if node in done:
            return True
        visiting.add(node)
        for downstream in steps.get(node, ()):
            if not visit(downstream):
                return False
        visiting.discard(node)
        done.add(node)
        permanent.append(node)
        return True

    for node in sorted(steps):
        if not visit(node):
            return None
    return tuple(permanent)


@dataclass(frozen=True, slots=True)
class ProjectCost:
    """Direct and allocated cost, kept apart permanently.

    Merged into one field, next quarter someone computes cost-per-document
    from a number containing a slice of the CI cluster, and there is no
    way to back it out.
    """

    dimensions: Dimensions
    direct_cost: Money
    allocated_cost: Money

    @property
    def total_cost(self) -> Money:
        return self.direct_cost + self.allocated_cost


@dataclass(frozen=True, slots=True)
class RollupConsistency:
    """Whether the hierarchy adds up, and by how much it does not.

    Checked and returned rather than asserted: an assertion turns a data
    problem into a 500, while a residual turns it into a visible caveat
    on a report the user can still read.
    """

    org_total: Money
    department_total: Money
    project_total: Money
    residual_departments: Money
    residual_projects: Money

    @property
    def org_equals_departments(self) -> bool:
        return self.residual_departments.is_zero

    @property
    def org_equals_projects(self) -> bool:
        return self.residual_projects.is_zero


def check_rollup(costs: Sequence[ProjectCost], *, currency: str) -> RollupConsistency:
    """Compare the organization total against its projections."""
    zero = Money.measured_zero(currency)
    org = zero
    by_department: dict[str | None, Money] = {}
    by_project: dict[str | None, Money] = {}

    for entry in costs:
        org = org + entry.total_cost
        department = entry.dimensions.department_id
        project = entry.dimensions.project_id
        # A project whose department is unknown gets its own bucket rather
        # than being folded in with genuinely-other departments.
        by_department[department] = by_department.get(department, zero) + entry.total_cost
        by_project[project] = by_project.get(project, zero) + entry.total_cost

    department_total = sum(by_department.values(), zero)
    project_total = sum(by_project.values(), zero)
    return RollupConsistency(
        org_total=org,
        department_total=department_total,
        project_total=project_total,
        residual_departments=org - department_total,
        residual_projects=org - project_total,
    )


@dataclass(frozen=True, slots=True)
class WorkVolume:
    """How much work was done, with "not measured" distinct from "zero"."""

    meter: str
    count: Decimal | None
    dimensions: Dimensions
    observed_fraction: Decimal | None = None


@dataclass(frozen=True, slots=True)
class UnitEconomics:
    """Cost per unit of work, or precisely why there is no such figure."""

    numerator: Money
    denominator: Decimal | None
    denominator_meter: str
    value: Decimal | None
    unavailable: UnitCostUnavailable | None
    numerator_is_lower_bound: bool
    denominator_coverage: Decimal | None
    fixed_component: Money | None = None
    variable_component: Money | None = None


def unit_cost(
    cost: Money,
    volume: WorkVolume,
    *,
    scope: Dimensions,
    numerator_is_lower_bound: bool = False,
    fixed_component: Money | None = None,
    min_coverage: Decimal = Decimal("0.8"),
) -> UnitEconomics:
    """Cost divided by work, with every way that can fail named.

    A zero denominator returns ``value=None`` with the numerator still
    populated. Both alternatives lie: ``0.0`` says the work was free, and
    a huge sentinel says something absurd. What is true is "$412 of spend,
    zero requests" -- idle spend, the single most actionable cost finding
    there is, and destroyed by either default.

    Scope equality is enforced. Cost summed over prod and staging divided
    by prod-only request counts is wrong by a factor nobody can see, and
    it is the classic unit-economics bug.
    """
    variable = None if fixed_component is None else cost - fixed_component

    def result(value: Decimal | None, unavailable: UnitCostUnavailable | None) -> UnitEconomics:
        return UnitEconomics(
            numerator=cost,
            denominator=volume.count,
            denominator_meter=volume.meter,
            value=value,
            unavailable=unavailable,
            numerator_is_lower_bound=numerator_is_lower_bound,
            denominator_coverage=volume.observed_fraction,
            fixed_component=fixed_component,
            variable_component=variable,
        )

    if volume.dimensions != scope:
        return result(None, UnitCostUnavailable.SCOPE_MISMATCH)
    if volume.count is None:
        return result(None, UnitCostUnavailable.DENOMINATOR_NOT_MEASURED)
    if volume.count == 0:
        return result(None, UnitCostUnavailable.ZERO_DENOMINATOR)
    if volume.observed_fraction is not None and volume.observed_fraction < min_coverage:
        return result(None, UnitCostUnavailable.DENOMINATOR_PARTIAL_COVERAGE)

    value = WORKING_CONTEXT.divide(cost.amount, volume.count)
    if numerator_is_lower_bound:
        return result(value, UnitCostUnavailable.NUMERATOR_PARTIAL)
    return result(value, None)


@dataclass(frozen=True, slots=True)
class CostVariance:
    """Why a cost changed between two periods.

    Volume and price effects are separated because they need different
    people: "we used 40% more" goes to engineering and "the price rose
    40%" goes to procurement. A single delta sends both to neither.
    """

    previous: Money
    current: Money
    delta: Money
    volume_effect: Money | None
    price_effect: Money | None
    mix_effect: Money | None
    unexplained: Money


def decompose_variance(
    *,
    previous_cost: Money,
    current_cost: Money,
    previous_quantity: Decimal | None,
    current_quantity: Decimal | None,
    previous_rate: Decimal | None,
    current_rate: Decimal | None,
) -> CostVariance:
    """Split a cost change into volume, price, and the rest.

    Uses the standard decomposition with the mix term carried explicitly
    rather than folded into one of the others:
    ``dQ*p0`` volume, ``Q0*dp`` price, ``dQ*dp`` mix. Whatever those three
    fail to explain is returned as ``unexplained`` instead of being
    absorbed, because a residual is evidence that something outside the
    model moved.
    """
    delta = current_cost - previous_cost
    currency = current_cost.currency
    if None in (previous_quantity, current_quantity, previous_rate, current_rate):
        return CostVariance(
            previous=previous_cost,
            current=current_cost,
            delta=delta,
            volume_effect=None,
            price_effect=None,
            mix_effect=None,
            unexplained=delta,
        )

    quantity_before = previous_quantity or Decimal(0)
    quantity_after = current_quantity or Decimal(0)
    rate_before = previous_rate or Decimal(0)
    rate_after = current_rate or Decimal(0)

    delta_quantity = quantity_after - quantity_before
    delta_rate = rate_after - rate_before
    volume = Money(WORKING_CONTEXT.multiply(delta_quantity, rate_before), currency)
    price = Money(WORKING_CONTEXT.multiply(quantity_before, delta_rate), currency)
    mix = Money(WORKING_CONTEXT.multiply(delta_quantity, delta_rate), currency)

    explained = volume + price + mix
    return CostVariance(
        previous=previous_cost,
        current=current_cost,
        delta=delta,
        volume_effect=volume,
        price_effect=price,
        mix_effect=mix,
        unexplained=delta - explained,
    )


@dataclass(frozen=True, slots=True)
class CostReport:
    """A period's cost with its coverage and its per-project detail."""

    period_label: str
    currency: str
    coverage: CoverageStatement
    projects: tuple[ProjectCost, ...] = field(default_factory=tuple)

    @property
    def total_cost(self) -> Money:
        return self.coverage.total_cost

    @property
    def status(self) -> ReportStatus:
        return self.coverage.report_status

    def bounds_for(self, project: ProjectCost) -> ShareBounds:
        return share_bounds(project.total_cost, self.total_cost, self.coverage.unattributed_cost)

    def ranking_is_supported(self, gap: Decimal) -> bool:
        """Whether a ranking gap survives the unattributed uncertainty."""
        return gap > self.coverage.unattributed_fraction


__all__ = [
    "DOMINANT_CONSUMER_SHARE",
    "MATERIALLY_UNATTRIBUTED",
    "AllocationOutcome",
    "CostReport",
    "CostVariance",
    "CoverageStatement",
    "Dimensions",
    "ProjectCost",
    "RollupConsistency",
    "ShareBounds",
    "UnitEconomics",
    "WorkVolume",
    "allocate_shared",
    "allocation_order",
    "check_rollup",
    "decompose_variance",
    "share_bounds",
    "unit_cost",
]
