"""Auth edge cases and direct tests for the notification layer."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from shared_core.enums.notification_type import NotificationType
from shared_core.events.base import BaseEvent

from app.events.domain_events import InvoiceGeneratedEvent, PaymentFailedEvent, QuotaExceededEvent
from app.services.notifications import BillingNotifier, NotifyingPublisher
from tests.conftest import HTTP_FORBIDDEN, HTTP_OK, HTTP_UNAUTHORIZED, AuthHeadersFn


class TestAuthEdgeCases:
    async def test_malformed_token_is_unauthorized(self, client: AsyncClient) -> None:
        response = await client.get("/licenses", headers={"Authorization": "Bearer not-a-real-jwt"})
        assert response.status_code == HTTP_UNAUTHORIZED

    async def test_missing_organization_claim_is_forbidden(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=None)
        response = await client.get("/licenses", headers=headers)
        assert response.status_code == HTTP_FORBIDDEN

    async def test_empty_roles_cannot_administer(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=[])
        response = await client.post(
            "/licenses",
            json={"customer_id": str(uuid4()), "license_model": "saas"},
            headers=headers,
        )
        assert response.status_code == HTTP_FORBIDDEN

    async def test_administrator_role_case_insensitive(
        self, client: AsyncClient, auth_headers: AuthHeadersFn
    ) -> None:
        headers = auth_headers(organization_id=uuid4(), roles=["  Billing_Admin  "])
        response = await client.get("/licenses", headers=headers)
        assert response.status_code == HTTP_OK


class _RecordingManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def broadcast(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestBillingNotifier:
    async def test_notify_trial_expiring(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_trial_expiring(subscription_id="s-1", days_remaining=3)
        assert manager.calls[0]["topic"] == "license_billing.trial_expiring"

    async def test_notify_subscription_expiring(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_subscription_expiring(subscription_id="s-1", days_remaining=0)
        assert manager.calls[0]["priority"].name == "HIGH"

    async def test_notify_payment_failed(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_payment_failed(payment_transaction_id="p-1", billing_account_id="a-1")
        assert manager.calls[0]["notification_type"] is NotificationType.MONITORING

    async def test_notify_invoice_generated(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_invoice_generated(invoice_id="i-1", total_amount=100.0)
        assert manager.calls[0]["topic"] == "license_billing.invoice_generated"

    async def test_notify_quota_exceeded(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_quota_exceeded(customer_id="c-1", metric_key="seats")
        assert manager.calls[0]["topic"] == "license_billing.quota_exceeded"

    async def test_notify_license_expired(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_license_expired(license_id="l-1", customer_id="c-1")
        assert manager.calls[0]["topic"] == "license_billing.license_expired"

    async def test_notify_renewal_reminder(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_renewal_reminder(
            subscription_id="s-1", current_period_end="2026-07-01T00:00:00Z"
        )
        assert manager.calls[0]["topic"] == "license_billing.renewal_reminder"

    async def test_notify_contract_renewal_due(self) -> None:
        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        await notifier.notify_contract_renewal_due(contract_id="c-1", end_at="2026-07-01T00:00:00Z")
        assert manager.calls[0]["topic"] == "license_billing.contract_renewal_due"


class TestNotifyingPublisher:
    async def test_forwards_every_event(self) -> None:
        forwarded: list[BaseEvent] = []

        async def _inner(event: BaseEvent) -> None:
            forwarded.append(event)

        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = InvoiceGeneratedEvent(
            source_service="license-billing-service",
            payload={"invoice_id": "i-1", "billing_account_id": "a-1", "total_amount": 50.0},
        )
        await publisher(event)
        assert forwarded == [event]
        assert manager.calls[0]["topic"] == "license_billing.invoice_generated"

    async def test_payment_failed_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = PaymentFailedEvent(
            source_service="license-billing-service",
            payload={"payment_transaction_id": "p-1", "billing_account_id": "a-1"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "license_billing.payment_failed"

    async def test_quota_exceeded_triggers_notification(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = QuotaExceededEvent(
            source_service="license-billing-service",
            payload={"customer_id": "c-1", "quota_id": "q-1", "metric_key": "seats"},
        )
        await publisher(event)
        assert manager.calls[0]["topic"] == "license_billing.quota_exceeded"

    async def test_unmapped_event_does_not_notify(self) -> None:
        async def _inner(event: BaseEvent) -> None:
            pass

        from app.events.domain_events import CustomerCreatedEvent

        manager = _RecordingManager()
        notifier = BillingNotifier(manager)  # type: ignore[arg-type]
        publisher = NotifyingPublisher(_inner, notifier)
        event = CustomerCreatedEvent(
            source_service="license-billing-service",
            payload={"customer_id": "c-1", "name": "Acme", "customer_type": "organization"},
        )
        await publisher(event)
        assert manager.calls == []
