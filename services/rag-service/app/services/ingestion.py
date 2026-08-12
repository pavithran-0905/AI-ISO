"""Document ingestion (docs/062 "DOCUMENT LIFECYCLE").

The path from bytes to retrievable chunks: parse, scan, normalise,
chunk, store. Embedding and indexing happen separately -- see
:mod:`app.services.indexing` -- because they are the expensive,
retryable, rate-limited half and ingestion is the cheap deterministic
half. A parse failure should not consume an embedding quota, and an
embedding outage should not lose a parse.

**Content-addressed, so re-ingesting is free.** A document whose bytes
have not changed produces the same checksum, and this returns the
existing version rather than writing a duplicate. Without that, every
sync sweep re-parses and re-embeds an unchanged corpus, which is the
single largest avoidable cost in this service.

**A new version never destroys the old one.** Chunks hang off the
version, so the previous set stays retrievable until the new one is
indexed. Deleting first would open a window where the document is in the
corpus but returns nothing -- worse than briefly serving slightly stale
text.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID

from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.chunking.splitter import Chunk, ChunkingConfig, chunk_text
from app.chunking.tokens import estimate_tokens
from app.events.rag_events import DocumentImportedEvent
from app.models.analytics import RagAudit
from app.models.document import Document, DocumentChunk, DocumentVersion
from app.models.enums import (
    AuditAction,
    ChunkKind,
    ChunkStrategy,
    ClassificationLevel,
    DocumentStatus,
    SecurityFinding,
    SourceKind,
)
from app.parsers import ParsedBlock, ParseResult, blocks_to_text, detect_kind, get_parser
from app.repositories.analytics import RagAuditRepository
from app.repositories.document import (
    DocumentChunkRepository,
    DocumentMetadataRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.security import scanner
from app.types import EventPublisher

logger = get_logger("app.services.ingestion")

_SOURCE_SERVICE = "rag-service"


_BLOCK_SEPARATOR = "\n\n"
"""What :func:`~app.parsers.base.blocks_to_text` joins blocks with. The
chunk offsets computed here have to advance by exactly this much between
blocks or every stored offset drifts from the text it indexes into."""


def _redact_block(block: ParsedBlock) -> ParsedBlock:
    """A copy of *block* with invisible characters and PII removed."""
    cleaned, _hit = scanner.redact(scanner.strip_invisible(block.text))
    return replace(block, text=cleaned)


def _resolve_kind(chunk: Chunk, block: ParsedBlock | None) -> ChunkKind:
    """The chunk kind, preferring what the parser knew over what the
    splitter inferred.

    The parser saw the markup; the splitter sees only text. A ``<table>``
    the HTML parser rendered as aligned rows is a table whatever the
    splitter makes of the result.
    """
    if block is not None and block.is_table:
        return ChunkKind.TABLE
    if block is not None and block.is_code:
        return ChunkKind.CODE
    return chunk.kind


def _plan_chunks(
    text: str, blocks: Sequence[ParsedBlock], config: ChunkingConfig
) -> list[tuple[Chunk, ParsedBlock | None]]:
    """Pair every chunk with the parsed block it came from.

    With no blocks -- a parser that only produced flat text -- the whole
    document is chunked at once and every chunk is unattributed. That is
    the honest outcome: inventing a page number for text whose page
    nobody recorded would make a citation that points somewhere wrong,
    which is worse than one that points only at the document.
    """
    if not blocks:
        return [(chunk, None) for chunk in chunk_text(text, config)]

    planned: list[tuple[Chunk, ParsedBlock | None]] = []
    offset = 0
    for index, block in enumerate(blocks):
        if index:
            offset += len(_BLOCK_SEPARATOR)
        for chunk in chunk_text(block.text, config):
            planned.append(
                (replace(chunk, start=chunk.start + offset, end=chunk.end + offset), block)
            )
        offset += len(block.text)
    return planned


@dataclass(slots=True)
class IngestionResult:
    """What one ingestion produced."""

    document: Document
    version: DocumentVersion | None = None
    chunks: list[DocumentChunk] = field(default_factory=list)
    unchanged: bool = False
    """``True`` when the content matched what was already stored, so
    nothing was rewritten. The caller uses this to skip re-indexing."""
    blocked: bool = False
    findings: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


class IngestionService:
    """Turns uploaded or fetched bytes into stored, chunked text."""

    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        chunks: DocumentChunkRepository,
        metadata: DocumentMetadataRepository,
        audit: RagAuditRepository,
        *,
        publish_event: EventPublisher,
        chunk_size: int = 1_000,
        chunk_overlap: int = 150,
        max_chunks: int = 10_000,
        max_bytes: int = 52_428_800,
        scan_enabled: bool = True,
        block_on_injection: bool = False,
        redact_pii: bool = True,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._chunks = chunks
        self._metadata = metadata
        self._audit = audit
        self._publish_event = publish_event
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._max_chunks = max_chunks
        self._max_bytes = max_bytes
        self._scan_enabled = scan_enabled
        self._block_on_injection = block_on_injection
        self._redact_pii = redact_pii

    async def ingest(
        self,
        *,
        organization_id: UUID,
        data: bytes,
        title: str,
        filename: str | None = None,
        content_type: str | None = None,
        source_kind: SourceKind | None = None,
        external_id: str | None = None,
        knowledge_source_id: UUID | None = None,
        classification: ClassificationLevel = ClassificationLevel.INTERNAL,
        allowed_roles: list[str] | None = None,
        tags: list[str] | None = None,
        project_scope_id: UUID | None = None,
        source_uri: str | None = None,
        chunk_strategy: ChunkStrategy = ChunkStrategy.HYBRID,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        ingested_by: str | None = None,
    ) -> IngestionResult:
        """Ingest one document end to end.

        Raises:
            ValidationError: If the format cannot be determined, has no
                parser, or the document exceeds the size limit.
        """
        checksum = hashlib.sha256(data).hexdigest()
        kind = source_kind or detect_kind(filename, content_type=content_type)
        if kind is None:
            raise ValidationError(
                f"Could not determine the format of {filename or title!r}. Supply a "
                "filename with a known extension, a content type, or an explicit "
                "source kind."
            )

        document = await self._resolve_document(
            organization_id=organization_id,
            external_id=external_id,
            checksum=checksum,
            title=title,
            kind=kind,
            knowledge_source_id=knowledge_source_id,
            classification=classification,
            allowed_roles=allowed_roles or [],
            tags=tags or [],
            project_scope_id=project_scope_id,
            source_uri=source_uri,
            byte_size=len(data),
            content_type=content_type,
            ingested_by=ingested_by,
        )

        # Content-addressed short circuit. Checked after the document row
        # exists so a re-import still refreshes its metadata, but before
        # any parsing -- re-parsing unchanged bytes is pure waste.
        current = await self._versions.get_current(document.id)
        if current is not None and current.checksum == checksum:
            logger.info(
                "Document content is unchanged; nothing was re-parsed.",
                extra={"extra_fields": {"document_id": str(document.id)}},
            )
            return IngestionResult(document=document, version=current, unchanged=True)

        parsed = self._parse(data, kind=kind, filename=filename)
        if parsed.error is not None:
            await self._fail(document, parsed.error, ingested_by=ingested_by)
            raise ValidationError(f"Could not parse {title!r}: {parsed.error}")
        if parsed.is_empty:
            # Parsed cleanly and found nothing -- a scanned PDF with no
            # text layer, most often. Storing it would leave a document in
            # the corpus with zero chunks that can never be retrieved and
            # never reports why. The distinction is actionable, so it is
            # stated: this one needs OCR, not a different parser.
            reason = (
                "The document parsed successfully but contained no extractable text. "
                "A scanned PDF or an image-only file needs OCR before it can be indexed."
            )
            await self._fail(document, reason, ingested_by=ingested_by)
            raise ValidationError(f"Nothing to index in {title!r}: {reason}")

        text = parsed.text
        findings: list[dict[str, object]] = []
        if self._scan_enabled:
            report = scanner.scan(text, byte_size=len(data), max_bytes=self._max_bytes)
            findings = report.to_dicts()
            if report.should_block or (
                self._block_on_injection
                and any(f.finding == SecurityFinding.PROMPT_INJECTION for f in report.findings)
            ):
                await self._fail(
                    document,
                    f"Blocked by ingestion scanning: {report.highest_severity!s}.",
                    ingested_by=ingested_by,
                )
                await self._record(
                    document,
                    action=AuditAction.SECURITY_SCANNED,
                    summary=f"Ingestion blocked for {title!r}.",
                    actor_id=ingested_by,
                    succeeded=False,
                )
                return IngestionResult(
                    document=document, blocked=True, findings=findings, warnings=parsed.warnings
                )

        # Blank blocks are dropped here and nowhere else, because
        # ``blocks_to_text`` drops them too: keeping one in this list
        # while the joined text omits it would shift every subsequent
        # chunk offset by the length of a separator that was never
        # written.
        blocks = [block for block in parsed.blocks if block.text.strip()]
        if self._redact_pii:
            # Redaction is applied per block and the document text is
            # rebuilt from the result, rather than applied to the joined
            # text. Redacting the join would leave the blocks holding the
            # unredacted originals, and the blocks are what gets chunked
            # and embedded -- so the secret would be removed from the
            # copy nobody queries and left in the copy everybody does.
            blocks = [
                cleaned
                for cleaned in (_redact_block(block) for block in blocks)
                if cleaned.text.strip()
            ]
            text = (
                blocks_to_text(blocks)
                if blocks
                else scanner.redact(scanner.strip_invisible(text))[0]
            )

        version = await self._store_version(
            document, text=text, checksum=checksum, parsed=parsed, created_by=ingested_by
        )
        stored = await self._store_chunks(
            document,
            version,
            text=text,
            blocks=blocks,
            strategy=chunk_strategy,
            size=chunk_size or self._chunk_size,
            overlap=chunk_overlap or self._chunk_overlap,
        )
        await self._store_metadata(document, parsed)

        document.status = DocumentStatus.CHUNKED
        document.chunk_count = len(stored)
        document.token_count = sum(chunk.token_count for chunk in stored)
        document.checksum = checksum
        document.byte_size = len(data)
        document.current_version_number = version.version_number
        document.error = None
        await self._documents.update(document)

        await self._record(
            document,
            action=AuditAction.DOCUMENT_IMPORTED,
            summary=f"Ingested {title!r} as version {version.version_number}.",
            actor_id=ingested_by,
        )
        await self._publish_event(
            DocumentImportedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "document_id": str(document.id),
                    "version": version.version_number,
                    "chunks": len(stored),
                    "source_kind": str(kind),
                },
            )
        )
        return IngestionResult(
            document=document,
            version=version,
            chunks=stored,
            findings=findings,
            warnings=parsed.warnings,
        )

    def _parse(self, data: bytes, *, kind: SourceKind, filename: str | None) -> ParseResult:
        """Run the parser for *kind*.

        Raises:
            ValidationError: If that kind has no parser. The connector
                kinds -- Confluence, S3, a git repository -- fetch bytes
                that are then parsed by whichever *format* parser
                matches, so reaching here with one means a caller passed
                a system where a format belongs.
        """
        parser = get_parser(kind)
        if parser is None:
            raise ValidationError(
                f"No parser exists for {kind!s}. Connector kinds fetch bytes that are "
                "then parsed as whichever file format they turn out to be; pass that "
                "format instead."
            )
        return parser.parse(data, filename=filename)

    async def _resolve_document(
        self,
        *,
        organization_id: UUID,
        external_id: str | None,
        checksum: str,
        title: str,
        kind: SourceKind,
        knowledge_source_id: UUID | None,
        classification: ClassificationLevel,
        allowed_roles: list[str],
        tags: list[str],
        project_scope_id: UUID | None,
        source_uri: str | None,
        byte_size: int,
        content_type: str | None,
        ingested_by: str | None,
    ) -> Document:
        """Find the document this ingestion updates, or create it.

        Matched on ``external_id`` first -- that is what makes a source
        sync idempotent. Falling back to the checksum catches the same
        file uploaded twice under different names, which would otherwise
        be embedded twice and returned twice by every query matching it.
        """
        existing: Document | None = None
        if external_id:
            existing = await self._documents.get_by_external_id(organization_id, external_id)
        if existing is None:
            existing = await self._documents.get_by_checksum(organization_id, checksum)

        if existing is not None:
            existing.title = title
            existing.classification = classification
            existing.allowed_roles = list(allowed_roles)
            existing.tags = list(tags)
            if source_uri:
                existing.source_uri = source_uri
            return await self._documents.update(existing)

        return await self._documents.create(
            Document(
                organization_id=organization_id,
                knowledge_source_id=knowledge_source_id,
                external_id=external_id,
                title=title,
                source_kind=kind,
                status=DocumentStatus.PENDING,
                classification=classification,
                project_scope_id=project_scope_id,
                allowed_roles=list(allowed_roles),
                tags=list(tags),
                content_type=content_type,
                byte_size=byte_size,
                checksum=checksum,
                source_uri=source_uri,
                ingested_by=ingested_by,
            )
        )

    async def _store_version(
        self,
        document: Document,
        *,
        text: str,
        checksum: str,
        parsed: ParseResult,
        created_by: str | None,
    ) -> DocumentVersion:
        """Write a new version and make it live.

        The previous version is demoted, not deleted: its chunks stay
        retrievable until the new ones are indexed, so there is never a
        moment when the document is in the corpus and returns nothing.
        """
        await self._versions.clear_current(document.id)
        extracted: dict[str, object] = dict(parsed.metadata)
        return await self._versions.create(
            DocumentVersion(
                organization_id=document.organization_id,
                document_id=document.id,
                version_number=await self._versions.next_version_number(document.id),
                content=text,
                checksum=checksum,
                byte_size=len(text.encode("utf-8")),
                token_count=estimate_tokens(text),
                page_count=parsed.page_count,
                parser=parsed.parser,
                is_current=True,
                extracted_metadata=extracted,
                warnings=list(parsed.warnings),
                authored_by=created_by,
            )
        )

    async def _store_chunks(
        self,
        document: Document,
        version: DocumentVersion,
        *,
        text: str,
        blocks: Sequence[ParsedBlock],
        strategy: ChunkStrategy,
        size: int,
        overlap: int,
    ) -> list[DocumentChunk]:
        """Split the text and persist the chunks.

        **Chunked block by block, not over the flattened text.** Every
        parser emits blocks carrying where their text came from -- page
        number, heading trail, whether it was a table. Chunking the joined
        string throws all of that away, and it cannot be recovered
        afterwards: the parser stripped the ``##`` markers, so a heading
        strategy run over the flattened text finds no headings at all and
        silently degrades to fixed-size windows, and a PDF chunk's page
        number becomes permanently unknowable. Every citation this service
        produces would then point at a document rather than into it.

        Raises:
            ValidationError: If the chunking configuration is impossible
                -- an overlap at least as wide as the window would never
                terminate.
        """
        try:
            config = ChunkingConfig(
                strategy=strategy,
                chunk_size=size,
                overlap=overlap,
                max_chunks=self._max_chunks,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        stored: list[DocumentChunk] = []
        for chunk, block in _plan_chunks(text, blocks, config):
            if len(stored) >= self._max_chunks:
                logger.warning(
                    "Stopped chunking at the configured ceiling.",
                    extra={
                        "extra_fields": {
                            "document_id": str(document.id),
                            "max_chunks": self._max_chunks,
                        }
                    },
                )
                break
            row = self._to_row(document, version, chunk, strategy, block, len(stored))
            stored.append(await self._chunks.create(row))
        version.chunk_count = len(stored)
        await self._versions.update(version)
        return stored

    @staticmethod
    def _to_row(
        document: Document,
        version: DocumentVersion,
        chunk: Chunk,
        strategy: ChunkStrategy,
        block: ParsedBlock | None,
        sequence: int,
    ) -> DocumentChunk:
        """Turn a pure :class:`Chunk` into a persistable row.

        The *requested* strategy is stored, not the per-chunk kind: the
        hybrid splitter emits headings, tables, and code from one run, and
        recording the kind as the strategy would make it impossible to
        answer "which strategy produced this index?" -- the question a
        re-chunking decision turns on.

        Where the splitter found structure of its own it wins over the
        block's, since it is the more specific of the two: a heading found
        *inside* a block describes that chunk better than the trail the
        whole block sat under.
        """
        block_path = " > ".join(block.section_path) if block and block.section_path else None
        return DocumentChunk(
            organization_id=document.organization_id,
            document_id=document.id,
            document_version_id=version.id,
            sequence=sequence,
            content=chunk.content,
            chunk_kind=_resolve_kind(chunk, block),
            strategy=strategy,
            token_count=chunk.token_estimate,
            character_count=chunk.character_count,
            start_offset=chunk.start,
            end_offset=chunk.end,
            page_number=block.page_number if block else None,
            section_path=chunk.section_label or block_path,
            heading=chunk.heading or (block.heading if block else None),
            overlap_tokens=chunk.overlap_tokens,
        )

    async def _store_metadata(self, document: Document, parsed: ParseResult) -> None:
        """Persist whatever the format itself declared.

        Written as *extracted*, so a human who later corrects one of
        these values is not overruled by the next re-parse.
        """
        for key, value in parsed.metadata.items():
            if value and value.strip():
                await self._metadata.upsert(
                    document.id,
                    document.organization_id,
                    key,
                    value.strip()[:1_024],
                    extracted=True,
                )

    async def _fail(self, document: Document, reason: str, *, ingested_by: str | None) -> None:
        """Mark a document failed, with the reason attached to the row."""
        document.status = DocumentStatus.FAILED
        document.error = reason
        await self._documents.update(document)
        logger.warning(
            "Ingestion failed.",
            extra={"extra_fields": {"document_id": str(document.id), "reason": reason}},
        )

    async def _record(
        self,
        document: Document,
        *,
        action: AuditAction,
        summary: str,
        actor_id: str | None,
        succeeded: bool = True,
    ) -> None:
        """Append one audit row."""
        await self._audit.create(
            RagAudit(
                organization_id=document.organization_id,
                action=action,
                entity_type="document",
                entity_id=document.id,
                entity_reference=document.title,
                actor_id=actor_id,
                occurred_at=datetime.now(UTC),
                summary=summary[:512],
                succeeded=succeeded,
            )
        )


__all__ = ["IngestionResult", "IngestionService"]
