"""The domain events this service publishes (docs/073 "EVENTS",
integrating Prompt 020).

All eight spec-named events. **Every event is registered with the
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
class DeveloperRegisteredEvent(DomainEvent):
    """A developer account was registered.

    Expected payload: ``developer_account_id``, ``email``.
    """

    event_name: ClassVar[str] = "DeveloperRegistered"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ApplicationCreatedEvent(DomainEvent):
    """A developer application was registered.

    Expected payload: ``application_id``, ``developer_account_id``, ``name``.
    """

    event_name: ClassVar[str] = "ApplicationCreated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class APIKeyGeneratedEvent(DomainEvent):
    """An API key was generated.

    Expected payload: ``api_key_id``, ``application_id``.
    """

    event_name: ClassVar[str] = "APIKeyGenerated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class OAuthClientCreatedEvent(DomainEvent):
    """An OAuth client was registered.

    Expected payload: ``oauth_client_id``, ``application_id``.
    """

    event_name: ClassVar[str] = "OAuthClientCreated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SubscriptionActivatedEvent(DomainEvent):
    """A developer subscribed to an API plan.

    Expected payload: ``subscription_id``, ``developer_account_id``, ``api_plan_id``.
    """

    event_name: ClassVar[str] = "SubscriptionActivated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class QuotaExceededEvent(DomainEvent):
    """A developer account exceeded one of its own quotas.

    Expected payload: ``developer_account_id``, ``quota_type``.
    """

    event_name: ClassVar[str] = "QuotaExceeded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SDKGeneratedEvent(DomainEvent):
    """An SDK was generated for a published API product (integrating
    Prompt 071).

    Expected payload: ``api_product_id``, ``language``.
    """

    event_name: ClassVar[str] = "SDKGenerated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class APIVersionReleasedEvent(DomainEvent):
    """An API version was released.

    Expected payload: ``api_version_id``, ``api_product_id``, ``version``.
    """

    event_name: ClassVar[str] = "APIVersionReleased"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "APIKeyGeneratedEvent",
    "APIVersionReleasedEvent",
    "ApplicationCreatedEvent",
    "DeveloperRegisteredEvent",
    "OAuthClientCreatedEvent",
    "QuotaExceededEvent",
    "SDKGeneratedEvent",
    "SubscriptionActivatedEvent",
]
