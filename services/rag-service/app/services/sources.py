"""Knowledge sources (docs/062 "KNOWLEDGE SOURCE MANAGEMENT").

A knowledge source is a *configured* place documents come from -- a
Confluence space, an S3 prefix, a git repository -- with its own sync
schedule, default classification, and chunking settings. This module owns
the configuration and the sync bookkeeping.

**It does not fetch anything, and that is stated rather than implied.**
No Confluence, SharePoint, or S3 instance exists anywhere in this
platform's infrastructure, so a client for one would be code that has
never executed against the thing it claims to talk to. What is real here
is the registry, the schedule, the credential *reference*, and the
per-source ingestion defaults -- everything a connector would need, with
the connector itself left to whoever has an instance to test against.
:meth:`SourceService.record_sync` is the seam: a connector calls it with
what it fetched.

**A credential reference is stored, never a credential.** The column holds
a pointer into whatever secret store the deployment uses. A source row is
returned by an API, logged, and included in reports; a password in it
would be disclosed by all three.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.events.rag_events import KnowledgeSourceUpdatedEvent
from app.models.analytics import KnowledgeSource, RagAudit
from app.models.enums import (
    AuditAction,
    ChunkStrategy,
    ClassificationLevel,
    SourceKind,
    SyncStatus,
)
from app.repositories.analytics import KnowledgeSourceRepository, RagAuditRepository
from app.repositories.document import DocumentRepository
from app.types import EventPublisher

logger = get_logger("app.services.sources")

_SOURCE_SERVICE = "rag-service"

MIN_SYNC_INTERVAL_SECONDS = 60
"""One minute. Anything shorter means a sweep can still be running when
the next one is due, and two concurrent syncs of one source race to write
the same documents."""

_SLUG = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


@dataclass(slots=True)
class SyncOutcome:
    """What one connector reported after a sync attempt."""

    source: KnowledgeSource
    documents_seen: int = 0
    documents_ingested: int = 0
    documents_failed: int = 0
    cursor: str | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class SourceService:
    """Registers, configures, and schedules knowledge sources."""

    def __init__(
        self,
        sources: KnowledgeSourceRepository,
        documents: DocumentRepository,
        audit: RagAuditRepository,
        *,
        publish_event: EventPublisher,
    ) -> None:
        self._sources = sources
        self._documents = documents
        self._audit = audit
        self._publish_event = publish_event

    async def create_source(
        self,
        organization_id: UUID,
        *,
        slug: str,
        name: str,
        source_kind: SourceKind,
        description: str | None = None,
        uri: str | None = None,
        credential_reference: str | None = None,
        sync_enabled: bool = False,
        sync_interval_seconds: int = 3_600,
        default_classification: ClassificationLevel = ClassificationLevel.INTERNAL,
        default_tags: list[str] | None = None,
        allowed_roles: list[str] | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chunk_strategy: ChunkStrategy | None = None,
        configuration: dict[str, object] | None = None,
        created_by: str | None = None,
    ) -> KnowledgeSource:
        """Register a new knowledge source.

        Raises:
            ValidationError: If the slug is malformed or already taken, or
                the sync interval is below the floor.
        """
        self._validate_slug(slug)
        self._validate_interval(sync_interval_seconds)
        self._validate_chunking(chunk_size, chunk_overlap)
        if await self._sources.get_by_slug(organization_id, slug) is not None:
            raise ValidationError(
                f"A knowledge source with slug {slug!r} already exists in this "
                "organization. Slugs identify a source across syncs, so reusing one "
                "would silently redirect an existing schedule at a different system."
            )

        source = await self._sources.create(
            KnowledgeSource(
                organization_id=organization_id,
                slug=slug,
                name=name,
                description=description,
                source_kind=source_kind,
                uri=uri,
                credential_reference=credential_reference,
                sync_enabled=sync_enabled,
                sync_interval_seconds=sync_interval_seconds,
                sync_status=SyncStatus.NEVER_SYNCED,
                default_classification=default_classification,
                default_tags=list(default_tags or []),
                allowed_roles=list(allowed_roles or []),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                chunk_strategy=str(chunk_strategy) if chunk_strategy else None,
                configuration=dict(configuration or {}),
            )
        )
        await self._record(source, AuditAction.SOURCE_CREATED, f"Created {name!r}.", created_by)
        await self._announce(source, "created")
        return source

    async def update_source(
        self,
        organization_id: UUID,
        source_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        uri: str | None = None,
        credential_reference: str | None = None,
        is_enabled: bool | None = None,
        sync_enabled: bool | None = None,
        sync_interval_seconds: int | None = None,
        default_classification: ClassificationLevel | None = None,
        default_tags: list[str] | None = None,
        allowed_roles: list[str] | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chunk_strategy: ChunkStrategy | None = None,
        configuration: dict[str, object] | None = None,
        updated_by: str | None = None,
    ) -> KnowledgeSource:
        """Reconfigure a source.

        The slug and kind are not editable. Both are identity: changing
        the slug orphans the schedule that referenced it, and changing the
        kind would reinterpret every document already imported under it.

        Raises:
            NotFoundError: If the source is not in this organization.
            ValidationError: If the new sync interval is below the floor.
        """
        source = await self._sources.require_in_org(organization_id, source_id)
        if sync_interval_seconds is not None:
            self._validate_interval(sync_interval_seconds)
            source.sync_interval_seconds = sync_interval_seconds
        if chunk_size is not None or chunk_overlap is not None:
            self._validate_chunking(
                chunk_size if chunk_size is not None else source.chunk_size,
                chunk_overlap if chunk_overlap is not None else source.chunk_overlap,
            )
        for attribute, value in (
            ("name", name),
            ("description", description),
            ("uri", uri),
            ("credential_reference", credential_reference),
            ("is_enabled", is_enabled),
            ("sync_enabled", sync_enabled),
            ("default_classification", default_classification),
            ("chunk_size", chunk_size),
            ("chunk_overlap", chunk_overlap),
        ):
            if value is not None:
                setattr(source, attribute, value)
        if default_tags is not None:
            source.default_tags = list(default_tags)
        if allowed_roles is not None:
            source.allowed_roles = list(allowed_roles)
        if chunk_strategy is not None:
            source.chunk_strategy = str(chunk_strategy)
        if configuration is not None:
            source.configuration = dict(configuration)

        updated = await self._sources.update(source)
        await self._record(
            updated, AuditAction.SOURCE_UPDATED, f"Updated {updated.name!r}.", updated_by
        )
        await self._announce(updated, "updated")
        return updated

    async def list_sources(
        self, organization_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[KnowledgeSource]:
        """Every source in this organization, newest first."""
        return await self._sources.list_for_org(organization_id, limit=limit, offset=offset)

    async def get_source(self, organization_id: UUID, source_id: UUID) -> KnowledgeSource:
        """One source.

        Raises:
            NotFoundError: If it is not in this organization.
        """
        return await self._sources.require_in_org(organization_id, source_id)

    async def delete_source(
        self, organization_id: UUID, source_id: UUID, *, deleted_by: str | None = None
    ) -> KnowledgeSource:
        """Retire a source, leaving its documents in place.

        The documents keep their content and stay retrievable, with
        ``knowledge_source_id`` nulled by the foreign key's ``SET NULL``.
        Cascading the delete would remove a corpus because somebody
        removed a *schedule*, which is not what "delete this source"
        asks for.
        """
        source = await self._sources.require_in_org(organization_id, source_id)
        orphaned = await self._sources.count_documents(source.id)
        source.is_enabled = False
        source.sync_enabled = False
        await self._sources.update(source)
        await self._sources.delete(source.id)
        await self._record(
            source,
            AuditAction.SOURCE_UPDATED,
            f"Retired {source.name!r}; {orphaned} document(s) kept.",
            deleted_by,
        )
        await self._announce(source, "retired")
        return source

    # -- syncing --------------------------------------------------------------

    async def claim_for_sync(self, organization_id: UUID, source_id: UUID) -> KnowledgeSource:
        """Mark a source as syncing, so a second worker leaves it alone.

        Raises:
            NotFoundError: If the source is not in this organization.
            ValidationError: If it is already syncing. Two concurrent
                syncs of one source race to write the same documents, and
                whichever loses leaves a half-imported corpus behind.
        """
        source = await self._sources.require_in_org(organization_id, source_id)
        if source.sync_status == SyncStatus.SYNCING:
            raise ValidationError(
                f"Knowledge source {source.slug!r} is already syncing. Two syncs of "
                "one source write the same documents and the loser leaves a "
                "half-imported corpus behind."
            )
        source.sync_status = SyncStatus.SYNCING
        source.last_sync_error = None
        return await self._sources.update(source)

    async def record_sync(self, outcome: SyncOutcome) -> KnowledgeSource:
        """Record what a connector's sync attempt produced.

        The seam this module exposes to whatever actually fetches
        documents. The cursor is stored **only on success**: a cursor
        advanced past a failed page would make the next sync skip exactly
        the documents that did not import.
        """
        source = outcome.source
        source.last_synced_at = datetime.now(UTC)
        source.document_count = await self._sources.count_documents(source.id)

        if outcome.succeeded:
            source.sync_status = (
                SyncStatus.PARTIAL if outcome.documents_failed else SyncStatus.SUCCEEDED
            )
            source.last_sync_error = (
                f"{outcome.documents_failed} of {outcome.documents_seen} document(s) "
                "failed to import."
                if outcome.documents_failed
                else None
            )
            if outcome.cursor:
                source.last_sync_cursor = outcome.cursor
        else:
            source.sync_status = SyncStatus.FAILED
            source.last_sync_error = (outcome.error or "")[:2_000]

        updated = await self._sources.update(source)
        await self._record(
            updated,
            AuditAction.SOURCE_SYNCED,
            (
                f"Synced {updated.name!r}: {outcome.documents_ingested} ingested, "
                f"{outcome.documents_failed} failed of {outcome.documents_seen} seen."
            ),
            None,
            succeeded=outcome.succeeded,
        )
        await self._announce(updated, "synced")
        logger.info(
            "Recorded a knowledge source sync.",
            extra={
                "extra_fields": {
                    "source_id": str(updated.id),
                    "status": str(updated.sync_status),
                    "ingested": outcome.documents_ingested,
                    "failed": outcome.documents_failed,
                }
            },
        )
        return updated

    async def list_due_for_sync(
        self, moment: datetime | None = None, *, limit: int = 100
    ) -> list[KnowledgeSource]:
        """Sources whose sync interval has elapsed, across every tenant."""
        return await self._sources.list_due_for_sync(moment or datetime.now(UTC), limit=limit)

    async def refresh_document_counts(self, organization_id: UUID) -> dict[UUID, int]:
        """Recount documents per source.

        The stored count is denormalised and therefore drifts -- a
        document deleted directly does not decrement it. Recounting is
        cheap and keeps the number honest, which matters because it is
        what the sources report shows.
        """
        counts: dict[UUID, int] = {}
        for source in await self._sources.list_for_org(organization_id, limit=1_000):
            counts[source.id] = await self._sources.count_documents(source.id)
            if source.document_count != counts[source.id]:
                source.document_count = counts[source.id]
                await self._sources.update(source)
        return counts

    # -- validation ------------------------------------------------------------

    @staticmethod
    def _validate_slug(slug: str) -> None:
        """Refuse a slug that is not a bare kebab or snake identifier.

        Raises:
            ValidationError: If the slug does not match.
        """
        if not _SLUG.match(slug):
            raise ValidationError(
                f"Slug {slug!r} must be lowercase alphanumeric words separated by "
                "single hyphens or underscores. Slugs appear in URLs and in sync "
                "configuration, where anything else needs escaping that will "
                "eventually be forgotten."
            )

    @staticmethod
    def _validate_interval(seconds: int) -> None:
        """Refuse a sync interval below the floor.

        Raises:
            ValidationError: If below :data:`MIN_SYNC_INTERVAL_SECONDS`.
        """
        if seconds < MIN_SYNC_INTERVAL_SECONDS:
            raise ValidationError(
                f"sync_interval_seconds must be at least {MIN_SYNC_INTERVAL_SECONDS}, "
                f"got {seconds!r}. Below that a sweep can still be running when the "
                "next is due, and two concurrent syncs race to write the same "
                "documents."
            )

    @staticmethod
    def _validate_chunking(chunk_size: int | None, chunk_overlap: int | None) -> None:
        """Refuse a chunking override that cannot terminate.

        Raises:
            ValidationError: If the overlap is at least as wide as the
                window. Caught here rather than at ingestion time, when
                the source would fail on every document it fetched with
                an error that named the document rather than the setting.
        """
        if chunk_size is not None and chunk_size < 1:
            raise ValidationError(f"chunk_size must be at least 1, got {chunk_size!r}.")
        if chunk_overlap is not None and chunk_overlap < 0:
            raise ValidationError(f"chunk_overlap must not be negative, got {chunk_overlap!r}.")
        if chunk_size is not None and chunk_overlap is not None and chunk_overlap >= chunk_size:
            raise ValidationError(
                f"chunk_overlap ({chunk_overlap}) must be smaller than chunk_size "
                f"({chunk_size}); an overlap at least as wide as the window makes "
                "every window start at or before the previous one, so splitting "
                "would never terminate."
            )

    # -- recording --------------------------------------------------------------

    async def _record(
        self,
        source: KnowledgeSource,
        action: AuditAction,
        summary: str,
        actor_id: str | None,
        *,
        succeeded: bool = True,
    ) -> None:
        """Append one audit row."""
        await self._audit.create(
            RagAudit(
                organization_id=source.organization_id,
                action=action,
                entity_type="knowledge_source",
                entity_id=source.id,
                entity_reference=source.slug,
                actor_id=actor_id,
                occurred_at=datetime.now(UTC),
                summary=summary[:512],
                succeeded=succeeded,
            )
        )

    async def _announce(self, source: KnowledgeSource, change: str) -> None:
        """Publish that a source changed.

        Carries the change kind, so a consumer maintaining its own view
        can tell a reconfiguration from a sync without diffing state it
        does not have.
        """
        await self._publish_event(
            KnowledgeSourceUpdatedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=source.organization_id,
                payload={
                    "source_id": str(source.id),
                    "slug": source.slug,
                    "change": change,
                    "sync_status": str(source.sync_status),
                    "documents": source.document_count,
                },
            )
        )


__all__ = ["MIN_SYNC_INTERVAL_SECONDS", "SourceService", "SyncOutcome"]
