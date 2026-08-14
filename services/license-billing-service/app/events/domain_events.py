"""The domain events this service publishes (docs/069 "EVENTS",
integrating Prompt 020).

All eleven spec-named events. **Every event is registered with the
shared registry at import time.** ``EventManager.publish`` validates
against :data:`shared_core.events.registry.default_registry` and
refuses anything unregistered as ``AIIOS-EVENT-0002``.

**Fields live in ``payload``**, per :class:`~shared_core.events.base.BaseEvent`
-- not as typed attributes on each subclass, matching the convention
every other AI-IOS service follows.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class CustomerCreatedEvent(DomainEvent):
    """A new customer was created.

    Expected payload: ``customer_id``, ``name``, ``customer_type``.
    """

    event_name: ClassVar[str] = "CustomerCreated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SubscriptionCreatedEvent(DomainEvent):
    """A new subscription was created.

    Expected payload: ``subscription_id``, ``customer_id``, ``plan_id``.
    """

    event_name: ClassVar[str] = "SubscriptionCreated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SubscriptionRenewedEvent(DomainEvent):
    """A subscription was renewed for another period.

    Expected payload: ``subscription_id``, ``current_period_end``.
    """

    event_name: ClassVar[str] = "SubscriptionRenewed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SubscriptionExpiredEvent(DomainEvent):
    """A subscription expired without renewal.

    Expected payload: ``subscription_id``, ``customer_id``.
    """

    event_name: ClassVar[str] = "SubscriptionExpired"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class LicenseActivatedEvent(DomainEvent):
    """A license seat was activated.

    Expected payload: ``license_id``, ``activation_ref``.
    """

    event_name: ClassVar[str] = "LicenseActivated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class LicenseRevokedEvent(DomainEvent):
    """A license was revoked.

    Expected payload: ``license_id``, ``customer_id``.
    """

    event_name: ClassVar[str] = "LicenseRevoked"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class QuotaExceededEvent(DomainEvent):
    """A hard quota refused a request.

    Expected payload: ``customer_id``, ``quota_id``, ``metric_key``.
    """

    event_name: ClassVar[str] = "QuotaExceeded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class InvoiceGeneratedEvent(DomainEvent):
    """An invoice was generated.

    Expected payload: ``invoice_id``, ``billing_account_id``,
    ``total_amount``.
    """

    event_name: ClassVar[str] = "InvoiceGenerated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PaymentReceivedEvent(DomainEvent):
    """A payment transaction succeeded.

    Expected payload: ``payment_transaction_id``, ``billing_account_id``,
    ``amount``.
    """

    event_name: ClassVar[str] = "PaymentReceived"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class PaymentFailedEvent(DomainEvent):
    """A payment transaction failed.

    Expected payload: ``payment_transaction_id``, ``billing_account_id``.
    """

    event_name: ClassVar[str] = "PaymentFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class MarketplacePurchaseCompletedEvent(DomainEvent):
    """A marketplace purchase completed.

    Expected payload: ``marketplace_subscription_id``, ``customer_id``.
    """

    event_name: ClassVar[str] = "MarketplacePurchaseCompleted"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "CustomerCreatedEvent",
    "InvoiceGeneratedEvent",
    "LicenseActivatedEvent",
    "LicenseRevokedEvent",
    "MarketplacePurchaseCompletedEvent",
    "PaymentFailedEvent",
    "PaymentReceivedEvent",
    "QuotaExceededEvent",
    "SubscriptionCreatedEvent",
    "SubscriptionExpiredEvent",
    "SubscriptionRenewedEvent",
]
