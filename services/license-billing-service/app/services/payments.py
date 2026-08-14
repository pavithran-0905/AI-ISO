"""Payment transaction recording and retry eligibility.

Wires ``app.payments.engine``'s pure retry decision onto the repository
that persists payment transactions, publishing
``PaymentReceived``/``PaymentFailed``.

**This service records payment outcomes; it never processes a real
payment itself** -- see this package's README "Scope boundary". A
caller (a payment gateway webhook handler, an operator) reports the
outcome; this service is the system of record for it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.events.domain_events import PaymentFailedEvent, PaymentReceivedEvent
from app.models.billing import PaymentTransaction
from app.models.enums import AuditAction, PaymentStatus
from app.payments.engine import RetryDecision, should_retry_payment
from app.repositories.billing import PaymentTransactionRepository
from app.services.audit import AuditService
from app.types import EventPublisher

_SOURCE_SERVICE = "license-billing-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PaymentService:
    def __init__(
        self,
        repo: PaymentTransactionRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        audit: AuditService | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._audit = audit

    async def record_attempt(
        self,
        organization_id: UUID,
        *,
        billing_account_id: UUID,
        payment_method_id: UUID | None,
        invoice_id: UUID | None,
        amount: float,
        currency: str,
    ) -> PaymentTransaction:
        return await self._repo.create(
            PaymentTransaction(
                organization_id=organization_id,
                billing_account_id=billing_account_id,
                payment_method_id=payment_method_id,
                invoice_id=invoice_id,
                amount=amount,
                currency=currency,
                status=PaymentStatus.PENDING,
            )
        )

    async def mark_succeeded(
        self, transaction: PaymentTransaction, *, now: datetime
    ) -> PaymentTransaction:
        transaction.status = PaymentStatus.SUCCEEDED
        transaction.processed_at = now
        await self._repo.update(transaction)
        if self._audit is not None:
            await self._audit.record(
                transaction.organization_id,
                action=AuditAction.PAYMENT_EVENT,
                entity_type="payment_transaction",
                entity_id=transaction.id,
                occurred_at=now,
                summary=(
                    f"Payment {transaction.id!s} succeeded for "
                    f"{transaction.amount} {transaction.currency}."
                ),
            )
        await self._publish(
            PaymentReceivedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=transaction.organization_id,
                payload={
                    "payment_transaction_id": str(transaction.id),
                    "billing_account_id": str(transaction.billing_account_id),
                    "amount": transaction.amount,
                },
            )
        )
        return transaction

    async def mark_failed(
        self, transaction: PaymentTransaction, *, now: datetime
    ) -> PaymentTransaction:
        transaction.status = PaymentStatus.FAILED
        transaction.processed_at = now
        await self._repo.update(transaction)
        if self._audit is not None:
            await self._audit.record(
                transaction.organization_id,
                action=AuditAction.PAYMENT_EVENT,
                entity_type="payment_transaction",
                entity_id=transaction.id,
                occurred_at=now,
                summary=f"Payment {transaction.id!s} failed.",
                succeeded=False,
            )
        await self._publish(
            PaymentFailedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=transaction.organization_id,
                payload={
                    "payment_transaction_id": str(transaction.id),
                    "billing_account_id": str(transaction.billing_account_id),
                },
            )
        )
        return transaction

    async def prepare_retry(
        self, transaction: PaymentTransaction, *, max_attempts: int
    ) -> RetryDecision:
        """Whether *transaction* should be retried, incrementing its
        attempt count when it is."""
        decision = should_retry_payment(
            transaction.status, attempt_count=transaction.attempt_count, max_attempts=max_attempts
        )
        if decision.should_retry:
            transaction.attempt_count += 1
            transaction.status = PaymentStatus.PENDING
            await self._repo.update(transaction)
        return decision


__all__ = ["PaymentService"]
