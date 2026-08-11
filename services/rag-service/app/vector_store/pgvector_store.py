"""The pgvector-backed store -- this service's real vector backend.

**Ordering and limiting happen in SQL, not in Python.** ``ORDER BY
embedding <=> :query LIMIT :k`` lets PostgreSQL stop as soon as it has
``k`` rows, and lets it use an ANN index if one exists. Loading every
vector into the process and sorting there works fine on a thousand
chunks and falls over on a million -- and the failure is a slow timeout
rather than an error, which makes it hard to attribute.

**Access filtering is in the same WHERE clause as the similarity
search.** Not applied afterwards: filtering post-hoc means asking for
ten results, getting ten, dropping six, and returning four -- while the
count of what was dropped leaks how much the caller cannot see.

ai-assistant-service's own ``search_similar`` is the precedent for the
distance operator and the model filter; the access scoping and the
metadata joins are new here.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from shared_core.logging.logger import get_logger
from sqlalchemy import cast, delete, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.models.embedding import EmbeddingVector
from app.models.enums import VectorStoreProvider, classification_rank
from app.vector_store.base import (
    StoreInfo,
    VectorMatch,
    VectorQuery,
    VectorRecord,
    VectorStoreError,
    similarity_from_distance,
)

logger = get_logger("app.vector_store.pgvector")

_CLASSIFICATIONS_BY_RANK = ("public", "internal", "confidential", "restricted", "secret")


class PgVectorStore:
    """Vectors in PostgreSQL, searched with pgvector's ``<=>`` operator."""

    provider = VectorStoreProvider.PGVECTOR

    def __init__(
        self,
        session: AsyncSession,
        *,
        model_name: str,
        dimensions: int,
        embedding_provider: str,
    ) -> None:
        self._session = session
        self._model = model_name
        self._dimensions = dimensions
        self._embedding_provider = embedding_provider

    async def upsert(self, records: Sequence[VectorRecord]) -> int:
        """Write vectors, replacing any this chunk already had for this model.

        Deleting-then-inserting rather than an ``ON CONFLICT`` update:
        the natural key is ``(chunk, provider, model)``, and a chunk
        re-embedded under a *different* model must keep both vectors,
        which an upsert keyed on the chunk alone would destroy.
        """
        if not records:
            return 0
        for record in records:
            if len(record.vector) != self._dimensions:
                raise VectorStoreError(
                    f"Chunk {record.chunk_id} has a {len(record.vector)}-dimension "
                    f"vector but this store holds {self._dimensions}."
                )

        chunk_ids = [record.chunk_id for record in records]
        try:
            await self._session.execute(
                delete(EmbeddingVector).where(
                    EmbeddingVector.document_chunk_id.in_(chunk_ids),
                    EmbeddingVector.model_name == self._model,
                )
            )
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise VectorStoreError(f"Could not replace existing vectors: {exc}") from exc
        return len(records)

    async def search(self, query: VectorQuery) -> list[VectorMatch]:
        """Nearest neighbours, access-filtered inside the query itself."""
        distance = EmbeddingVector.vector.cosine_distance(query.vector).label("distance")
        statement = (
            select(
                EmbeddingVector.document_chunk_id,
                EmbeddingVector.document_id,
                DocumentChunk.content,
                distance,
            )
            .join(DocumentChunk, DocumentChunk.id == EmbeddingVector.document_chunk_id)
            .join(Document, Document.id == EmbeddingVector.document_id)
            .where(
                EmbeddingVector.organization_id == query.organization_id,
                EmbeddingVector.model_name == self._model,
                Document.deleted_at.is_(None),
            )
        )
        statement = self._apply_scope(statement, query)
        statement = statement.order_by(distance).limit(query.top_k)

        try:
            result = await self._session.execute(statement)
            rows = result.all()
        except SQLAlchemyError as exc:
            raise VectorStoreError(f"Vector search failed: {exc}") from exc

        matches = [
            VectorMatch(
                chunk_id=row.document_chunk_id,
                document_id=row.document_id,
                score=similarity_from_distance(float(row.distance)),
                distance=float(row.distance),
                content=row.content or "",
            )
            for row in rows
        ]
        return [match for match in matches if match.score >= query.min_similarity]

    def _apply_scope(self, statement, query: VectorQuery):  # type: ignore[no-untyped-def]
        """Fold the caller's access scope into the WHERE clause.

        Every predicate here has to be part of the same query as the
        similarity ordering. See this module's docstring for why
        filtering afterwards is not equivalent.
        """
        if query.project_scope_id is not None:
            statement = statement.where(
                (Document.project_scope_id.is_(None))
                | (Document.project_scope_id == query.project_scope_id)
            )
        if query.document_ids:
            statement = statement.where(Document.id.in_(query.document_ids))

        ceiling = classification_rank(query.max_classification)
        permitted = [
            level for level in _CLASSIFICATIONS_BY_RANK if classification_rank(level) <= ceiling
        ]
        statement = statement.where(Document.classification.in_(permitted))

        # The role filter is applied ALWAYS, including when the caller
        # presents no roles at all. Skipping it in that case fails open:
        # a caller with no roles would see every role-restricted document
        # in the organization, which is the opposite of what a role
        # restriction means. With no roles, only documents that declare
        # none are visible.
        roles = cast(Document.allowed_roles, JSONB)
        unrestricted = func.jsonb_array_length(roles) == 0
        if query.caller_roles:
            statement = statement.where(
                unrestricted | roles.op("?|")(pg_array(list(query.caller_roles)))
            )
        else:
            statement = statement.where(unrestricted)
        return statement

    async def delete_document(self, organization_id: UUID, document_id: UUID) -> int:
        """Remove every vector belonging to one document."""
        try:
            result = await self._session.execute(
                delete(EmbeddingVector).where(
                    EmbeddingVector.organization_id == organization_id,
                    EmbeddingVector.document_id == document_id,
                )
            )
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise VectorStoreError(f"Could not delete vectors: {exc}") from exc
        return int(result.rowcount or 0)

    async def count(self, organization_id: UUID) -> int:
        """How many vectors this organization has under this model."""
        result = await self._session.execute(
            select(func.count())
            .select_from(EmbeddingVector)
            .where(
                EmbeddingVector.organization_id == organization_id,
                EmbeddingVector.model_name == self._model,
            )
        )
        return int(result.scalar_one())

    async def describe(self) -> StoreInfo:
        """Report the store's shape and whether an ANN index exists.

        The index method is read from PostgreSQL's own catalogue rather
        than from the ``vector_indexes`` table, because that table
        records what was *declared* and this answers what is actually
        built -- and those differing is exactly the condition index
        validation exists to catch.
        """
        total = int(
            (
                await self._session.execute(select(func.count()).select_from(EmbeddingVector))
            ).scalar_one()
        )
        method: str | None = None
        try:
            found = await self._session.execute(
                text(
                    "SELECT amname FROM pg_index i "
                    "JOIN pg_class c ON c.oid = i.indexrelid "
                    "JOIN pg_am am ON am.oid = c.relam "
                    "JOIN pg_class t ON t.oid = i.indrelid "
                    "WHERE t.relname = 'embedding_vectors' "
                    "AND am.amname IN ('hnsw', 'ivfflat') LIMIT 1"
                )
            )
            row = found.first()
            method = str(row[0]) if row else None
        except SQLAlchemyError as exc:  # pragma: no cover - catalogue is always readable
            logger.warning(
                "Could not read the index catalogue.",
                extra={"extra_fields": {"error": str(exc)}},
            )

        return StoreInfo(
            provider=self.provider,
            dimensions=self._dimensions,
            vector_count=total,
            index_method=method,
            is_ready=True,
            detail=(
                f"pgvector, model {self._model}, "
                f"{method or 'sequential scan (no ANN index built)'}"
            ),
        )


__all__ = ["PgVectorStore"]
