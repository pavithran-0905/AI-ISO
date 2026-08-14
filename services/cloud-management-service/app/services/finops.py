"""Cost recording and budget threshold tracking.

Wires ``app.finops.engine``'s pure budget classification onto the
repository that persists budgets, publishing ``BudgetThresholdExceeded``
on crossing into warning/critical/exceeded.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import BudgetThresholdExceededEvent
from app.finops.engine import BudgetStatus, classify_budget_status
from app.models.enums import AuditAction, BudgetPeriod
from app.models.operations import CloudBudget, CloudCost
from app.repositories.operations import CloudBudgetRepository, CloudCostRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "cloud-management-service"

_NOTIFIABLE_STATUSES = frozenset(
    {BudgetStatus.WARNING, BudgetStatus.CRITICAL, BudgetStatus.EXCEEDED}
)


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class CloudCostService:
    def __init__(self, repo: CloudCostRepository, *, audit: AuditService | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def record_cost(
        self,
        organization_id: UUID,
        *,
        account_id: UUID,
        resource_id: UUID | None,
        amount: float,
        currency: str,
        cost_category: str,
        period_start: datetime,
        period_end: datetime,
        actor_id: str | None,
        now: datetime,
    ) -> CloudCost:
        cost = await self._repo.create(
            CloudCost(
                organization_id=organization_id,
                account_id=account_id,
                resource_id=resource_id,
                amount=amount,
                currency=currency,
                cost_category=cost_category,
                period_start=period_start,
                period_end=period_end,
            )
        )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.COST_CHANGED,
                entity_type="cloud_cost",
                entity_id=cost.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=(
                    f"Recorded {amount} {currency} of {cost_category} cost for "
                    f"account {account_id!s}."
                ),
            )
        return cost


class CloudBudgetService:
    def __init__(
        self, repo: CloudBudgetRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def create_budget(
        self,
        organization_id: UUID,
        *,
        account_id: UUID | None,
        name: str,
        amount: float,
        period: BudgetPeriod,
        threshold_fraction: float,
        period_start: datetime,
        period_end: datetime,
    ) -> CloudBudget:
        return await self._repo.create(
            CloudBudget(
                organization_id=organization_id,
                account_id=account_id,
                name=name,
                amount=amount,
                period=period,
                threshold_fraction=threshold_fraction,
                period_start=period_start,
                period_end=period_end,
            )
        )

    async def refresh_spend(
        self, budget: CloudBudget, *, current_spend: float, critical_threshold: float
    ) -> str:
        """Update *budget*'s current spend and publish
        ``BudgetThresholdExceeded`` if it has crossed into warning,
        critical, or exceeded.

        Returns the classified :class:`~app.finops.engine.BudgetStatus`.
        """
        previous_status = classify_budget_status(
            budget.current_spend,
            budget.amount,
            warning_threshold=budget.threshold_fraction,
            critical_threshold=critical_threshold,
        )
        budget.current_spend = current_spend
        status = classify_budget_status(
            current_spend,
            budget.amount,
            warning_threshold=budget.threshold_fraction,
            critical_threshold=critical_threshold,
        )
        await self._repo.update(budget)

        if status in _NOTIFIABLE_STATUSES and status != previous_status:
            await self._publish(
                BudgetThresholdExceededEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=budget.organization_id,
                    payload={
                        "budget_id": str(budget.id),
                        "status": status,
                        "current_spend": current_spend,
                        "amount": budget.amount,
                    },
                )
            )
        return status


__all__ = ["CloudBudgetService", "CloudCostService"]
