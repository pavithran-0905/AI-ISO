"""The embedding service: batching, caching, and cost accounting.

Sits between ingestion and whichever provider is configured, and owns
three concerns none of the callers should have to:

**Batching.** Providers charge per request as well as per token, and
round-trip latency dominates for small chunks. Texts are grouped into
batches, and a failed batch loses only that batch.

**Caching.** An embedding is a pure function of ``(text, model)``, so it
never goes stale. Re-embedding text already embedded is the single
largest avoidable cost in this service -- a reindex that changes one
paragraph should not pay to re-embed the other nine hundred.

**Cost accounting.** Tokens and dollars are attributed per batch, because
"why did embedding cost that much?" is otherwise unanswerable after the
fact.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from shared_core.logging.logger import get_logger

from app.chunking.tokens import estimate_cost_usd, estimate_tokens
from app.embeddings.client import EmbeddingClient
from app.embeddings.encoder import HashingEncoder, content_hash
from app.models.enums import EmbeddingProvider

logger = get_logger("app.embeddings.service")


class VectorCache(Protocol):
    """The subset of a cache this service needs.

    A protocol rather than a concrete Redis dependency, so the service is
    usable -- and testable -- with no cache at all.
    """

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None: ...


@dataclass(slots=True)
class EmbeddingBatch:
    """What one embedding run produced and cost."""

    vectors: list[list[float]] = field(default_factory=list)
    tokens: int = 0
    cost_usd: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    provider: str = ""
    model: str = ""

    @property
    def hit_rate(self) -> float:
        """Fraction served from cache. ``0.0`` when nothing was asked
        for, rather than a division error."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total else 0.0


class EmbeddingService:
    """Generates embeddings, caching and costing them.

    Exactly one of *client* and the builtin encoder is in play: a
    ``None`` client means the builtin encoder, which is how
    :func:`~app.embeddings.client.build_client` signals ``BUILTIN``.
    """

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        model: str,
        dimensions: int,
        client: EmbeddingClient | None = None,
        encoder: HashingEncoder | None = None,
        cache: VectorCache | None = None,
        batch_size: int = 64,
        cache_ttl_seconds: int = 604_800,
        usd_per_1k_tokens: float = 0.0,
    ) -> None:
        if client is None and encoder is None:
            raise ValueError(
                "An EmbeddingService needs either an HTTP client or the builtin "
                "encoder; with neither there is nothing to embed with."
            )
        if batch_size < 1:
            raise ValueError(f"batch_size must be at least 1, got {batch_size!r}.")
        self._provider = provider
        self._model = model
        self._dimensions = dimensions
        self._client = client
        self._encoder = encoder
        self._cache = cache
        self._batch_size = batch_size
        self._ttl = cache_ttl_seconds
        self._usd_per_1k = usd_per_1k_tokens

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
        """Embed *texts*, in order, using the cache where possible.

        The returned vectors line up positionally with *texts*. That is
        load-bearing: the caller pairs them with chunks by position, and
        a reordering here would attach every vector to the wrong chunk.
        """
        batch = EmbeddingBatch(provider=str(self._provider), model=self._model)
        if not texts:
            return batch

        resolved: list[list[float] | None] = [None] * len(texts)
        pending: list[tuple[int, str]] = []

        for position, text in enumerate(texts):
            cached = await self._from_cache(text)
            if cached is not None:
                resolved[position] = cached
                batch.cache_hits += 1
            else:
                pending.append((position, text))
                batch.cache_misses += 1

        for start in range(0, len(pending), self._batch_size):
            window = pending[start : start + self._batch_size]
            vectors = await self._generate([text for _position, text in window])
            for (position, text), vector in zip(window, vectors, strict=True):
                resolved[position] = vector
                await self._to_cache(text, vector)
            batch.tokens += sum(estimate_tokens(text) for _position, text in window)

        batch.vectors = [vector for vector in resolved if vector is not None]
        if len(batch.vectors) != len(texts):  # pragma: no cover - defensive
            raise RuntimeError(
                f"Embedded {len(batch.vectors)} of {len(texts)} texts; refusing to "
                "return a list that no longer lines up with its input."
            )
        batch.cost_usd = estimate_cost_usd(batch.tokens, usd_per_1k_tokens=self._usd_per_1k)
        return batch

    async def embed_one(self, text: str) -> list[float]:
        """Embed a single string -- the query path."""
        batch = await self.embed([text])
        return batch.vectors[0]

    async def _generate(self, texts: list[str]) -> list[list[float]]:
        """Produce vectors for a cache-missed batch."""
        if self._client is not None:
            vectors = await self._client.embed(texts, model=self._model)
        else:
            assert self._encoder is not None
            vectors = self._encoder.encode_many(texts)
        self._check_dimensions(vectors)
        return vectors

    def _check_dimensions(self, vectors: list[list[float]]) -> None:
        """Refuse vectors that do not fit the configured column.

        Caught here rather than at the database, because pgvector's error
        for a width mismatch names neither the model nor the chunk, and
        by then the batch's other vectors have already been written.
        """
        for vector in vectors:
            if len(vector) != self._dimensions:
                raise ValueError(
                    f"Model {self._model!r} returned a {len(vector)}-dimension vector "
                    f"but this index stores {self._dimensions}. Vectors of different "
                    "width cannot share an index, and their distances would not be "
                    "comparable even if they could."
                )

    async def _from_cache(self, text: str) -> list[float] | None:
        if self._cache is None:
            return None
        try:
            raw = await self._cache.get(self._key(text))
        except Exception as exc:
            # A cache failure must never fail an ingestion. The worst
            # case is paying to embed something already embedded.
            logger.warning(
                "Embedding cache read failed; falling through to the provider.",
                extra={"extra_fields": {"error": str(exc)}},
            )
            return None
        if not raw:
            return None
        try:
            vector = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(vector, list) or len(vector) != self._dimensions:
            # A cached vector of the wrong width is a leftover from a
            # different model; ignore it rather than poison the index.
            return None
        return [float(value) for value in vector]

    async def _to_cache(self, text: str, vector: list[float]) -> None:
        if self._cache is None:
            return
        try:
            await self._cache.set(self._key(text), json.dumps(vector), ttl_seconds=self._ttl)
        except Exception as exc:
            logger.warning(
                "Embedding cache write failed; the vector is still returned.",
                extra={"extra_fields": {"error": str(exc)}},
            )

    def _key(self, text: str) -> str:
        """Cache key, namespaced by model.

        The model is in the key, so switching models cannot serve one
        model's vectors to another -- which would produce a corpus whose
        distances are meaningless in a way nothing downstream could
        detect.
        """
        return f"rag:embedding:{content_hash(text, model=self._model)}"


__all__ = ["EmbeddingBatch", "EmbeddingService", "VectorCache"]
