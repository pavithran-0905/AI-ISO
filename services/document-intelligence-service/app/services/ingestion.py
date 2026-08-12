"""Document ingestion (docs/063 "DOCUMENT LIFECYCLE").

Accepting a document: check its size, identify its format, hash it,
detect whether it is a duplicate, and record it as ``UPLOADED`` with a
queued processing job.

**Ingestion does not parse.** It stores the bytes and queues the work,
because parsing a two-hundred-page scan inside the upload request holds
an HTTP connection open for minutes and fails the whole upload if one
page is malformed. The pipeline runs against the stored bytes afterwards.

**A duplicate is recorded, not rejected.** The same bytes uploaded twice
is usually a person re-sending rather than an error, and refusing the
second upload loses the fact that it happened. The new document is
stored, linked to the original through ``duplicate_of_id``, and skips
re-processing -- the results are already there.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.documents.detection import detect_format
from app.events.document_events import DocumentUploadedEvent
from app.models.document import Document
from app.models.enums import (
    DocumentFormat,
    DocumentStatus,
    JobStatus,
    ProcessingStage,
    needs_ocr,
)
from app.models.operations import DocumentAudit, DocumentProcessingJob
from app.repositories.document import DocumentRepository
from app.repositories.operations import (
    DocumentAuditRepository,
    DocumentProcessingJobRepository,
)
from app.types import EventPublisher

_LOGGER = get_logger(__name__)
_SOURCE_SERVICE = "document-intelligence-service"

DEFAULT_STAGES: tuple[ProcessingStage, ...] = (
    ProcessingStage.PARSING,
    ProcessingStage.OCR,
    ProcessingStage.LAYOUT,
    ProcessingStage.CLASSIFICATION,
    ProcessingStage.ENTITY_EXTRACTION,
    ProcessingStage.TABLE_EXTRACTION,
    ProcessingStage.FORM_EXTRACTION,
    ProcessingStage.VALIDATION_RULES,
)
"""The stages a newly uploaded document runs, in order. Summarization and
translation are not here: both are expensive and neither is needed to
decide whether a document is usable, so they are requested explicitly."""


@dataclass(slots=True)
class IngestionResult:
    """What ingestion produced."""

    document: Document
    job: DocumentProcessingJob | None
    is_duplicate: bool = False
    duplicate_of: Document | None = None

    @property
    def will_process(self) -> bool:
        return self.job is not None


class IngestionService:
    """Accepts documents and queues them for processing."""

    def __init__(
        self,
        *,
        documents: DocumentRepository,
        jobs: DocumentProcessingJobRepository,
        audits: DocumentAuditRepository,
        publish: EventPublisher,
        max_bytes: int,
    ) -> None:
        self._documents = documents
        self._jobs = jobs
        self._audits = audits
        self._publish = publish
        self._max_bytes = max_bytes

    async def ingest(
        self,
        *,
        organization_id: UUID,
        data: bytes,
        title: str,
        filename: str | None = None,
        content_type: str | None = None,
        uploaded_by: str | None = None,
        tags: list[str] | None = None,
        stages: tuple[ProcessingStage, ...] = DEFAULT_STAGES,
        priority: int = 100,
    ) -> IngestionResult:
        """Accept one document.

        Raises:
            ValidationError: When the payload is empty, too large, or of a
                format this service cannot read. Each is rejected at the
                door rather than stored and failed later, because a
                caller can act on a synchronous rejection and cannot act
                on a job that fails an hour afterwards.
        """
        self._check_size(data)
        guess = detect_format(data, filename=filename, content_type=content_type)
        if not guess.is_known:
            raise ValidationError(
                f"The format of {filename or 'this upload'} could not be identified: "
                f"{guess.evidence}. Supply a filename or content type."
            )

        checksum = f"sha256:{hashlib.sha256(data).hexdigest()}"
        existing = await self._documents.find_by_checksum(organization_id, checksum)

        document = await self._documents.create(
            Document(
                organization_id=organization_id,
                title=title.strip() or (filename or "Untitled document"),
                filename=filename,
                document_format=guess.format,
                content_type=content_type,
                status=DocumentStatus.UPLOADED,
                byte_size=len(data),
                checksum=checksum,
                requires_ocr=needs_ocr(guess.format),
                tags=list(tags or []),
                uploaded_by=uploaded_by,
                duplicate_of_id=existing.id if existing is not None else None,
                document_metadata={
                    "format_confidence": guess.confidence,
                    "format_evidence": guess.evidence,
                },
            )
        )

        job = None
        if existing is None:
            job = await self._queue(document, stages, priority, uploaded_by)
        else:
            _LOGGER.info(
                "document.duplicate",
                extra={"document_id": str(document.id), "duplicate_of": str(existing.id)},
            )

        await self._audits.create(
            DocumentAudit(
                organization_id=organization_id,
                action="uploaded",
                entity_type="document",
                entity_id=document.id,
                occurred_at=datetime.now(UTC),
                actor_id=uploaded_by,
                summary=f"{guess.format!s} document accepted ({len(data)} bytes)",
                details={"checksum": checksum, "duplicate": existing is not None},
            )
        )

        await self._publish(
            DocumentUploadedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "document_id": str(document.id),
                    "format": str(guess.format),
                    "byte_size": len(data),
                    "requires_ocr": document.requires_ocr,
                    "is_duplicate": existing is not None,
                    "job_id": str(job.id) if job is not None else None,
                },
            )
        )
        return IngestionResult(
            document=document,
            job=job,
            is_duplicate=existing is not None,
            duplicate_of=existing,
        )

    def _check_size(self, data: bytes) -> None:
        """Reject an empty or oversized payload.

        Raises:
            ValidationError: With the actual and permitted sizes, so the
                caller can tell how far over it is rather than having to
                bisect.
        """
        if not data:
            raise ValidationError("The upload is empty; there is no document to ingest.")
        if len(data) > self._max_bytes:
            raise ValidationError(
                f"The upload is {len(data)} bytes, above the {self._max_bytes}-byte limit."
            )

    async def _queue(
        self,
        document: Document,
        stages: tuple[ProcessingStage, ...],
        priority: int,
        requested_by: str | None,
    ) -> DocumentProcessingJob:
        """Queue the pipeline run for a document."""
        return await self._jobs.create(
            DocumentProcessingJob(
                organization_id=document.organization_id,
                document_id=document.id,
                status=JobStatus.QUEUED,
                stages=[str(stage) for stage in stages],
                priority=priority,
                scheduled_at=datetime.now(UTC),
                requested_by=requested_by,
            )
        )

    async def requeue(
        self,
        *,
        organization_id: UUID,
        document_id: UUID,
        stages: tuple[ProcessingStage, ...] = DEFAULT_STAGES,
        priority: int = 50,
        requested_by: str | None = None,
    ) -> DocumentProcessingJob:
        """Queue another pipeline run over an existing document.

        Raised in priority by default, because a reprocess is nearly
        always a human reacting to a bad result and waiting on the answer,
        while the ordinary queue is machines.

        Raises:
            NotFoundError: If the document is not in that organization.
        """
        document = await self._documents.require_in_org(organization_id, document_id)
        job = await self._queue(document, stages, priority, requested_by)
        await self._documents.mark_status(document.id, DocumentStatus.UPLOADED)
        await self._audits.create(
            DocumentAudit(
                organization_id=organization_id,
                action="requeued",
                entity_type="document",
                entity_id=document.id,
                occurred_at=datetime.now(UTC),
                actor_id=requested_by,
                summary=f"Reprocessing queued for stages {[str(s) for s in stages]}",
            )
        )
        return job


def checksum_of(data: bytes) -> str:
    """The checksum this service identifies a document by."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def is_supported(fmt: DocumentFormat) -> bool:
    """Whether a parser exists for *fmt*."""
    from app.documents.parser import supported_formats  # noqa: PLC0415 -- avoids a cycle

    return fmt in supported_formats()


__all__ = [
    "DEFAULT_STAGES",
    "IngestionResult",
    "IngestionService",
    "checksum_of",
    "is_supported",
]
