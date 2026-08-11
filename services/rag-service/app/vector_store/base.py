"""The vector store abstraction (docs/062 "VECTOR DATABASE").

**What "pluggable provider architecture" means here, and what it does
not.** The spec names eight backends. Two have implementations:
``pgvector``, which is real and is what the compose stack runs, and
``memory``, which exists so the abstraction itself is testable without a
database.

The other six are declared in
:class:`~app.models.enums.VectorStoreProvider` and are **not**
implemented, deliberately. No Qdrant, Milvus, Weaviate, Chroma,
Pinecone, or FAISS instance exists anywhere in this platform's
infrastructure, so a client for one would be code that has never once
executed against the thing it claims to talk to. Shipping six of those
would make this file look complete and make the service fail at the
first deployment that selected one. The deliverable is the *seam*: this
protocol, plus a registry, plus two implementations proving the seam
holds for both a networked store and an in-process one.

Adding a provider means implementing :class:`VectorStore` and calling
:func:`~app.vector_store.registry.register`. Nothing else in the service
changes -- which is the property a pluggable architecture is actually
supposed to give you.

**Filtering happens inside the store, never after it.** A store that
returned the top 10 and let the caller drop the ones it may not see
would return 3 results where 10 were asked for, and would leak the
existence of the other 7 through the count. Every query carries its
tenant, project, and permission scope into the backend.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.models.enums import VectorStoreProvider


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """One vector plus everything needed to filter and cite it."""

    chunk_id: UUID
    document_id: UUID
    organization_id: UUID
    vector: list[float]
    content: str = ""
    project_scope_id: UUID | None = None
    classification: str = "internal"
    allowed_roles: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VectorQuery:
    """One similarity search, with its access scope attached.

    The scope is part of the query rather than a separate argument
    because it must reach the backend's own WHERE clause. Carrying it
    separately invites exactly the mistake this design forbids --
    fetching first and filtering afterwards.
    """

    organization_id: UUID
    vector: list[float]
    top_k: int = 10
    project_scope_id: UUID | None = None
    caller_roles: tuple[str, ...] = ()
    max_classification: str = "secret"
    metadata_filters: dict[str, str] = field(default_factory=dict)
    document_ids: tuple[UUID, ...] = ()
    min_similarity: float = 0.0

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError(f"top_k must be at least 1, got {self.top_k!r}.")
        if not self.vector:
            raise ValueError("Cannot search with an empty query vector.")
        if not 0.0 <= self.min_similarity <= 1.0:
            raise ValueError(f"min_similarity must be within [0, 1], got {self.min_similarity!r}.")


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """One search hit."""

    chunk_id: UUID
    document_id: UUID
    score: float
    """Cosine **similarity** in ``[0, 1]``, not distance. Normalised at
    the store boundary so callers never have to know which convention a
    given backend used -- pgvector returns distance, an in-memory store
    naturally computes similarity, and a caller comparing the two
    directly would rank everything backwards."""
    distance: float
    content: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoreInfo:
    """What a store reports about itself."""

    provider: VectorStoreProvider
    dimensions: int
    vector_count: int
    index_method: str | None = None
    is_ready: bool = True
    detail: str = ""


class VectorStore(Protocol):
    """The contract every backend implements."""

    provider: VectorStoreProvider

    async def upsert(self, records: Sequence[VectorRecord]) -> int:
        """Insert or replace vectors, returning how many were written."""
        ...

    async def search(self, query: VectorQuery) -> list[VectorMatch]:
        """Nearest neighbours, best first, already access-filtered."""
        ...

    async def delete_document(self, organization_id: UUID, document_id: UUID) -> int:
        """Remove every vector for one document."""
        ...

    async def count(self, organization_id: UUID) -> int:
        """How many vectors one organization has stored."""
        ...

    async def describe(self) -> StoreInfo:
        """What this store is and whether it is ready."""
        ...


class VectorStoreError(RuntimeError):
    """A vector store operation failed."""


def similarity_from_distance(distance: float) -> float:
    """Convert a cosine distance to a similarity in ``[0, 1]``.

    pgvector's ``<=>`` returns ``1 - cosine_similarity``, so the range is
    ``[0, 2]`` -- 0 for identical, 1 for orthogonal, 2 for opposite.
    Clamped at zero because a negative similarity is not useful as a
    relevance score and would sort below "no match at all", which is not
    a distinction any caller acts on.
    """
    return max(0.0, 1.0 - distance)


__all__ = [
    "StoreInfo",
    "VectorMatch",
    "VectorQuery",
    "VectorRecord",
    "VectorStore",
    "VectorStoreError",
    "similarity_from_distance",
]
