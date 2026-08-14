"""The invoice generation sweep worker.

**Leader-elected** through ``shared_core.scheduler``; see
:mod:`app.workers.registrar`.

For every active subscription with a billing account, issues one
invoice per billing period -- skipping any subscription already
invoiced since its current period started, so a re-run mid-period never
double-bills. Also transitions any issued invoice past its due date to
``OVERDUE``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import InvoiceStatus, SubscriptionStatus
from app.services.bundle import build_repositories
from app.services.invoices import InvoiceItemInput, InvoiceService
from app.types import EventPublisher

logger = get_logger("app.workers.invoice_generation_sweep")


class InvoiceGenerationSweepWorker:
    """Issues one invoice per billing period for every active,
    billable subscription, and marks overdue invoices as such."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        due_days: int,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._due_days = due_days

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> int:
        """Sweep every organization's billing, returning how many
        invoices were generated."""
        now = datetime.now(UTC)
        generated = 0
        overdue = 0

        async with self._session_factory() as session:
            repos = build_repositories(session)
            invoice_service = InvoiceService(
                repos.invoices, repos.invoice_items, publish=self._publish_event
            )

            for organization_id in await repos.subscriptions.list_organization_ids():
                for subscription in await repos.subscriptions.list_by_status(
                    organization_id, status=SubscriptionStatus.ACTIVE
                ):
                    billing_account = await repos.billing_accounts.find_for_customer(
                        subscription.customer_id
                    )
                    if billing_account is None:
                        continue
                    already_invoiced = any(
                        invoice.issued_at is not None
                        and invoice.issued_at >= subscription.current_period_start
                        for invoice in await repos.invoices.list_for_subscription(subscription.id)
                    )
                    if already_invoiced:
                        continue

                    plan = await repos.plans.get_by_id(subscription.plan_id)
                    if plan is None:
                        continue

                    invoice_number = (
                        f"INV-{subscription.id.hex[:12]}-{subscription.current_period_start:%Y%m%d}"
                    )
                    await invoice_service.generate(
                        organization_id,
                        billing_account_id=billing_account.id,
                        subscription_id=subscription.id,
                        invoice_number=invoice_number,
                        items=[
                            InvoiceItemInput(
                                description=f"{plan.name} subscription period",
                                quantity=1.0,
                                unit_price=plan.base_price,
                            )
                        ],
                        currency=plan.currency,
                        due_days=self._due_days,
                        actor_id=None,
                        now=now,
                    )
                    generated += 1

            for organization_id in await repos.invoices.list_organization_ids():
                for invoice in await repos.invoices.list_by_status(
                    organization_id, status=InvoiceStatus.ISSUED
                ):
                    if invoice.due_at is not None and invoice.due_at < now:
                        await invoice_service.mark_overdue(invoice)
                        overdue += 1

            await session.commit()

        logger.info(
            "invoice generation sweep completed",
            extra={"extra_fields": {"generated": generated, "overdue": overdue}},
        )
        return generated


__all__ = ["InvoiceGenerationSweepWorker"]
