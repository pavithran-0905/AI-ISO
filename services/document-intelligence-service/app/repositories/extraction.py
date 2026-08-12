"""Repositories for everything extracted from a document.

Every one of these hangs off a *version* rather than a document, and
every listing scopes to one. Extraction results belong to the parse that
produced them: re-running the pipeline writes a new version, and a query
by document alone would return two generations of results mixed together
with no way to tell which is current.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DocumentCategory, EntityKind, SummaryKind
from app.models.extraction import (
    DocumentClassification,
    DocumentEntity,
    DocumentForm,
    DocumentKeyValue,
    DocumentSummary,
    DocumentTable,
    DocumentTranslation,
)
from app.repositories.document import MAX_PAGE_SIZE


class DocumentEntityRepository(BaseRepository[DocumentEntity]):
    """Entities extracted from a document version."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentEntity, tenant_scope=tenant_scope)

    async def list_for_version(
        self,
        version_id: UUID,
        *,
        kinds: Sequence[EntityKind] = (),
        minimum_confidence: float = 0.0,
        limit: int = MAX_PAGE_SIZE,
        offset: int = 0,
    ) -> Sequence[DocumentEntity]:
        """Entities in document order, filtered by kind and confidence."""
        stmt = self._base_select().where(DocumentEntity.document_version_id == version_id)
        if kinds:
            stmt = stmt.where(DocumentEntity.entity_kind.in_([str(kind) for kind in kinds]))
        if minimum_confidence > 0:
            stmt = stmt.where(DocumentEntity.confidence >= minimum_confidence)
        stmt = (
            stmt.order_by(DocumentEntity.start_offset)
            .offset(max(offset, 0))
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_value(
        self, organization_id: UUID, normalized_value: str, *, limit: int = 50
    ) -> Sequence[DocumentEntity]:
        """Every occurrence of one value across an organization's corpus.

        Matched on the *normalized* value, so "+44 20 7946 0018" and
        "(020) 7946 0018" find each other -- which is the only way this
        query answers the question anyone actually asks of it.
        """
        stmt = (
            self._base_select()
            .where(
                DocumentEntity.organization_id == organization_id,
                DocumentEntity.normalized_value == normalized_value,
            )
            .order_by(DocumentEntity.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def count_by_kind(self, version_id: UUID) -> dict[str, int]:
        """How many entities of each kind this version yielded."""
        stmt = (
            select(DocumentEntity.entity_kind, func.count())
            .where(
                DocumentEntity.document_version_id == version_id,
                DocumentEntity.deleted_at.is_(None),
            )
            .group_by(DocumentEntity.entity_kind)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(kind): int(count) for kind, count in rows}

    async def redact_kinds(self, version_id: UUID, kinds: Sequence[EntityKind]) -> int:
        """Mark entities of *kinds* redacted, returning how many."""
        if not kinds:
            return 0
        result = await self._session.execute(
            update(DocumentEntity)
            .where(
                DocumentEntity.document_version_id == version_id,
                DocumentEntity.entity_kind.in_([str(kind) for kind in kinds]),
            )
            .values(is_redacted=True)
        )
        return int(result.rowcount or 0)


class DocumentTableRepository(BaseRepository[DocumentTable]):
    """Tables extracted from a document version."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentTable, tenant_scope=tenant_scope)

    async def list_for_version(self, version_id: UUID) -> Sequence[DocumentTable]:
        """Tables in document order.

        Only top-level tables: a nested table is reachable through its
        parent, and returning both would have a caller iterating the same
        rows twice.
        """
        stmt = (
            self._base_select()
            .where(
                DocumentTable.document_version_id == version_id,
                DocumentTable.parent_table_id.is_(None),
            )
            .order_by(DocumentTable.sequence)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_children(self, table_id: UUID) -> Sequence[DocumentTable]:
        """Tables nested inside *table_id*."""
        stmt = (
            self._base_select()
            .where(DocumentTable.parent_table_id == table_id)
            .order_by(DocumentTable.sequence)
        )
        return (await self._session.execute(stmt)).scalars().all()


class DocumentFormRepository(BaseRepository[DocumentForm]):
    """Forms detected on a document version."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentForm, tenant_scope=tenant_scope)

    async def list_for_version(self, version_id: UUID) -> Sequence[DocumentForm]:
        """Forms in document order."""
        stmt = (
            self._base_select()
            .where(DocumentForm.document_version_id == version_id)
            .order_by(DocumentForm.sequence)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_template(
        self, organization_id: UUID, template_id: UUID, *, limit: int = 50
    ) -> Sequence[DocumentForm]:
        """Every instance of one template."""
        stmt = (
            self._base_select()
            .where(
                DocumentForm.organization_id == organization_id,
                DocumentForm.template_id == template_id,
            )
            .order_by(DocumentForm.created_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DocumentKeyValueRepository(BaseRepository[DocumentKeyValue]):
    """Key-value fields extracted from a document version."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentKeyValue, tenant_scope=tenant_scope)

    async def list_for_version(
        self, version_id: UUID, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DocumentKeyValue]:
        """Fields in the order they appear."""
        stmt = (
            self._base_select()
            .where(DocumentKeyValue.document_version_id == version_id)
            .order_by(DocumentKeyValue.page_number, DocumentKeyValue.top, DocumentKeyValue.key)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_for_form(self, form_id: UUID) -> Sequence[DocumentKeyValue]:
        """Fields belonging to one form."""
        stmt = (
            self._base_select()
            .where(DocumentKeyValue.document_form_id == form_id)
            .order_by(DocumentKeyValue.top, DocumentKeyValue.key)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find_by_key(self, version_id: UUID, normalized_key: str) -> DocumentKeyValue | None:
        """One field by its normalized key, or ``None``."""
        stmt = self._base_select().where(
            DocumentKeyValue.document_version_id == version_id,
            DocumentKeyValue.normalized_key == normalized_key,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_low_confidence(
        self, version_id: UUID, threshold: float, *, limit: int = MAX_PAGE_SIZE
    ) -> Sequence[DocumentKeyValue]:
        """Fields below *threshold*, least confident first.

        The reviewer's work queue for one document: fields already
        corrected are excluded, because re-presenting a field a human has
        already fixed is how a review queue never empties.
        """
        stmt = (
            self._base_select()
            .where(
                DocumentKeyValue.document_version_id == version_id,
                DocumentKeyValue.confidence < threshold,
                DocumentKeyValue.corrected_value.is_(None),
            )
            .order_by(DocumentKeyValue.confidence)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def correction_rate(self, version_id: UUID) -> float | None:
        """Fields a human changed over fields a human saw.

        ``None`` where nothing was reviewed: reporting 0.0 for
        "unmeasured" would read as a perfect extractor, which is the most
        misleading number this query could return.
        """
        stmt = select(
            func.count(),
            func.count(DocumentKeyValue.corrected_value),
        ).where(
            DocumentKeyValue.document_version_id == version_id,
            DocumentKeyValue.deleted_at.is_(None),
            DocumentKeyValue.is_confirmed.is_(True),
        )
        seen, corrected = (await self._session.execute(stmt)).one()
        if not seen:
            return None
        return round(int(corrected) / int(seen), 4)


class DocumentClassificationRepository(BaseRepository[DocumentClassification]):
    """Classifications assigned to a document version."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentClassification, tenant_scope=tenant_scope)

    async def list_for_version(self, version_id: UUID) -> Sequence[DocumentClassification]:
        """Labels, most confident first."""
        stmt = (
            self._base_select()
            .where(DocumentClassification.document_version_id == version_id)
            .order_by(DocumentClassification.confidence.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def primary_for_version(self, version_id: UUID) -> DocumentClassification | None:
        """The primary label, or ``None``."""
        stmt = self._base_select().where(
            DocumentClassification.document_version_id == version_id,
            DocumentClassification.is_primary.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def demote_others(self, version_id: UUID, keep_id: UUID) -> None:
        """Clear ``is_primary`` on every other label of this version."""
        await self._session.execute(
            update(DocumentClassification)
            .where(
                DocumentClassification.document_version_id == version_id,
                DocumentClassification.id != keep_id,
                DocumentClassification.is_primary.is_(True),
            )
            .values(is_primary=False)
        )

    async def count_by_category(self, organization_id: UUID) -> dict[str, int]:
        """How many documents fall into each primary category."""
        stmt = (
            select(DocumentClassification.category, func.count())
            .where(
                DocumentClassification.organization_id == organization_id,
                DocumentClassification.is_primary.is_(True),
                DocumentClassification.deleted_at.is_(None),
            )
            .group_by(DocumentClassification.category)
        )
        rows = (await self._session.execute(stmt)).all()
        return {str(category): int(count) for category, count in rows}

    async def list_by_category(
        self, organization_id: UUID, category: DocumentCategory, *, limit: int = 50
    ) -> Sequence[DocumentClassification]:
        """Documents whose primary label is *category*."""
        stmt = (
            self._base_select()
            .where(
                DocumentClassification.organization_id == organization_id,
                DocumentClassification.category == category,
                DocumentClassification.is_primary.is_(True),
            )
            .order_by(DocumentClassification.confidence.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class DocumentSummaryRepository(BaseRepository[DocumentSummary]):
    """Summaries of a document version."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentSummary, tenant_scope=tenant_scope)

    async def list_for_version(self, version_id: UUID) -> Sequence[DocumentSummary]:
        """Every summary of this version."""
        stmt = (
            self._base_select()
            .where(DocumentSummary.document_version_id == version_id)
            .order_by(DocumentSummary.summary_kind)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find_of_kind(self, version_id: UUID, kind: SummaryKind) -> DocumentSummary | None:
        """The summary of one kind, or ``None``."""
        stmt = self._base_select().where(
            DocumentSummary.document_version_id == version_id,
            DocumentSummary.summary_kind == kind,
        )
        return (await self._session.execute(stmt)).scalars().first()


class DocumentTranslationRepository(BaseRepository[DocumentTranslation]):
    """Translations of a document version."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, DocumentTranslation, tenant_scope=tenant_scope)

    async def list_for_version(self, version_id: UUID) -> Sequence[DocumentTranslation]:
        """Every translation of this version."""
        stmt = (
            self._base_select()
            .where(DocumentTranslation.document_version_id == version_id)
            .order_by(DocumentTranslation.target_language)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def find_in_language(
        self, version_id: UUID, target_language: str
    ) -> DocumentTranslation | None:
        """The translation into *target_language*, or ``None``."""
        stmt = self._base_select().where(
            DocumentTranslation.document_version_id == version_id,
            DocumentTranslation.target_language == target_language,
        )
        return (await self._session.execute(stmt)).scalars().first()


__all__ = [
    "DocumentClassificationRepository",
    "DocumentEntityRepository",
    "DocumentFormRepository",
    "DocumentKeyValueRepository",
    "DocumentSummaryRepository",
    "DocumentTableRepository",
    "DocumentTranslationRepository",
]
