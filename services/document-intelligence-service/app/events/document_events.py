"""The domain events this service publishes (docs/063 "EVENTS",
integrating Prompt 020).

All seven the spec names, plus two it implies: ``ProcessingFailed`` and
``DocumentDeleted``. Without the first, a consumer tracking a document
through the pipeline sees ``DocumentUploaded`` and then silence, and
cannot distinguish a failure from a slow queue. Without the second, a
consumer's view of the corpus learns that documents appear but never
that one went away, so it drifts permanently out of date.

**Versioned as ``v1`` from the start.** A consumer subscribing to
``ExtractionCompleted`` is coupled to this payload's shape, and the only
way to change it later without breaking them is to publish a ``v2``
alongside -- which requires the version to have been there from the
beginning.

**Every event is registered with the shared registry at import time.**
``EventManager.publish`` validates against
:data:`shared_core.events.registry.default_registry` and refuses anything
unregistered, so an unregistered event is not a warning -- it is an
``AIIOS-EVENT-0002`` on the request that triggered it. A test double for
the publisher will never surface that, which is exactly why the decorator
is here rather than assumed.

**Payloads carry identifiers and counts, never document content.** An
``ExtractionCompleted`` event carrying the extracted values would put
them on the message bus, in every queue that subscribes, and in any
dead-letter store it lands in -- including for the passport numbers and
account details this service is specifically built to find. Consumers
that need the values fetch them through the API, where access control
applies.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class DocumentUploadedEvent(DomainEvent):
    """A document was accepted and is queued for processing."""

    event_name: ClassVar[str] = "DocumentUploaded"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class OcrCompletedEvent(DomainEvent):
    """A document's pages were read by OCR.

    Carries the mean and the lowest page confidence rather than one
    number: a forty-page scan averaging 0.92 with one page at 0.31 is not
    a document anyone should treat as read, and the mean alone hides that
    page completely.
    """

    event_name: ClassVar[str] = "OCRCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ClassificationCompletedEvent(DomainEvent):
    """A document was assigned its categories."""

    event_name: ClassVar[str] = "ClassificationCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ExtractionCompletedEvent(DomainEvent):
    """Entities, tables and fields were extracted from a document."""

    event_name: ClassVar[str] = "ExtractionCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ValidationCompletedEvent(DomainEvent):
    """A document was validated against its rules."""

    event_name: ClassVar[str] = "ValidationCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReviewCompletedEvent(DomainEvent):
    """A human finished reviewing a document."""

    event_name: ClassVar[str] = "ReviewCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DocumentArchivedEvent(DomainEvent):
    """A document was archived and is no longer in the active corpus."""

    event_name: ClassVar[str] = "DocumentArchived"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ProcessingFailedEvent(DomainEvent):
    """A pipeline stage failed on a document.

    Not in docs/063's own list, and added deliberately: every other event
    here announces a success, so a consumer tracking a document sees
    ``DocumentUploaded`` and then nothing at all when processing fails.
    Silence is indistinguishable from a slow queue, and a consumer cannot
    escalate on it.
    """

    event_name: ClassVar[str] = "ProcessingFailed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DocumentDeletedEvent(DomainEvent):
    """A document was deleted and is no longer retrievable.

    Also not in the spec's list. A consumer maintaining its own index of
    the corpus would otherwise keep serving links to documents that no
    longer exist, with no event that would ever tell it otherwise.
    """

    event_name: ClassVar[str] = "DocumentDeleted"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "ClassificationCompletedEvent",
    "DocumentArchivedEvent",
    "DocumentDeletedEvent",
    "DocumentUploadedEvent",
    "ExtractionCompletedEvent",
    "OcrCompletedEvent",
    "ProcessingFailedEvent",
    "ReviewCompletedEvent",
    "ValidationCompletedEvent",
]
