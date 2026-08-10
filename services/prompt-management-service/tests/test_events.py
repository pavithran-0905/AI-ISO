"""This service's own domain events (docs/061 "EVENTS").

Every class in :mod:`app.events.prompt_events` is a declarative
:class:`~shared_core.events.base.DomainEvent` subclass whose only real
behaviour is the ``@default_registry.register`` decorator applied at
import time. These tests confirm each of the nine is registered under
its own ``event_name``, carries the fields every
:class:`~shared_core.events.base.BaseEvent` defines with the right
defaults, is a genuinely distinct class, and accepts the exact payload
shape the service that publishes it actually sends.

The payload assertions are pinned deliberately. ``payload`` is an
untyped ``dict``, so nothing in the event class itself would notice a
producer quietly renaming a key -- these tests are the only place the
published contract is written down next to the keys the producers use.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from shared_core.events import default_registry
from shared_core.events.base import BaseEvent, DomainEvent, EventType

from app.events import prompt_events
from app.events.prompt_events import (
    PromptApprovalRequestedEvent,
    PromptCreatedEvent,
    PromptDeprecatedEvent,
    PromptEvaluatedEvent,
    PromptExecutedEvent,
    PromptOptimizedEvent,
    PromptPublishedEvent,
    PromptSecurityViolationEvent,
    PromptUpdatedEvent,
)

SOURCE_SERVICE = "prompt-management-service"

EVENT_CLASSES: list[tuple[type[DomainEvent], str]] = [
    (PromptCreatedEvent, "PromptCreated"),
    (PromptUpdatedEvent, "PromptUpdated"),
    (PromptPublishedEvent, "PromptPublished"),
    (PromptDeprecatedEvent, "PromptDeprecated"),
    (PromptExecutedEvent, "PromptExecuted"),
    (PromptEvaluatedEvent, "PromptEvaluated"),
    (PromptOptimizedEvent, "PromptOptimized"),
    (PromptApprovalRequestedEvent, "PromptApprovalRequested"),
    (PromptSecurityViolationEvent, "PromptSecurityViolation"),
]

EXPECTED_EVENT_COUNT = 9


# ---- event_name / registration ---------------------------------------------


@pytest.mark.parametrize(("event_cls", "expected_name"), EVENT_CLASSES)
def test_event_name_matches_the_docs_061_vocabulary(
    event_cls: type[DomainEvent], expected_name: str
) -> None:
    assert event_cls.event_name == expected_name


@pytest.mark.parametrize(("event_cls", "expected_name"), EVENT_CLASSES)
def test_every_event_is_registered_with_the_default_registry(
    event_cls: type[DomainEvent], expected_name: str
) -> None:
    assert default_registry.is_registered(expected_name)
    assert default_registry.lookup(expected_name) is event_cls
    assert default_registry.lookup(expected_name, "v1") is event_cls
    assert expected_name in default_registry.all_event_names()
    assert default_registry.supported_versions(expected_name) == ["v1"]


def test_all_nine_events_are_distinct_classes_under_distinct_names() -> None:
    """A copy-paste that forgot to change ``event_name`` would silently
    shadow another event in the registry rather than fail loudly."""
    names = [name for _cls, name in EVENT_CLASSES]
    classes = [cls for cls, _name in EVENT_CLASSES]
    assert len(names) == EXPECTED_EVENT_COUNT
    assert len(set(names)) == EXPECTED_EVENT_COUNT
    assert len(set(classes)) == EXPECTED_EVENT_COUNT


def test_the_module_exports_exactly_the_nine_registered_events() -> None:
    """``__all__`` drifting from the module's real contents is how an
    event ends up published but unimportable by its consumers."""
    assert set(prompt_events.__all__) == {cls.__name__ for cls, _name in EVENT_CLASSES}


# ---- base shape / defaults --------------------------------------------------


@pytest.mark.parametrize(("event_cls", "_expected_name"), EVENT_CLASSES)
def test_every_event_is_a_v1_domain_event(
    event_cls: type[DomainEvent], _expected_name: str
) -> None:
    assert issubclass(event_cls, DomainEvent)
    assert issubclass(event_cls, BaseEvent)
    assert event_cls.event_type is EventType.DOMAIN
    assert event_cls.event_version == "v1"


@pytest.mark.parametrize(("event_cls", "_expected_name"), EVENT_CLASSES)
def test_constructing_requires_only_source_service(
    event_cls: type[DomainEvent], _expected_name: str
) -> None:
    before = datetime.now(UTC)
    event = event_cls(source_service=SOURCE_SERVICE)

    assert event.source_service == SOURCE_SERVICE
    assert event.payload == {}
    assert event.metadata == {}
    assert isinstance(event.event_id, uuid.UUID)
    assert before <= event.timestamp <= datetime.now(UTC)


@pytest.mark.parametrize(("event_cls", "_expected_name"), EVENT_CLASSES)
def test_source_service_is_mandatory(event_cls: type[DomainEvent], _expected_name: str) -> None:
    with pytest.raises(ValidationError):
        event_cls()


@pytest.mark.parametrize(("event_cls", "_expected_name"), EVENT_CLASSES)
def test_each_construction_gets_its_own_event_id(
    event_cls: type[DomainEvent], _expected_name: str
) -> None:
    first = event_cls(source_service=SOURCE_SERVICE)
    second = event_cls(source_service=SOURCE_SERVICE)
    assert first.event_id != second.event_id


@pytest.mark.parametrize(("event_cls", "_expected_name"), EVENT_CLASSES)
def test_organization_id_is_carried_verbatim(
    event_cls: type[DomainEvent], _expected_name: str
) -> None:
    organization_id = uuid.uuid4()
    event = event_cls(source_service=SOURCE_SERVICE, organization_id=organization_id)
    assert event.organization_id == organization_id


@pytest.mark.parametrize(("event_cls", "_expected_name"), EVENT_CLASSES)
def test_an_event_round_trips_through_its_own_json_dump(
    event_cls: type[DomainEvent], _expected_name: str
) -> None:
    organization_id = uuid.uuid4()
    event = event_cls(
        source_service=SOURCE_SERVICE,
        organization_id=organization_id,
        payload={"prompt_id": str(uuid.uuid4()), "nested": {"count": 2}},
    )
    dumped = event.model_dump()

    assert dumped["source_service"] == SOURCE_SERVICE
    assert dumped["organization_id"] == organization_id
    assert dumped["payload"]["nested"] == {"count": 2}
    assert event_cls.model_validate(dumped).payload == event.payload


# ---- payload shape, per producing flow --------------------------------------


def test_prompt_created_payload_shape() -> None:
    prompt_id = uuid.uuid4()
    event = PromptCreatedEvent(
        source_service=SOURCE_SERVICE,
        organization_id=uuid.uuid4(),
        payload={"prompt_id": str(prompt_id), "slug": "greeting"},
    )
    assert set(event.payload) == {"prompt_id", "slug"}
    assert event.payload["prompt_id"] == str(prompt_id)
    assert event.payload["slug"] == "greeting"


def test_prompt_updated_carries_either_the_identity_or_the_revision_shape() -> None:
    """``PromptUpdated`` is published by two distinct flows.

    ``PromptService.update`` announces an identity change and sends
    ``slug``; ``PromptService.add_version`` announces a new draft and
    sends ``version_number`` instead. Both are legitimate, which is
    exactly why the shape is asserted here rather than assumed.
    """
    prompt_id = str(uuid.uuid4())
    identity = PromptUpdatedEvent(
        source_service=SOURCE_SERVICE, payload={"prompt_id": prompt_id, "slug": "greeting"}
    )
    revision = PromptUpdatedEvent(
        source_service=SOURCE_SERVICE,
        payload={"prompt_id": prompt_id, "version_number": "1.1.0"},
    )
    assert set(identity.payload) == {"prompt_id", "slug"}
    assert set(revision.payload) == {"prompt_id", "version_number"}
    assert revision.payload["version_number"] == "1.1.0"


def test_prompt_published_payload_shape_including_the_rollback_flag() -> None:
    plain = PromptPublishedEvent(
        source_service=SOURCE_SERVICE,
        payload={"prompt_id": str(uuid.uuid4()), "slug": "greeting", "version_number": "1.0.0"},
    )
    rolled_back = PromptPublishedEvent(
        source_service=SOURCE_SERVICE,
        payload={
            "prompt_id": str(uuid.uuid4()),
            "slug": "greeting",
            "version_number": "1.0.0",
            "rolled_back": True,
        },
    )
    assert set(plain.payload) == {"prompt_id", "slug", "version_number"}
    assert "rolled_back" not in plain.payload
    assert rolled_back.payload["rolled_back"] is True


def test_prompt_deprecated_payload_shape() -> None:
    event = PromptDeprecatedEvent(
        source_service=SOURCE_SERVICE,
        payload={"prompt_id": str(uuid.uuid4()), "slug": "greeting"},
    )
    assert set(event.payload) == {"prompt_id", "slug"}


def test_prompt_executed_payload_shape() -> None:
    event = PromptExecutedEvent(
        source_service=SOURCE_SERVICE,
        payload={
            "prompt_id": str(uuid.uuid4()),
            "version_number": "1.0.0",
            "status": "succeeded",
            "total_tokens": 42,
        },
    )
    assert set(event.payload) == {"prompt_id", "version_number", "status", "total_tokens"}
    assert event.payload["total_tokens"] == 42


def test_prompt_evaluated_payload_shape() -> None:
    event = PromptEvaluatedEvent(
        source_service=SOURCE_SERVICE,
        payload={
            "prompt_version_id": str(uuid.uuid4()),
            "overall": 0.8125,
            "metrics": ["safety", "hallucination"],
        },
    )
    assert set(event.payload) == {"prompt_version_id", "overall", "metrics"}
    assert event.payload["metrics"] == ["safety", "hallucination"]


def test_prompt_optimized_payload_shape() -> None:
    event = PromptOptimizedEvent(
        source_service=SOURCE_SERVICE,
        payload={
            "prompt_id": str(uuid.uuid4()),
            "optimization_id": str(uuid.uuid4()),
            "resulting_version": "1.0.1",
            "token_saving": 8,
        },
    )
    assert set(event.payload) == {
        "prompt_id",
        "optimization_id",
        "resulting_version",
        "token_saving",
    }
    assert event.payload["resulting_version"] == "1.0.1"


def test_prompt_approval_requested_payload_shape() -> None:
    event = PromptApprovalRequestedEvent(
        source_service=SOURCE_SERVICE,
        payload={
            "prompt_version_id": str(uuid.uuid4()),
            "version_number": "1.0.0",
            "required_approvals": 2,
        },
    )
    assert set(event.payload) == {"prompt_version_id", "version_number", "required_approvals"}
    assert event.payload["required_approvals"] == 2


def test_prompt_security_violation_payload_carries_kinds_never_matched_text() -> None:
    """The one event whose payload shape is a security property.

    Its own docstring promises finding kinds and severities only. A
    payload that grew a ``matched`` or ``snippet`` key would put a
    detected secret onto the bus and into every subscriber's own logs.
    """
    event = PromptSecurityViolationEvent(
        source_service=SOURCE_SERVICE,
        payload={
            "prompt_version_id": str(uuid.uuid4()),
            "status": "blocked",
            "highest_severity": "critical",
            "finding_count": 1,
            "findings": ["secret_detected"],
        },
    )
    assert set(event.payload) == {
        "prompt_version_id",
        "status",
        "highest_severity",
        "finding_count",
        "findings",
    }
    assert event.payload["findings"] == ["secret_detected"]
    assert not {"matched", "snippet", "value", "text"} & set(event.payload)
