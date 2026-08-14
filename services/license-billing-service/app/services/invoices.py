"""Invoice generation.

Wires ``app.billing.engine``'s pure subtotal/discount calculation onto
the repositories that persist invoices and their line items, publishing
``InvoiceGenerated``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.billing.engine import InvoiceLineItem, compute_invoice_subtotal
from app.events.domain_events import InvoiceGeneratedEvent
from app.models.billing import Invoice, InvoiceItem
from app.models.enums import AuditAction, InvoiceStatus
from app.repositories.billing import InvoiceItemRepository, InvoiceRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "license-billing-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


@dataclass(frozen=True, slots=True)
class InvoiceItemInput:
    description: str
    quantity: float
    unit_price: float


class InvoiceService:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        item_repo: InvoiceItemRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._item_repo = item_repo
        self._publish = publish
        self._audit = audit

    async def generate(
        self,
        organization_id: UUID,
        *,
        billing_account_id: UUID,
        subscription_id: UUID | None,
        invoice_number: str,
        items: list[InvoiceItemInput],
        currency: str,
        due_days: int,
        actor_id: str | None,
        now: datetime,
    ) -> Invoice:
        subtotal = compute_invoice_subtotal(
            [InvoiceLineItem(quantity=item.quantity, unit_price=item.unit_price) for item in items]
        )
        invoice = await self._invoice_repo.create(
            Invoice(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                subscription_id=subscription_id,
                invoice_number=invoice_number,
                status=InvoiceStatus.ISSUED,
                issued_at=now,
                due_at=now + timedelta(days=due_days),
                total_amount=subtotal,
                currency=currency,
            )
        )
        for item in items:
            await self._item_repo.create(
                InvoiceItem(
                    organization_id=organization_id,
                    invoice_id=invoice.id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.quantity * item.unit_price,
                )
            )
        if self._audit is not None:
            await self._audit.record(
                organization_id,
                action=AuditAction.INVOICE_GENERATED,
                entity_type="invoice",
                entity_id=invoice.id,
                occurred_at=now,
                actor_id=actor_id,
                summary=f"Generated invoice {invoice_number!r} for {subtotal} {currency}.",
            )
        await self._publish(
            InvoiceGeneratedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "invoice_id": str(invoice.id),
                    "billing_account_id": str(billing_account_id),
                    "total_amount": subtotal,
                },
            )
        )
        return invoice

    async def mark_paid(self, invoice: Invoice) -> Invoice:
        invoice.status = InvoiceStatus.PAID
        return await self._invoice_repo.update(invoice)

    async def mark_overdue(self, invoice: Invoice) -> Invoice:
        invoice.status = InvoiceStatus.OVERDUE
        return await self._invoice_repo.update(invoice)

    async def void(self, invoice: Invoice) -> Invoice:
        invoice.status = InvoiceStatus.VOID
        return await self._invoice_repo.update(invoice)


__all__ = ["InvoiceItemInput", "InvoiceService"]
