"""Repositories for documents, versions, chunks, and metadata.

``require_in_org`` is named apart from ``BaseRepository``'s own unscoped
``require_by_id`` deliberately, per the convention every AI-IOS service
follows: the two differ only in whether they enforce tenant scoping, and
a name collision would make an unscoped lookup look like a scoped one at
the call site.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.search import apply_search
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DocumentMetadata, DocumentVersion
from app.models.enums import ClassificationLevel, DocumentStatus, SourceKind


class DocumentRepository(BaseRepository[Document]):
    """CRUD plus lookup for :class:`Document`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Document, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, document_id: UUID) -> Document:
        """Return *document_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such document exists in that organization.
        """
        stmt = self._base_select().where(
            Document.id == document_id, Document.organization_id == organization_id
        )
        found: Document | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Document {document_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def get_by_external_id(self, organization_id: UUID, external_id: str) -> Document | None:
        """The document previously imported under *external_id*, or ``None``.

        The idempotency lookup every source sync depends on: a Confluence
        page re-fetched on every sweep must update its document rather
        than create a second one.
        """
        stmt = self._base_select().where(
            Document.organization_id == organization_id, Document.external_id == external_id
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def get_by_checksum(self, organization_id: UUID, checksum: str) -> Document | None:
        """A document with identical content, or ``None``.

        Catches the same file uploaded twice under different names, which
        would otherwise be embedded twice and returned twice by every
        query that matched it.
        """
        stmt = self._base_select().where(
            Document.organization_id == organization_id, Document.checksum == checksum
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        status: DocumentStatus | None = None,
        source_kind: SourceKind | None = None,
        classification: ClassificationLevel | None = None,
        knowledge_source_id: UUID | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Document]:
        """Documents in *organization_id*, newest first."""
        stmt = self._base_select().where(Document.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Document.status == status)
        if source_kind is not None:
            stmt = stmt.where(Document.source_kind == source_kind)
        if classification is not None:
            stmt = stmt.where(Document.classification == classification)
        if knowledge_source_id is not None:
            stmt = stmt.where(Document.knowledge_source_id == knowledge_source_id)
        stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        return list((await self._session.execute(stmt)).scalars().all())

    async def search_in_org(
        self, organization_id: UUID, query: str, *, limit: int = 50
    ) -> list[Document]:
        """Text search over title and description.

        Named apart from ``BaseRepository.search`` for the same reason
        ``require_in_org`` is: the base takes an explicit field list and
        no tenant, so sharing the name would break substitutability and
        make an unscoped search indistinguishable from a scoped one.
        """
        base = self._base_select().where(Document.organization_id == organization_id)
        stmt = apply_search(base, Document, ["title", "description"], query).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_needing_index(
        self, organization_id: UUID | None = None, *, limit: int = 100
    ) -> list[Document]:
        """Documents whose content has changed since they were indexed.

        The selector an incremental sweep runs on: ``checksum`` differing
        from ``indexed_checksum`` is exactly "this document changed", and
        a ``NULL`` indexed checksum means it was never indexed at all.
        Comparing content instead would mean re-reading every document on
        every sweep.

        **``FAILED`` documents are included, deliberately.** Most indexing
        failures are transient -- the embedding provider was rate-limited,
        the vector store was briefly unreachable -- and excluding them
        means an outage permanently strands every document it touched,
        with no path back except somebody noticing and re-queueing by
        hand. A genuinely poisonous document does then fail on every
        sweep, which is noisy; it is also visible, and visible-and-noisy
        beats silently-never-retried.
        """
        stmt = self._base_select().where(
            Document.status.notin_([DocumentStatus.ARCHIVED, DocumentStatus.DELETED]),
            (Document.indexed_checksum.is_(None))
            | (Document.indexed_checksum != Document.checksum),
        )
        if organization_id is not None:
            stmt = stmt.where(Document.organization_id == organization_id)
        stmt = stmt.order_by(Document.created_at.asc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_expired(self, moment: datetime, *, limit: int = 200) -> list[Document]:
        """Documents past their own expiry date."""
        stmt = (
            self._base_select()
            .where(
                Document.expires_at.is_not(None),
                Document.expires_at <= moment,
                Document.status != DocumentStatus.ARCHIVED,
            )
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_organization_ids(self, *, limit: int = 200) -> list[UUID]:
        """Every organization with at least one document.

        Backs the statistics rollup, which iterates tenants without an
        organizations table of its own.
        """
        stmt = select(Document.organization_id).distinct().limit(limit)
        return [row for row in (await self._session.execute(stmt)).scalars().all() if row]

    async def count_by_status(self, organization_id: UUID) -> dict[str, int]:
        """How many documents sit in each status."""
        stmt = (
            select(Document.status, func.count())
            .where(Document.organization_id == organization_id)
            .group_by(Document.status)
        )
        return {str(status): int(count) for status, count in (await self._session.execute(stmt))}

    async def list_in_window(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> list[Document]:
        """Documents created inside one window."""
        stmt = self._base_select().where(
            Document.organization_id == organization_id,
            Document.created_at >= since,
            Document.created_at < until,
        )
        return list((await self._session.execute(stmt)).scalars().all())


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    """CRUD plus lookup for :class:`DocumentVersion`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentVersion, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, version_id: UUID) -> DocumentVersion:
        """Return *version_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such version exists in that organization.
        """
        stmt = self._base_select().where(
            DocumentVersion.id == version_id,
            DocumentVersion.organization_id == organization_id,
        )
        found: DocumentVersion | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"DocumentVersion {version_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def get_current(self, document_id: UUID) -> DocumentVersion | None:
        """The live version of *document_id*, or ``None``."""
        stmt = self._base_select().where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.is_current.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_document(
        self, document_id: UUID, *, limit: int = 100
    ) -> list[DocumentVersion]:
        """Every version of one document, newest first."""
        stmt = (
            self._base_select()
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def next_version_number(self, document_id: UUID) -> int:
        """The next version number for *document_id*.

        Derived from the highest existing rather than a stored counter:
        a counter and the rows it counts can disagree, and the rows are
        the truth.
        """
        stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
        highest = (await self._session.execute(stmt)).scalar()
        return int(highest or 0) + 1

    async def clear_current(self, document_id: UUID) -> int:
        """Demote every currently-live version of *document_id*."""
        rows = await self.list_for_document(document_id)
        demoted = 0
        for row in rows:
            if row.is_current:
                row.is_current = False
                await self.update(row)
                demoted += 1
        return demoted


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """CRUD plus lookup for :class:`DocumentChunk`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentChunk, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, chunk_id: UUID) -> DocumentChunk:
        """Return *chunk_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such chunk exists in that organization.
        """
        stmt = self._base_select().where(
            DocumentChunk.id == chunk_id, DocumentChunk.organization_id == organization_id
        )
        found: DocumentChunk | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"DocumentChunk {chunk_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_for_version(
        self, document_version_id: UUID, *, limit: int = 10_000
    ) -> list[DocumentChunk]:
        """Every chunk of one version, in document order."""
        stmt = (
            self._base_select()
            .where(DocumentChunk.document_version_id == document_version_id)
            .order_by(DocumentChunk.sequence.asc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_by_ids(
        self, organization_id: UUID, chunk_ids: list[UUID]
    ) -> list[DocumentChunk]:
        """Chunks by id, scoped to one organization.

        The hydration step after a vector search: the store returns ids
        and scores, and this fetches the text and provenance to build
        citations from.
        """
        if not chunk_ids:
            return []
        stmt = self._base_select().where(
            DocumentChunk.organization_id == organization_id,
            DocumentChunk.id.in_(chunk_ids),
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_unembedded(
        self, organization_id: UUID | None = None, *, limit: int = 500
    ) -> list[DocumentChunk]:
        """Chunks with no vector yet.

        Reads the denormalised ``is_embedded`` flag rather than
        anti-joining ``embedding_vectors``: one indexed boolean beats a
        NOT EXISTS against a table with a row per chunk per model, on the
        query the indexing sweep runs constantly.
        """
        stmt = self._base_select().where(DocumentChunk.is_embedded.is_(False))
        if organization_id is not None:
            stmt = stmt.where(DocumentChunk.organization_id == organization_id)
        stmt = stmt.order_by(DocumentChunk.created_at.asc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def search_keyword(
        self, organization_id: UUID, query: str, *, limit: int = 100
    ) -> list[DocumentChunk]:
        """Candidate chunks for the lexical arm of hybrid search.

        Selects candidates with PostgreSQL's own index; the *ranking*
        then happens in :mod:`app.hybrid_search.bm25`. Doing both here
        would mean either ranking without term statistics or loading the
        corpus into Python.
        """
        base = self._base_select().where(DocumentChunk.organization_id == organization_id)
        stmt = apply_search(base, DocumentChunk, ["content"], query).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def delete_for_version(self, document_version_id: UUID) -> int:
        """Remove every chunk of one version."""
        rows = await self.list_for_version(document_version_id)
        for row in rows:
            await self.delete(row.id)
        return len(rows)

    async def count_for_org(self, organization_id: UUID) -> int:
        """How many chunks one organization holds."""
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.organization_id == organization_id)
        )
        return int((await self._session.execute(stmt)).scalar_one())


class DocumentMetadataRepository(BaseRepository[DocumentMetadata]):
    """CRUD plus lookup for :class:`DocumentMetadata`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentMetadata, tenant_scope=tenant_scope)

    async def list_for_document(self, document_id: UUID) -> list[DocumentMetadata]:
        """Every metadata row for one document."""
        stmt = (
            self._base_select()
            .where(DocumentMetadata.document_id == document_id)
            .order_by(DocumentMetadata.key.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_value(self, document_id: UUID, key: str) -> DocumentMetadata | None:
        """One metadata row by key, or ``None``."""
        stmt = self._base_select().where(
            DocumentMetadata.document_id == document_id, DocumentMetadata.key == key
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def upsert(
        self, document_id: UUID, organization_id: UUID, key: str, value: str, *, extracted: bool
    ) -> DocumentMetadata:
        """Set one metadata value, replacing any existing one.

        An extracted value never overwrites an asserted one: a human who
        corrected the parser's guess must not have that correction undone
        by the next re-parse.
        """
        existing = await self.get_value(document_id, key)
        if existing is not None:
            if extracted and not existing.is_extracted:
                return existing
            existing.value = value
            existing.is_extracted = extracted
            return await self.update(existing)
        return await self.create(
            DocumentMetadata(
                organization_id=organization_id,
                document_id=document_id,
                key=key,
                value=value,
                is_extracted=extracted,
            )
        )

    async def find_documents(
        self, organization_id: UUID, filters: dict[str, str], *, limit: int = 500
    ) -> set[UUID]:
        """Document ids matching every metadata filter.

        Intersects per-key matches rather than OR-ing them: a caller
        asking for ``department=finance`` *and* ``year=2026`` means both,
        and returning either would widen the result rather than narrow
        it.
        """
        if not filters:
            return set()
        matched: set[UUID] | None = None
        for key, value in filters.items():
            stmt = (
                select(DocumentMetadata.document_id)
                .where(
                    DocumentMetadata.organization_id == organization_id,
                    DocumentMetadata.key == key,
                    DocumentMetadata.value == value,
                    DocumentMetadata.is_filterable.is_(True),
                )
                .limit(limit)
            )
            ids = set((await self._session.execute(stmt)).scalars().all())
            matched = ids if matched is None else (matched & ids)
            if not matched:
                return set()
        return matched or set()


__all__ = [
    "DocumentChunkRepository",
    "DocumentMetadataRepository",
    "DocumentRepository",
    "DocumentVersionRepository",
]
