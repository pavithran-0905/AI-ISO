"""Repositories for documents, versions, pages and layouts.

``require_in_org`` is named apart from ``BaseRepository``'s own unscoped
``require_by_id`` deliberately, per the convention every AI-IOS service
follows: the two differ only in whether they enforce tenant scoping, and
a name collision would make an unscoped lookup look like a scoped one at
the call site.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentLayout, DocumentPage, DocumentVersion
from app.models.enums import DocumentFormat, DocumentStatus

MAX_PAGE_SIZE = 200
"""A ceiling on any listing. A caller asking for everything gets the
first two hundred rows and a stable page size, rather than a query that
holds the connection open while it materialises a corpus."""


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

    async def find_by_checksum(self, organization_id: UUID, checksum: str) -> Document | None:
        """An existing document with the same bytes, or ``None``.

        Scoped to the organization on purpose: two tenants uploading the
        same public standard are not duplicates of each other, and
        telling one that its document already exists would leak that the
        other has it.
        """
        stmt = (
            self._base_select()
            .where(
                Document.organization_id == organization_id,
                Document.checksum == checksum,
                Document.duplicate_of_id.is_(None),
            )
            .order_by(Document.created_at)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_by_status(
        self,
        organization_id: UUID,
        status: DocumentStatus,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Document]:
        """Documents in *status*, oldest first."""
        stmt = (
            self._base_select()
            .where(
                Document.organization_id == organization_id,
                Document.status == status,
            )
            .order_by(Document.created_at)
            .offset(max(offset, 0))
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_awaiting_review(
        self, organization_id: UUID, *, limit: int = 50
    ) -> Sequence[Document]:
        """Documents flagged for review, least confident first.

        Ordered by confidence rather than by age: a reviewer's time is
        best spent where the extractor was least sure, and a queue in
        arrival order buries the worst documents behind the merely old
        ones. ``NULL`` confidence sorts first -- it means nothing scored
        the document at all.
        """
        stmt = (
            self._base_select()
            .where(
                Document.organization_id == organization_id,
                Document.requires_review.is_(True),
            )
            .order_by(Document.overall_confidence.asc().nulls_first(), Document.created_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_stalled(
        self, *, statuses: Sequence[DocumentStatus], older_than: datetime, limit: int = 100
    ) -> Sequence[Document]:
        """Documents stuck mid-pipeline since before *older_than*.

        Global rather than per-organization, because the worker that
        recovers them sweeps every tenant and has no organization of its
        own to scope to.
        """
        stmt = (
            select(Document)
            .where(
                Document.status.in_(list(statuses)),
                Document.updated_at < older_than,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.updated_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_expired(self, now: datetime, *, limit: int = 100) -> Sequence[Document]:
        """Documents whose retention period has passed.

        Already-archived documents are excluded, so the retention sweep is
        idempotent: without that, every tick would re-archive the same
        documents and write a fresh audit row for each, and the trail would
        fill with events that never happened.

        Global rather than per-organization, because the sweep runs for
        every tenant and has no organization of its own to scope to.
        """
        stmt = (
            select(Document)
            .where(
                Document.expires_at.is_not(None),
                Document.expires_at < now,
                Document.status != DocumentStatus.ARCHIVED,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.expires_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def search_in_org(
        self,
        organization_id: UUID,
        query: str,
        *,
        formats: Sequence[DocumentFormat] = (),
        limit: int = 25,
    ) -> Sequence[Document]:
        """Documents whose title or filename matches *query*."""
        pattern = f"%{query.strip()}%"
        stmt = self._base_select().where(Document.organization_id == organization_id)
        if query.strip():
            stmt = stmt.where(Document.title.ilike(pattern) | Document.filename.ilike(pattern))
        if formats:
            stmt = stmt.where(Document.document_format.in_([str(item) for item in formats]))
        stmt = stmt.order_by(Document.created_at.desc()).limit(min(limit, MAX_PAGE_SIZE))
        return (await self._session.execute(stmt)).scalars().all()

    async def count_by_status(self, organization_id: UUID) -> dict[str, int]:
        """How many documents sit in each status."""
        stmt = (
            select(Document.status, func.count())
            .where(
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .group_by(Document.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(status): int(count) for status, count in rows}

    async def count_by_format(self, organization_id: UUID) -> dict[str, int]:
        """How many documents of each format."""
        stmt = (
            select(Document.document_format, func.count())
            .where(
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .group_by(Document.document_format)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(fmt): int(count) for fmt, count in rows}

    async def mark_status(
        self, document_id: UUID, status: DocumentStatus, *, error: str | None = None
    ) -> None:
        """Move one document to *status* without loading it.

        A direct UPDATE because the pipeline calls this on every stage
        transition, and round-tripping a row with a hundred-kilobyte
        metadata blob to change one string is waste that shows up under
        load.
        """
        await self._session.execute(
            update(Document).where(Document.id == document_id).values(status=status, error=error)
        )


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    """Versions of a document's extracted content."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentVersion, tenant_scope=tenant_scope)

    async def list_for_document(self, document_id: UUID) -> Sequence[DocumentVersion]:
        """Every version, newest first."""
        stmt = (
            self._base_select()
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def current_for_document(self, document_id: UUID) -> DocumentVersion | None:
        """The version marked current, or ``None``."""
        stmt = self._base_select().where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.is_current.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def require_current(self, document_id: UUID) -> DocumentVersion:
        """The current version.

        Raises:
            NotFoundError: When the document has none, which means it was
                never successfully parsed.
        """
        found = await self.current_for_document(document_id)
        if found is None:
            raise NotFoundError(
                f"Document {document_id!s} has no current version; it has not "
                "been parsed successfully."
            )
        return found

    async def next_version_number(self, document_id: UUID) -> int:
        """What the next version of this document should be numbered."""
        stmt = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id
        )
        highest = (await self._session.execute(stmt)).scalar()
        return int(highest or 0) + 1

    async def demote_others(self, document_id: UUID, keep_id: UUID) -> None:
        """Clear ``is_current`` on every version but *keep_id*.

        Run before promoting a new version rather than after, so there is
        no instant at which two versions both claim to be current -- a
        reader between the two writes would otherwise get whichever the
        index returned first.
        """
        await self._session.execute(
            update(DocumentVersion)
            .where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.id != keep_id,
                DocumentVersion.is_current.is_(True),
            )
            .values(is_current=False)
        )


class DocumentPageRepository(BaseRepository[DocumentPage]):
    """Pages of one version of a document."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentPage, tenant_scope=tenant_scope)

    async def list_for_version(
        self, version_id: UUID, *, limit: int = MAX_PAGE_SIZE, offset: int = 0
    ) -> Sequence[DocumentPage]:
        """Pages in reading order."""
        stmt = (
            self._base_select()
            .where(DocumentPage.document_version_id == version_id)
            .order_by(DocumentPage.page_number)
            .offset(max(offset, 0))
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def get_page(self, version_id: UUID, page_number: int) -> DocumentPage | None:
        """One page by its number, or ``None``."""
        stmt = self._base_select().where(
            DocumentPage.document_version_id == version_id,
            DocumentPage.page_number == page_number,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def delete_for_version(self, version_id: UUID) -> int:
        """Soft-delete every page of a version, returning how many."""
        pages = await self.list_for_version(version_id, limit=MAX_PAGE_SIZE)
        for page in pages:
            await self.delete(page.id)
        return len(pages)


class DocumentLayoutRepository(BaseRepository[DocumentLayout]):
    """Layout regions detected on a page."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentLayout, tenant_scope=tenant_scope)

    async def list_for_page(self, page_id: UUID) -> Sequence[DocumentLayout]:
        """Regions in reading order."""
        stmt = (
            self._base_select()
            .where(DocumentLayout.document_page_id == page_id)
            .order_by(DocumentLayout.reading_order)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_version(self, version_id: UUID) -> Sequence[DocumentLayout]:
        """Every region across every page of a version, in reading order.

        Joined through :class:`DocumentPage` rather than filtered on a
        version column, because a region belongs to a *page*. Duplicating
        the version onto every region would be a second copy of a fact
        the page already holds, and the two would drift the first time a
        page was reassigned.
        """
        stmt = (
            self._base_select()
            .join(DocumentPage, DocumentPage.id == DocumentLayout.document_page_id)
            .where(DocumentPage.document_version_id == version_id)
            .order_by(DocumentPage.page_number, DocumentLayout.reading_order)
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "DocumentLayoutRepository",
    "DocumentPageRepository",
    "DocumentRepository",
    "DocumentVersionRepository",
]
