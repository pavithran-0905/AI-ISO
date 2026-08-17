"""The domain events this service publishes (docs/077 "EVENTS",
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
class TestStartedEvent(DomainEvent):
    """A test run began.

    Expected payload: ``test_run_id``, ``test_suite_id``.
    """

    event_name: ClassVar[str] = "TestStarted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class TestCompletedEvent(DomainEvent):
    """A test run succeeded.

    Expected payload: ``test_run_id``.
    """

    event_name: ClassVar[str] = "TestCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class TestFailedEvent(DomainEvent):
    """A test run failed.

    Expected payload: ``test_run_id``, ``error_message``.
    """

    event_name: ClassVar[str] = "TestFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class QualityGatePassedEvent(DomainEvent):
    """A quality gate passed.

    Expected payload: ``quality_gate_id``, ``gate_type``.
    """

    event_name: ClassVar[str] = "QualityGatePassed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class QualityGateFailedEvent(DomainEvent):
    """A quality gate failed.

    Expected payload: ``quality_gate_id``, ``gate_type``.
    """

    event_name: ClassVar[str] = "QualityGateFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class BenchmarkCompletedEvent(DomainEvent):
    """A benchmark comparison completed.

    Expected payload: ``benchmark_result_id``, ``name``.
    """

    event_name: ClassVar[str] = "BenchmarkCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ChaosTestCompletedEvent(DomainEvent):
    """A chaos experiment completed.

    Expected payload: ``chaos_result_id``, ``fault_type``, ``status``.
    """

    event_name: ClassVar[str] = "ChaosTestCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class SecurityScanCompletedEvent(DomainEvent):
    """A security scan completed.

    Expected payload: ``security_result_id``, ``security_type``, ``status``.
    """

    event_name: ClassVar[str] = "SecurityScanCompleted"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "BenchmarkCompletedEvent",
    "ChaosTestCompletedEvent",
    "QualityGateFailedEvent",
    "QualityGatePassedEvent",
    "SecurityScanCompletedEvent",
    "TestCompletedEvent",
    "TestFailedEvent",
    "TestStartedEvent",
]
