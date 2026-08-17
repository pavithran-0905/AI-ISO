"""The domain events this service publishes (docs/079 "EVENTS",
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
class HardeningStartedEvent(DomainEvent):
    """A hardening run began.

    Expected payload: ``hardening_run_id``, ``hardening_profile_id``.
    """

    event_name: ClassVar[str] = "HardeningStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class HardeningCompletedEvent(DomainEvent):
    """A hardening run reached a terminal state, regardless of whether
    it succeeded or failed.

    Expected payload: ``hardening_run_id``, ``status``.
    """

    event_name: ClassVar[str] = "HardeningCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SecurityIssueDetectedEvent(DomainEvent):
    """A new security finding was recorded.

    Expected payload: ``security_finding_id``, ``severity``.
    """

    event_name: ClassVar[str] = "SecurityIssueDetected"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class VulnerabilityDetectedEvent(DomainEvent):
    """A new vulnerability scan result was recorded.

    Expected payload: ``vulnerability_scan_id``, ``severity``.
    """

    event_name: ClassVar[str] = "VulnerabilityDetected"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CertificationGrantedEvent(DomainEvent):
    """A production certification was granted.

    Expected payload: ``production_certification_id``, ``name``.
    """

    event_name: ClassVar[str] = "CertificationGranted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class CertificationRevokedEvent(DomainEvent):
    """A production certification was revoked.

    Expected payload: ``production_certification_id``, ``name``.
    """

    event_name: ClassVar[str] = "CertificationRevoked"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ComplianceValidatedEvent(DomainEvent):
    """A compliance control was evaluated, regardless of outcome.

    Expected payload: ``compliance_result_id``, ``framework``, ``is_compliant``.
    """

    event_name: ClassVar[str] = "ComplianceValidated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ProductionReadyEvent(DomainEvent):
    """An organization's aggregate production readiness score crossed
    the configured "ready" threshold.

    Expected payload: ``organization_id``, ``score``.
    """

    event_name: ClassVar[str] = "ProductionReady"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "CertificationGrantedEvent",
    "CertificationRevokedEvent",
    "ComplianceValidatedEvent",
    "HardeningCompletedEvent",
    "HardeningStartedEvent",
    "ProductionReadyEvent",
    "SecurityIssueDetectedEvent",
    "VulnerabilityDetectedEvent",
]
