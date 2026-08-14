"""Notifications (docs/069 "NOTIFICATIONS", integrating Prompt 025).

**Three of the eight notification kinds have a domain event behind
them** (Payment Failed, Invoice Generated, Quota Exceeded) and are
dispatched by :class:`NotifyingPublisher`, an ``EventPublisher`` that
wraps the real one, forwards every event unchanged, and
opportunistically notifies for the subset that warrant it -- exactly
the pattern
``services/multi-cluster-management-service/app/services/notifications.py``
established.

**The other five do not** (Trial Expiring, Subscription Expiring,
License Expired, Renewal Reminder, Contract Renewal Due): none maps to
a lifecycle-boundary domain event this service publishes, since
expiry/renewal windows are observed continuously by a worker rather
than announced as discrete facts. Those are called directly by the
workers that observe them.
"""

from __future__ import annotations

from typing import Any

from shared_core.enums.notification_type import NotificationType
from shared_core.enums.priority import Priority
from shared_core.events.base import BaseEvent
from shared_core.notifications.manager import NotificationManager

from app.types import EventPublisher

TOPIC_TRIAL_EXPIRING = "license_billing.trial_expiring"
TOPIC_SUBSCRIPTION_EXPIRING = "license_billing.subscription_expiring"
TOPIC_PAYMENT_FAILED = "license_billing.payment_failed"
TOPIC_INVOICE_GENERATED = "license_billing.invoice_generated"
TOPIC_QUOTA_EXCEEDED = "license_billing.quota_exceeded"
TOPIC_LICENSE_EXPIRED = "license_billing.license_expired"
TOPIC_RENEWAL_REMINDER = "license_billing.renewal_reminder"
TOPIC_CONTRACT_RENEWAL_DUE = "license_billing.contract_renewal_due"


class BillingNotifier:
    """Sends the eight notification kinds docs/069 names."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def notify_trial_expiring(self, *, subscription_id: str, days_remaining: int) -> None:
        await self._manager.broadcast(
            topic=TOPIC_TRIAL_EXPIRING,
            notification_type=NotificationType.INFORMATION,
            body=f"Trial subscription {subscription_id} expires in {days_remaining} day(s).",
            priority=Priority.NORMAL,
            variables={"subscription_id": subscription_id},
        )

    async def notify_subscription_expiring(
        self, *, subscription_id: str, days_remaining: int
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_SUBSCRIPTION_EXPIRING,
            notification_type=NotificationType.WARNING,
            body=f"Subscription {subscription_id} expires in {days_remaining} day(s).",
            priority=Priority.HIGH,
            variables={"subscription_id": subscription_id},
        )

    async def notify_payment_failed(
        self, *, payment_transaction_id: str, billing_account_id: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_PAYMENT_FAILED,
            notification_type=NotificationType.MONITORING,
            body=(
                f"Payment {payment_transaction_id} failed for billing account "
                f"{billing_account_id}."
            ),
            priority=Priority.CRITICAL,
            variables={"payment_transaction_id": payment_transaction_id},
        )

    async def notify_invoice_generated(self, *, invoice_id: str, total_amount: float) -> None:
        await self._manager.broadcast(
            topic=TOPIC_INVOICE_GENERATED,
            notification_type=NotificationType.INFORMATION,
            body=f"Invoice {invoice_id} generated for {total_amount:.2f}.",
            priority=Priority.NORMAL,
            variables={"invoice_id": invoice_id},
        )

    async def notify_quota_exceeded(self, *, customer_id: str, metric_key: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_QUOTA_EXCEEDED,
            notification_type=NotificationType.WARNING,
            body=f"Customer {customer_id} exceeded their {metric_key} quota.",
            priority=Priority.HIGH,
            variables={"customer_id": customer_id, "metric_key": metric_key},
        )

    async def notify_license_expired(self, *, license_id: str, customer_id: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_LICENSE_EXPIRED,
            notification_type=NotificationType.WARNING,
            body=f"License {license_id} for customer {customer_id} has expired.",
            priority=Priority.HIGH,
            variables={"license_id": license_id, "customer_id": customer_id},
        )

    async def notify_renewal_reminder(
        self, *, subscription_id: str, current_period_end: str
    ) -> None:
        await self._manager.broadcast(
            topic=TOPIC_RENEWAL_REMINDER,
            notification_type=NotificationType.INFORMATION,
            body=f"Subscription {subscription_id} renews at {current_period_end}.",
            priority=Priority.NORMAL,
            variables={"subscription_id": subscription_id},
        )

    async def notify_contract_renewal_due(self, *, contract_id: str, end_at: str) -> None:
        await self._manager.broadcast(
            topic=TOPIC_CONTRACT_RENEWAL_DUE,
            notification_type=NotificationType.WARNING,
            body=f"Contract {contract_id} renewal is due by {end_at}.",
            priority=Priority.HIGH,
            variables={"contract_id": contract_id},
        )


class NotifyingPublisher:
    """An :class:`EventPublisher` that forwards every event, and
    additionally notifies for the subset that warrant one.

    A notification failure never blocks or drops the event: the event
    still reaches its real destination exactly as if this wrapper were
    not there.
    """

    def __init__(self, inner: EventPublisher, notifier: BillingNotifier) -> None:
        self._inner = inner
        self._notifier = notifier

    async def __call__(self, event: BaseEvent) -> None:
        await self._inner(event)
        await self._maybe_notify(event)

    async def _maybe_notify(self, event: BaseEvent) -> None:
        payload: dict[str, Any] = event.payload
        if event.event_name == "PaymentFailed":
            await self._notifier.notify_payment_failed(
                payment_transaction_id=str(payload.get("payment_transaction_id", "")),
                billing_account_id=str(payload.get("billing_account_id", "")),
            )
        elif event.event_name == "InvoiceGenerated":
            await self._notifier.notify_invoice_generated(
                invoice_id=str(payload.get("invoice_id", "")),
                total_amount=float(payload.get("total_amount", 0.0)),
            )
        elif event.event_name == "QuotaExceeded":
            await self._notifier.notify_quota_exceeded(
                customer_id=str(payload.get("customer_id", "")),
                metric_key=str(payload.get("metric_key", "")),
            )


__all__ = ["BillingNotifier", "NotifyingPublisher"]
