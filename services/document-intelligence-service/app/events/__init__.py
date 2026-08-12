"""Domain events published by this service.

The event module is imported here for its side effect: each class
registers with the shared registry at import time, and an event class
that was never imported is one ``EventManager.publish`` refuses with
``AIIOS-EVENT-0002`` at the moment a real document tries to use it.
"""

from app.events.document_events import (
    ClassificationCompletedEvent,
    DocumentArchivedEvent,
    DocumentDeletedEvent,
    DocumentUploadedEvent,
    ExtractionCompletedEvent,
    OcrCompletedEvent,
    ProcessingFailedEvent,
    ReviewCompletedEvent,
    ValidationCompletedEvent,
)

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
