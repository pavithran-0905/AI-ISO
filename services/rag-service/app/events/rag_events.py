"""The domain events this service publishes (docs/062 "EVENTS",
integrating Prompt 020).

All eight the spec names, plus one it implies: ``DocumentDeleted``.
Without it, a consumer maintaining its own view of the corpus learns that
documents appear and are re-indexed but never that one went away, so its
view drifts permanently out of date.

**Versioned as ``v1`` from the start.** A consumer subscribing to
``DocumentIndexed`` is coupled to this payload's shape, and the only way
to change it later without breaking them is to publish a ``v2`` alongside
-- which requires the version to have been there from the beginning.

**Every event is registered with the shared registry at import time.**
``EventManager.publish`` validates against
:data:`shared_core.events.registry.default_registry` and refuses anything
unregistered, so an unregistered event is not a warning -- it is an
``AIIOS-EVENT-0002`` on the request that triggered it. A test double for
the publisher will never surface that, which is exactly why the decorator
is here rather than assumed.

**Payloads carry identifiers, never content.** A ``DocumentIndexed``
event carrying the document's text would put that text on the message
bus, in every queue that subscribes, and in any dead-letter store it
lands in -- including for documents whose whole point is that they are
confidential. Consumers that need the content fetch it through the API,
where access control applies.
"""

from __future__ import annotations

from typing import ClassVar

from shared_core.events import default_registry
from shared_core.events.base import DomainEvent


@default_registry.register
class DocumentImportedEvent(DomainEvent):
    """A document was ingested from a source or uploaded."""

    event_name: ClassVar[str] = "DocumentImported"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DocumentIndexedEvent(DomainEvent):
    """A document's chunks were embedded and are now retrievable."""

    event_name: ClassVar[str] = "DocumentIndexed"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class DocumentDeletedEvent(DomainEvent):
    """A document was archived or deleted and is no longer retrievable.

    Not in docs/062's own list, and added deliberately: a consumer
    tracking the corpus learns about arrivals and reindexes but never
    about departures without it, and would keep serving links to
    documents this service has stopped returning.
    """

    event_name: ClassVar[str] = "DocumentDeleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class EmbeddingGeneratedEvent(DomainEvent):
    """A batch of embeddings was produced.

    Carries token and cost totals, which is what makes embedding spend
    attributable to something other than a single monthly invoice.
    """

    event_name: ClassVar[str] = "EmbeddingGenerated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class RetrievalExecutedEvent(DomainEvent):
    """A retrieval ran.

    Published for empty results too. A consumer building a coverage
    dashboard needs the misses more than the hits -- the hits are what
    already works.
    """

    event_name: ClassVar[str] = "RetrievalExecuted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ContextGeneratedEvent(DomainEvent):
    """A context block was assembled for a caller."""

    event_name: ClassVar[str] = "ContextGenerated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class ReindexCompletedEvent(DomainEvent):
    """An indexing job finished.

    Published for partial and failed outcomes as well as clean ones: a
    reindex that half-worked is the case somebody most needs to hear
    about, and publishing only successes makes it invisible.
    """

    event_name: ClassVar[str] = "ReindexCompleted"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class KnowledgeSourceUpdatedEvent(DomainEvent):
    """A knowledge source was created, reconfigured, or synced."""

    event_name: ClassVar[str] = "KnowledgeSourceUpdated"
    event_version: ClassVar[str] = "v1"


@default_registry.register
class EvaluationCompletedEvent(DomainEvent):
    """A retrieval evaluation run finished, with its metric scores."""

    event_name: ClassVar[str] = "EvaluationCompleted"
    event_version: ClassVar[str] = "v1"


__all__ = [
    "ContextGeneratedEvent",
    "DocumentDeletedEvent",
    "DocumentImportedEvent",
    "DocumentIndexedEvent",
    "EmbeddingGeneratedEvent",
    "EvaluationCompletedEvent",
    "KnowledgeSourceUpdatedEvent",
    "ReindexCompletedEvent",
    "RetrievalExecutedEvent",
]
