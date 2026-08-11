"""Document lifecycle beyond ingestion (docs/062 "DOCUMENT MANAGEMENT").

Reading, updating, archiving, deleting, and restoring documents. The
ingestion pipeline is separate -- see :mod:`app.services.ingestion` --
because that path is about turning bytes into chunks and this one is
about the record afterwards.

**Deleting removes the vectors immediately, even though the document row
is only soft-deleted.** A soft-deleted document whose vectors survive is
still retrievable, and every retrieval would surface content the
organization believes it deleted. The row is kept for audit; the vectors
are not, because they are the part that leaks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from shared_core.exceptions.not_found import NotFoundError
from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.events.rag_events import DocumentDeletedEvent
from app.models.analytics import RagAudit
from app.models.document import Document, DocumentChunk, DocumentVersion
from app.models.enums import AuditAction, ClassificationLevel, DocumentStatus
from app.repositories.analytics import RagAuditRepository
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentMetadataRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.embedding import EmbeddingVectorRepository
from app.security.access import (
    AccessContext,
    clearance_allows,
    filter_readable,
    require_read,
)
from app.types import EventPublisher

logger = get_logger("app.services.documents")

_SOURCE_SERVICE = "rag-service"


class DocumentService:
    """Reads and lifecycle transitions for stored documents."""

    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        chunks: DocumentChunkRepository,
        metadata: DocumentMetadataRepository,
        vectors: EmbeddingVectorRepository,
        audit: RagAuditRepository,
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._chunks = chunks
        self._metadata = metadata
        self._vectors = vectors
        self._audit = audit
        self._publish_event = publish_event

    async def list_documents(
        self,
        context: AccessContext,
        *,
        status: DocumentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        """Documents this caller may see, newest first.

        Filtered after the query rather than pushed into it, and that is a
        deliberate limit: the page size is what the caller asked for, so a
        caller with narrow clearance receives a short page rather than a
        full one. Correct, and visibly so -- the alternative of topping up
        the page would leak how many documents were withheld.
        """
        rows = await self._documents.list_for_org(
            context.organization_id, status=status, limit=limit, offset=offset
        )
        return filter_readable(context, rows)

    async def search_documents(
        self, context: AccessContext, query: str, *, limit: int = 50
    ) -> list[Document]:
        """Title and description search, access-filtered."""
        rows = await self._documents.search_in_org(context.organization_id, query, limit=limit)
        return filter_readable(context, rows)

    async def get_document(self, context: AccessContext, document_id: UUID) -> Document:
        """One document.

        Raises:
            NotFoundError: If it does not exist in this organization.
            AccessDenied: If the caller may not read it.
        """
        document = await self._documents.require_in_org(context.organization_id, document_id)
        require_read(context, document)
        return document

    async def get_current_version(
        self, context: AccessContext, document_id: UUID
    ) -> DocumentVersion:
        """The live version's extracted text.

        Raises:
            NotFoundError: If the document has no version yet -- it was
                created but never successfully parsed.
        """
        await self.get_document(context, document_id)
        version = await self._versions.get_current(document_id)
        if version is None:
            raise NotFoundError(
                f"Document {document_id!s} has no current version; it has not been "
                "successfully parsed."
            )
        return version

    async def list_chunks(
        self, context: AccessContext, document_id: UUID, *, limit: int = 1_000
    ) -> list[DocumentChunk]:
        """The chunks of the live version, in document order."""
        version = await self.get_current_version(context, document_id)
        return await self._chunks.list_for_version(version.id, limit=limit)

    async def update_document(
        self,
        context: AccessContext,
        document_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        classification: ClassificationLevel | None = None,
        allowed_roles: list[str] | None = None,
        tags: list[str] | None = None,
        owner_id: str | None = None,
        expires_at: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Document:
        """Change a document's descriptive and access fields.

        Content is not editable here. The text comes from a parse of the
        original bytes, and letting it be edited in place would break the
        one guarantee versions exist to provide: that what was indexed can
        still be shown as it was.

        Raises:
            ValidationError: If raising the classification above the
                caller's own clearance. Otherwise anyone could make a
                document invisible to themselves and, more to the point,
                mark content ``SECRET`` that they cannot verify the
                handling of.
        """
        document = await self.get_document(context, document_id)
        if classification is not None and classification != document.classification:
            self._require_clearance_for(context, classification)
            document.classification = classification
        if title is not None:
            document.title = title
        if description is not None:
            document.description = description
        if allowed_roles is not None:
            document.allowed_roles = list(allowed_roles)
        if tags is not None:
            document.tags = list(tags)
        if owner_id is not None:
            document.owner_id = owner_id
        if expires_at is not None:
            document.expires_at = expires_at

        updated = await self._documents.update(document)
        for key, value in (metadata or {}).items():
            await self._metadata.upsert(
                updated.id, updated.organization_id, key, value, extracted=False
            )
        await self._record(
            updated,
            action=AuditAction.DOCUMENT_UPDATED,
            summary=f"Updated {updated.title!r}.",
            context=context,
        )
        return updated

    @staticmethod
    def _require_clearance_for(context: AccessContext, classification: ClassificationLevel) -> None:
        """Refuse a classification the caller is not themselves cleared for."""
        if not clearance_allows(context, classification):
            raise ValidationError(
                f"Cannot classify a document {classification!s}: the caller is cleared "
                f"for {context.clearance!s}. Classifying content above your own "
                "clearance would make it unreadable to you and unverifiable by you."
            )

    async def archive_document(self, context: AccessContext, document_id: UUID) -> Document:
        """Take a document out of retrieval without destroying anything.

        The reversible option, and the one to reach for first: chunks and
        vectors are left in place, so restoring is instant and no
        re-embedding cost is incurred for a document that turns out to
        have been archived by mistake. Retrieval excludes archived
        documents by status.
        """
        document = await self.get_document(context, document_id)
        document.status = DocumentStatus.ARCHIVED
        archived = await self._documents.update(document)
        await self._record(
            archived,
            action=AuditAction.DOCUMENT_ARCHIVED,
            summary=f"Archived {archived.title!r}.",
            context=context,
        )
        await self._publish_event(
            DocumentDeletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=archived.organization_id,
                payload={"document_id": str(archived.id), "mode": "archived"},
            )
        )
        return archived

    async def restore_document(self, context: AccessContext, document_id: UUID) -> Document:
        """Return an archived document to the corpus.

        Looked up including soft-deleted rows, deliberately. The ordinary
        scoped lookup filters them out, so a caller trying to restore a
        deleted document would get a bare "not found" -- which reads as
        "you typed the wrong id" when the truth is "this one is gone and
        here is what to do about it".

        Raises:
            NotFoundError: If no such document exists in this organization.
            ValidationError: If the document was deleted rather than
                archived. Its vectors are gone, so "restoring" it would
                put a row back into the corpus that retrieval can never
                return -- worse than refusing, because it looks like it
                worked.
        """
        document = await self._documents.get_by_id(document_id, include_deleted=True)
        if document is None or document.organization_id != context.organization_id:
            raise NotFoundError(
                f"Document {document_id!s} was not found in organization "
                f"{context.organization_id!s}."
            )
        require_read(context, document)
        if document.deleted_at is not None or document.status == DocumentStatus.DELETED:
            raise ValidationError(
                f"Document {document_id!s} was deleted, not archived; its embeddings "
                "were removed. Re-ingest the source document to make it retrievable "
                "again."
            )
        if document.status != DocumentStatus.ARCHIVED:
            return document
        document.status = (
            DocumentStatus.INDEXED if document.last_indexed_at else DocumentStatus.CHUNKED
        )
        restored = await self._documents.update(document)
        await self._record(
            restored,
            action=AuditAction.DOCUMENT_RESTORED,
            summary=f"Restored {restored.title!r}.",
            context=context,
        )
        return restored

    async def delete_document(self, context: AccessContext, document_id: UUID) -> Document:
        """Remove a document from retrieval and destroy its embeddings.

        The vectors go immediately and permanently; the document row is
        soft-deleted so the audit trail still resolves its title. Keeping
        the vectors alongside a soft-deleted row would leave the content
        fully retrievable under a record that says it was deleted, which
        is the worst of both.
        """
        document = await self.get_document(context, document_id)
        removed_vectors = await self._vectors.delete_for_document(document.id)

        document.status = DocumentStatus.DELETED
        document.chunk_count = 0
        document.last_indexed_at = None
        document.indexed_checksum = None
        await self._documents.update(document)
        await self._documents.delete(document.id)

        await self._record(
            document,
            action=AuditAction.DOCUMENT_DELETED,
            summary=f"Deleted {document.title!r}; removed {removed_vectors} embedding(s).",
            context=context,
        )
        await self._publish_event(
            DocumentDeletedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=document.organization_id,
                payload={
                    "document_id": str(document.id),
                    "mode": "deleted",
                    "embeddings_removed": removed_vectors,
                },
            )
        )
        logger.info(
            "Deleted a document and its embeddings.",
            extra={
                "extra_fields": {
                    "document_id": str(document.id),
                    "embeddings_removed": removed_vectors,
                }
            },
        )
        return document

    async def expire_documents(self, moment: datetime, *, limit: int = 200) -> list[UUID]:
        """Archive every document past its own expiry date.

        Archived rather than deleted: an expiry date is a retention
        policy, and retention policies are set months in advance by people
        who are not present when they fire. Destroying embeddings on a
        timer nobody is watching is not recoverable; archiving is.
        """
        expired: list[UUID] = []
        for document in await self._documents.list_expired(moment, limit=limit):
            if document.status == DocumentStatus.ARCHIVED:
                continue
            document.status = DocumentStatus.ARCHIVED
            await self._documents.update(document)
            await self._record(
                document,
                action=AuditAction.DOCUMENT_ARCHIVED,
                summary=f"Archived {document.title!r} at its expiry date.",
                context=None,
            )
            expired.append(document.id)
        return expired

    async def _record(
        self,
        document: Document,
        *,
        action: AuditAction,
        summary: str,
        context: AccessContext | None,
    ) -> None:
        """Append one audit row."""
        await self._audit.create(
            RagAudit(
                organization_id=document.organization_id,
                action=action,
                entity_type="document",
                entity_id=document.id,
                entity_reference=document.title,
                actor_id=context.user_id if context else None,
                occurred_at=datetime.now(UTC),
                summary=summary[:512],
                succeeded=True,
            )
        )


__all__ = ["DocumentService"]
