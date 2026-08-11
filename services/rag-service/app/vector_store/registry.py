"""Selecting a vector store by configuration.

The seam a "pluggable provider architecture" actually consists of: one
place that maps a configured provider name onto an implementation, so
adding a backend touches this file and nothing else.

**Unimplemented providers fail here, at startup, with an explanation** --
not at the first query, and not by silently falling back to pgvector. A
deployment that configured Qdrant and got PostgreSQL would be storing
vectors somewhere its operators did not intend, which is worse than
refusing to start.
"""

from __future__ import annotations

from shared_core.exceptions.dependency import DependencyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VectorStoreProvider
from app.vector_store.base import VectorStore
from app.vector_store.memory_store import MemoryVectorStore
from app.vector_store.pgvector_store import PgVectorStore

IMPLEMENTED: frozenset[VectorStoreProvider] = frozenset(
    {VectorStoreProvider.PGVECTOR, VectorStoreProvider.MEMORY}
)
"""The providers with real implementations. Everything else in
:class:`~app.models.enums.VectorStoreProvider` is declared by the spec
and refused by :func:`build_store`."""

_WHY_UNIMPLEMENTED = (
    "No {provider} instance exists in this platform's infrastructure, so a client "
    "for it would be code that has never executed against the thing it claims to "
    "talk to. Implement the VectorStore protocol in app/vector_store/ and register "
    "it here; nothing else in the service needs to change. Configured providers "
    "with implementations: {available}."
)


def build_store(
    provider: VectorStoreProvider | str,
    *,
    dimensions: int,
    session: AsyncSession | None = None,
    model_name: str = "",
    embedding_provider: str = "",
) -> VectorStore:
    """Build the configured store.

    Raises:
        DependencyError: If *provider* has no implementation, or if
            pgvector was selected without a database session.
    """
    chosen = VectorStoreProvider(str(provider))

    if chosen is VectorStoreProvider.MEMORY:
        return MemoryVectorStore(dimensions=dimensions)

    if chosen is VectorStoreProvider.PGVECTOR:
        if session is None:
            raise DependencyError("The pgvector store needs a database session; none was supplied.")
        return PgVectorStore(
            session,
            model_name=model_name,
            dimensions=dimensions,
            embedding_provider=embedding_provider,
        )

    raise DependencyError(
        _WHY_UNIMPLEMENTED.format(
            provider=str(chosen),
            available=", ".join(sorted(str(name) for name in IMPLEMENTED)),
        )
    )


def is_implemented(provider: VectorStoreProvider | str) -> bool:
    """Whether *provider* has a real implementation here."""
    try:
        return VectorStoreProvider(str(provider)) in IMPLEMENTED
    except ValueError:
        return False


__all__ = ["IMPLEMENTED", "build_store", "is_implemented"]
