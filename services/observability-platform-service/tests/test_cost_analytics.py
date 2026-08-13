"""Tests for app.cost.analytics -- attribution, allocation, unit economics."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.cost.analytics import (
    CoverageStatement,
    Dimensions,
    ProjectCost,
    WorkVolume,
    allocate_shared,
    allocation_order,
    check_rollup,
    decompose_variance,
    share_bounds,
    unit_cost,
)
from app.cost.enums import (
    AllocationFailure,
    AllocationMethod,
    ReportStatus,
    UnitCostUnavailable,
)
from app.cost.money import CurrencyMismatchError, Money


def _money(amount: str, currency: str = "USD") -> Money:
    return Money.of(amount, currency)


class TestDimensions:
    def test_project_to_department(self) -> None:
        dims = Dimensions(organization_id="org1", department_id="dept1", project_id="proj1")
        reduced = dims.project_to_department()
        assert reduced.department_id == "dept1"
        assert reduced.project_id is None

    def test_project_to_organization(self) -> None:
        dims = Dimensions(organization_id="org1", department_id="dept1")
        reduced = dims.project_to_organization()
        assert reduced.department_id is None


class TestShareBounds:
    def test_currency_mismatch_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            share_bounds(_money("1"), _money("10", "EUR"), _money("0"))

    def test_zero_total(self) -> None:
        bounds = share_bounds(_money("0"), _money("0"), _money("0"))
        assert bounds.lower == Decimal(0)
        assert bounds.upper == Decimal(0)

    def test_bounds_width_equals_unattributed_fraction(self) -> None:
        bounds = share_bounds(_money("30"), _money("100"), _money("10"))
        assert bounds.lower == Decimal("0.3")
        assert bounds.upper == Decimal("0.4")
        assert bounds.width == Decimal("0.1")
        assert not bounds.is_exact

    def test_exact_when_no_unattributed(self) -> None:
        bounds = share_bounds(_money("30"), _money("100"), _money("0"))
        assert bounds.is_exact


class TestCoverageStatement:
    def _statement(
        self,
        *,
        attributed: str,
        unattributed: str,
        unpriced: bool = False,
        observed: Decimal | None = Decimal(1),
    ) -> CoverageStatement:
        return CoverageStatement(
            attributed_cost=_money(attributed),
            unattributed_cost=_money(unattributed),
            unattributed_by_reason={},
            unpriced_quantity_by_meter={"tokens": Decimal(5)} if unpriced else {},
            observed_fraction=observed,
            duplicates_dropped=0,
            conflicting_duplicates=0,
        )

    def test_total_cost_includes_unattributed(self) -> None:
        statement = self._statement(attributed="70", unattributed="30")
        assert statement.total_cost.amount == Decimal("100")

    def test_unattributed_fraction_zero_total(self) -> None:
        statement = self._statement(attributed="0", unattributed="0")
        assert statement.unattributed_fraction == Decimal(0)

    def test_unattributed_fraction(self) -> None:
        statement = self._statement(attributed="90", unattributed="10")
        assert statement.unattributed_fraction == Decimal("0.1")

    def test_total_is_lower_bound_when_unpriced(self) -> None:
        statement = self._statement(attributed="90", unattributed="10", unpriced=True)
        assert statement.total_is_lower_bound

    def test_materially_unattributed(self) -> None:
        statement = self._statement(attributed="90", unattributed="10")
        assert statement.materially_unattributed

    def test_report_status_complete(self) -> None:
        statement = self._statement(attributed="100", unattributed="0")
        assert statement.report_status is ReportStatus.COMPLETE

    def test_report_status_partial_due_to_unattributed(self) -> None:
        statement = self._statement(attributed="90", unattributed="10")
        assert statement.report_status is ReportStatus.PARTIAL

    def test_report_status_partial_due_to_coverage(self) -> None:
        statement = self._statement(attributed="100", unattributed="0", observed=Decimal("0.5"))
        assert statement.report_status is ReportStatus.PARTIAL


class TestAllocateShared:
    def test_method_none_refuses(self) -> None:
        result = allocate_shared(_money("100"), {"a": Decimal(1)}, method=AllocationMethod.NONE)
        assert result.allocated is None
        assert result.unallocated.amount == Decimal("100")

    def test_no_targets_refuses(self) -> None:
        result = allocate_shared(_money("100"), {}, method=AllocationMethod.EVEN)
        assert result.failure is AllocationFailure.NO_TARGETS

    def test_negative_driver_refuses(self) -> None:
        result = allocate_shared(
            _money("100"), {"a": Decimal(-1), "b": Decimal(2)}, method=AllocationMethod.BY_DRIVER
        )
        assert result.failure is AllocationFailure.NEGATIVE_DRIVER

    def test_zero_driver_total_refuses(self) -> None:
        result = allocate_shared(
            _money("100"), {"a": Decimal(0), "b": Decimal(0)}, method=AllocationMethod.BY_DRIVER
        )
        assert result.failure is AllocationFailure.ZERO_DRIVER_TOTAL

    def test_even_split(self) -> None:
        result = allocate_shared(
            _money("100"), {"a": Decimal(1), "b": Decimal(1)}, method=AllocationMethod.EVEN
        )
        assert result.allocated is not None
        assert result.exact
        assert result.allocated["a"].amount == Decimal("50.00")

    def test_by_driver_split(self) -> None:
        result = allocate_shared(
            _money("100"), {"a": Decimal(3), "b": Decimal(1)}, method=AllocationMethod.BY_DRIVER
        )
        assert result.allocated is not None
        assert result.allocated["a"].amount == Decimal("75.00")

    def test_small_driver_base_caveat(self) -> None:
        result = allocate_shared(
            _money("100"),
            {"a": Decimal(1)},
            method=AllocationMethod.BY_DRIVER,
            min_driver_base=Decimal(10),
        )
        from app.cost.enums import AllocationCaveat

        assert AllocationCaveat.SMALL_DRIVER_BASE in result.caveats

    def test_driver_period_mismatch_caveat(self) -> None:
        result = allocate_shared(
            _money("100"),
            {"a": Decimal(1)},
            method=AllocationMethod.BY_DRIVER,
            driver_period_matches=False,
        )
        from app.cost.enums import AllocationCaveat

        assert AllocationCaveat.DRIVER_PERIOD_MISMATCH in result.caveats

    def test_driver_includes_allocated_cost_caveat(self) -> None:
        result = allocate_shared(
            _money("100"),
            {"a": Decimal(1)},
            method=AllocationMethod.BY_DRIVER,
            driver_includes_allocated_cost=True,
        )
        from app.cost.enums import AllocationCaveat

        assert AllocationCaveat.DRIVER_INCLUDES_ALLOCATED_COST in result.caveats

    def test_single_consumer_dominates_caveat(self) -> None:
        result = allocate_shared(
            _money("100"), {"a": Decimal(99), "b": Decimal(1)}, method=AllocationMethod.BY_DRIVER
        )
        from app.cost.enums import AllocationCaveat

        assert AllocationCaveat.SINGLE_CONSUMER_DOMINATES in result.caveats


class TestAllocationOrder:
    def test_simple_chain(self) -> None:
        order = allocation_order({"a": ["b"], "b": ["c"], "c": []})
        assert order == ("c", "b", "a")

    def test_cycle_returns_none(self) -> None:
        assert allocation_order({"a": ["b"], "b": ["a"]}) is None

    def test_empty_steps(self) -> None:
        assert allocation_order({}) == ()


class TestCheckRollup:
    def test_consistent_rollup(self) -> None:
        dims_a = Dimensions(organization_id="org1", department_id="dept1", project_id="proj1")
        dims_b = Dimensions(organization_id="org1", department_id="dept1", project_id="proj2")
        costs = [
            ProjectCost(dimensions=dims_a, direct_cost=_money("50"), allocated_cost=_money("0")),
            ProjectCost(dimensions=dims_b, direct_cost=_money("50"), allocated_cost=_money("0")),
        ]
        consistency = check_rollup(costs, currency="USD")
        assert consistency.org_total.amount == Decimal("100")
        assert consistency.org_equals_departments
        assert consistency.org_equals_projects

    def test_empty_costs(self) -> None:
        consistency = check_rollup([], currency="USD")
        assert consistency.org_total.amount == Decimal("0")
        assert consistency.org_equals_departments


class TestUnitCost:
    def _scope(self) -> Dimensions:
        return Dimensions(organization_id="org1", project_id="proj1")

    def test_scope_mismatch(self) -> None:
        volume = WorkVolume(
            meter="requests", count=Decimal(100), dimensions=Dimensions(organization_id="other")
        )
        result = unit_cost(_money("100"), volume, scope=self._scope())
        assert result.unavailable is UnitCostUnavailable.SCOPE_MISMATCH

    def test_denominator_not_measured(self) -> None:
        volume = WorkVolume(meter="requests", count=None, dimensions=self._scope())
        result = unit_cost(_money("100"), volume, scope=self._scope())
        assert result.unavailable is UnitCostUnavailable.DENOMINATOR_NOT_MEASURED

    def test_zero_denominator(self) -> None:
        volume = WorkVolume(meter="requests", count=Decimal(0), dimensions=self._scope())
        result = unit_cost(_money("412"), volume, scope=self._scope())
        assert result.unavailable is UnitCostUnavailable.ZERO_DENOMINATOR
        assert result.numerator.amount == Decimal("412")

    def test_partial_coverage(self) -> None:
        volume = WorkVolume(
            meter="requests",
            count=Decimal(100),
            dimensions=self._scope(),
            observed_fraction=Decimal("0.5"),
        )
        result = unit_cost(_money("100"), volume, scope=self._scope())
        assert result.unavailable is UnitCostUnavailable.DENOMINATOR_PARTIAL_COVERAGE

    def test_valid_unit_cost(self) -> None:
        volume = WorkVolume(meter="requests", count=Decimal(100), dimensions=self._scope())
        result = unit_cost(_money("50"), volume, scope=self._scope())
        assert result.value == Decimal("0.5")
        assert result.unavailable is None

    def test_lower_bound_numerator(self) -> None:
        volume = WorkVolume(meter="requests", count=Decimal(100), dimensions=self._scope())
        result = unit_cost(_money("50"), volume, scope=self._scope(), numerator_is_lower_bound=True)
        assert result.unavailable is UnitCostUnavailable.NUMERATOR_PARTIAL
        assert result.value == Decimal("0.5")

    def test_fixed_and_variable_component_split(self) -> None:
        volume = WorkVolume(meter="requests", count=Decimal(100), dimensions=self._scope())
        result = unit_cost(_money("150"), volume, scope=self._scope(), fixed_component=_money("50"))
        assert result.variable_component is not None
        assert result.variable_component.amount == Decimal("100")


class TestDecomposeVariance:
    def test_missing_data_returns_unexplained_only(self) -> None:
        result = decompose_variance(
            previous_cost=_money("100"),
            current_cost=_money("150"),
            previous_quantity=None,
            current_quantity=Decimal(10),
            previous_rate=Decimal(10),
            current_rate=Decimal(15),
        )
        assert result.volume_effect is None
        assert result.unexplained.amount == Decimal("50")

    def test_full_decomposition(self) -> None:
        result = decompose_variance(
            previous_cost=_money("100"),
            current_cost=_money("200"),
            previous_quantity=Decimal(10),
            current_quantity=Decimal(15),
            previous_rate=Decimal(10),
            current_rate=Decimal("10"),
        )
        assert result.volume_effect is not None
        assert result.volume_effect.amount == Decimal("50")
        assert result.price_effect is not None
        assert result.price_effect.amount == Decimal("0")
        assert result.mix_effect is not None
        assert result.mix_effect.amount == Decimal("0")
        assert result.delta.amount == Decimal("100")
        assert result.unexplained.amount == Decimal("50")  # delta(100) - explained(50)


class TestCostReport:
    def test_properties(self) -> None:
        from app.cost.analytics import CostReport

        coverage = CoverageStatement(
            attributed_cost=_money("90"),
            unattributed_cost=_money("10"),
            unattributed_by_reason={},
            unpriced_quantity_by_meter={},
            observed_fraction=Decimal(1),
            duplicates_dropped=0,
            conflicting_duplicates=0,
        )
        dims = Dimensions(organization_id="org1", project_id="proj1")
        project = ProjectCost(dimensions=dims, direct_cost=_money("90"), allocated_cost=_money("0"))
        report = CostReport(
            period_label="2026-01", currency="USD", coverage=coverage, projects=(project,)
        )

        assert report.total_cost.amount == Decimal("100")
        assert report.status is ReportStatus.PARTIAL
        bounds = report.bounds_for(project)
        assert bounds.lower == Decimal("0.9")
        assert report.ranking_is_supported(Decimal("0.5"))
        assert not report.ranking_is_supported(Decimal("0.05"))
