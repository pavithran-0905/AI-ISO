"""An in-process vector store.

Not in docs/062's list of backends, and added deliberately. It exists to
prove the :class:`~app.vector_store.base.VectorStore` seam holds for
something structurally unlike PostgreSQL: no SQL, no session, no
transaction, similarity computed rather than delegated. A protocol only
one implementation satisfies is not an abstraction, it is an indirection.

It is also what makes the retrieval pipeline exercisable with no
database at all, which matters for the same reason the builtin encoder
does.

**Not suitable for production**, and the reason is structural rather
than a matter of tuning: it scans every stored vector on every query, so
cost grows linearly with corpus size, and it holds everything in one
process's heap so nothing survives a restart. Both are stated here so
nobody has to discover them.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.embeddings.encoder import cosine_similarity
from app.models.enums import VectorStoreProvider, classification_rank
from app.vector_store.base import (
    StoreInfo,
    VectorMatch,
    VectorQuery,
    VectorRecord,
    VectorStoreError,
)


class MemoryVectorStore:
    """Vectors in a dictionary, searched by brute force."""

    provider = VectorStoreProvider.MEMORY

    def __init__(self, *, dimensions: int) -> None:
        self._dimensions = dimensions
        self._records: dict[UUID, VectorRecord] = {}

    async def upsert(self, records: Sequence[VectorRecord]) -> int:
        """Store vectors, replacing any with the same chunk id."""
        for record in records:
            if len(record.vector) != self._dimensions:
                raise VectorStoreError(
                    f"Chunk {record.chunk_id} has a {len(record.vector)}-dimension "
                    f"vector but this store holds {self._dimensions}."
                )
        for record in records:
            self._records[record.chunk_id] = record
        return len(records)

    async def search(self, query: VectorQuery) -> list[VectorMatch]:
        """Brute-force nearest neighbours, access-filtered.

        The filtering runs *before* scoring, mirroring what the SQL store
        does in its WHERE clause -- so both implementations answer the
        same question and a test against this one means something about
        the other.
        """
        if len(query.vector) != self._dimensions:
            raise VectorStoreError(
                f"Query vector has {len(query.vector)} dimensions but this store "
                f"holds {self._dimensions}."
            )

        ceiling = classification_rank(query.max_classification)
        ranked: list[tuple[float, VectorMatch]] = []
        for record in self._records.values():
            if record.organization_id != query.organization_id:
                continue
            if not self._in_scope(record, query, ceiling=ceiling):
                continue
            # Ranking uses the TRUE similarity; only the reported score
            # is clamped. pgvector orders by raw ``<=>`` distance and
            # clamps afterwards, so clamping before sorting here would
            # collapse every opposed vector to one score and lose the
            # ordering between them -- making the two stores disagree on
            # exactly the results neither considers relevant, which is
            # still a disagreement the abstraction cannot have.
            true_similarity = cosine_similarity(query.vector, record.vector)
            score = max(0.0, true_similarity)
            if score < query.min_similarity:
                continue
            ranked.append(
                (
                    true_similarity,
                    VectorMatch(
                        chunk_id=record.chunk_id,
                        document_id=record.document_id,
                        score=score,
                        distance=1.0 - true_similarity,
                        content=record.content,
                        metadata=dict(record.metadata),
                    ),
                )
            )
        # Ties break on chunk id so the order never depends on insertion
        # sequence, which would make a test flaky for no reason.
        ranked.sort(key=lambda pair: (-pair[0], str(pair[1].chunk_id)))
        return [match for _similarity, match in ranked[: query.top_k]]

    @staticmethod
    def _in_scope(record: VectorRecord, query: VectorQuery, *, ceiling: int) -> bool:
        """Whether the caller may see this record."""
        if (
            query.project_scope_id is not None
            and record.project_scope_id is not None
            and record.project_scope_id != query.project_scope_id
        ):
            return False
        if query.document_ids and record.document_id not in query.document_ids:
            return False
        if classification_rank(record.classification) > ceiling:
            return False
        if record.allowed_roles and not set(record.allowed_roles) & set(query.caller_roles):
            return False
        return all(
            record.metadata.get(key) == value for key, value in query.metadata_filters.items()
        )

    async def delete_document(self, organization_id: UUID, document_id: UUID) -> int:
        """Remove every vector for one document."""
        doomed = [
            chunk_id
            for chunk_id, record in self._records.items()
            if record.organization_id == organization_id and record.document_id == document_id
        ]
        for chunk_id in doomed:
            del self._records[chunk_id]
        return len(doomed)

    async def count(self, organization_id: UUID) -> int:
        """How many vectors one organization has stored."""
        return sum(
            1 for record in self._records.values() if record.organization_id == organization_id
        )

    async def describe(self) -> StoreInfo:
        return StoreInfo(
            provider=self.provider,
            dimensions=self._dimensions,
            vector_count=len(self._records),
            index_method=None,
            is_ready=True,
            detail=(
                "in-process brute-force store; scans every vector per query and "
                "does not survive a restart"
            ),
        )

    def clear(self) -> None:
        """Drop everything. Test convenience, not part of the protocol."""
        self._records.clear()


__all__ = ["MemoryVectorStore"]
