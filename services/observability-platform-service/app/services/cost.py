"""Cost reporting service: prices usage records with
``app.cost.rates``, tracks what could not be priced with
``app.cost.analytics``, and persists exactly one :class:`CostReport` row
per period/dimension -- with unattributed and unpriced cost kept
separate all the way through, per the module docstrings that govern them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.cost.analytics import CoverageStatement, share_bounds
from app.cost.enums import UnattributedReason
from app.cost.money import Money, sum_money
from app.cost.rates import RateCardSet, price_quantity, resolve_rate
from app.cost.usage import CoverageWindow, UsageRecord, dedupe_usage, observed_fraction
from app.models.analysis import CostReport
from app.models.enums import CostCategory
from app.repositories.analysis import CostReportRepository


class CostReportingService:
    """Prices one period's usage for one dimension and persists the report."""

    def __init__(self, repo: CostReportRepository) -> None:
        self._repo = repo

    async def generate_report(
        self,
        organization_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
        generated_at: datetime,
        dimension: str,
        dimension_value: str | None,
        category: CostCategory | None,
        usage_records: Sequence[UsageRecord],
        cards: RateCardSet,
        coverage_windows: Sequence[CoverageWindow],
        currency: str = "USD",
        rate_card_version: str | None = None,
    ) -> CostReport:
        """Deduplicate, price, and total one period's usage.

        Every usage record ends up in exactly one of three buckets:
        priced (attributed), priced-but-ownerless (unattributed, still
        inside the total), or genuinely unpriced (a quantity, never
        money, never inside the total). Which bucket a record lands in is
        never inferred twice -- each record is classified once, in this
        loop, and the totals below only ever sum what was already
        classified.
        """
        deduped = dedupe_usage(usage_records)
        priced_costs: list[Money] = []
        unattributed_costs: list[Money] = []
        unpriced_quantity: dict[str, Decimal] = {}
        unattributed_by_reason: dict[UnattributedReason, list[Money]] = {}
        by_category: dict[str, Decimal] = {}
        by_service: dict[str, Decimal] = {}

        for record in deduped.kept:
            resolution = resolve_rate(cards, record.meter, record.window_start)
            if resolution.rate is None:
                unpriced_quantity[record.meter] = (
                    unpriced_quantity.get(record.meter, Decimal(0)) + record.quantity
                )
                continue

            factor = cards.conversion_factor(record.unit, resolution.rate.unit)
            if factor is None:
                unpriced_quantity[record.meter] = (
                    unpriced_quantity.get(record.meter, Decimal(0)) + record.quantity
                )
                continue

            priced = price_quantity(record.quantity, resolution.rate, conversion_factor=factor)
            has_owner = bool(record.labels.get("project_id") or record.resource_id)
            if has_owner:
                priced_costs.append(priced.cost)
                service = record.labels.get("service", "unknown")
                by_service[service] = by_service.get(service, Decimal(0)) + priced.cost.amount
            else:
                unattributed_costs.append(priced.cost)
                reason = (
                    UnattributedReason.SHARED_INFRASTRUCTURE
                    if record.resource_id
                    else UnattributedReason.NO_LABELS
                )
                unattributed_by_reason.setdefault(reason, []).append(priced.cost)

            meter_category = record.labels.get("category", str(category) if category else "other")
            by_category[meter_category] = (
                by_category.get(meter_category, Decimal(0)) + priced.cost.amount
            )

        attributed_sum = sum_money(priced_costs, currency)
        unattributed_sum = sum_money(unattributed_costs, currency)
        attributed = attributed_sum.total or Money.measured_zero(currency)
        unattributed = unattributed_sum.total or Money.measured_zero(currency)

        coverage = CoverageStatement(
            attributed_cost=attributed,
            unattributed_cost=unattributed,
            unattributed_by_reason={
                reason: (sum_money(costs, currency).total or Money.measured_zero(currency))
                for reason, costs in unattributed_by_reason.items()
            },
            unpriced_quantity_by_meter=unpriced_quantity,
            observed_fraction=(
                observed_fraction(
                    coverage_windows,
                    period_start=period_start,
                    period_end=period_end,
                    meter=next(iter({r.meter for r in deduped.kept}), ""),
                )
                if deduped.kept
                else None
            ),
            duplicates_dropped=deduped.duplicates_dropped,
            conflicting_duplicates=len(deduped.conflicting),
        )
        total = coverage.total_cost

        return await self._repo.create(
            CostReport(
                organization_id=organization_id,
                period_start=period_start,
                period_end=period_end,
                generated_at=generated_at,
                dimension=dimension,
                dimension_value=dimension_value,
                category=category,
                currency=currency,
                total_cost=total.amount,
                attributed_cost=attributed.amount,
                unattributed_cost=unattributed.amount,
                allocated_shared_cost=Decimal(0),
                allocation_basis=None,
                by_category={key: str(value) for key, value in by_category.items()},
                by_service={key: str(value) for key, value in by_service.items()},
                rate_card_version=rate_card_version,
                details={
                    "unattributed_fraction": str(coverage.unattributed_fraction),
                    "materially_unattributed": coverage.materially_unattributed,
                    "total_is_lower_bound": coverage.total_is_lower_bound,
                    "report_status": str(coverage.report_status),
                    "unpriced_meters": list(unpriced_quantity),
                    "duplicates_dropped": deduped.duplicates_dropped,
                    "conflicting_duplicates": len(deduped.conflicting),
                },
            )
        )


def bounds_for_project(report: CostReport, project_cost: Money) -> tuple[Decimal, Decimal]:
    """Share bounds for one project's cost against a persisted report.

    A thin re-export so a caller with a report row (rather than the live
    :class:`CoverageStatement` that produced it) can still get the
    interval width that :mod:`app.cost.analytics` insists on.
    """
    total = Money(report.total_cost, report.currency)
    unattributed = Money(report.unattributed_cost, report.currency)
    bounds = share_bounds(project_cost, total, unattributed)
    return bounds.lower, bounds.upper


__all__ = ["CostReportingService", "bounds_for_project"]
