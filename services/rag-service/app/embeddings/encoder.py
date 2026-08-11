"""The builtin offline encoder.

Ported from ``ai-assistant-service/app/embeddings/encoder.py`` -- services
in this monorepo cannot import each other, and this is not in
``shared_core``.

**Why a service whose job is embedding ships an encoder that is not a
real embedding model.** Without one, nothing in this service could be
exercised without an API credential: not ingestion, not indexing, not
retrieval, not the vector store, not a single end-to-end test. A RAG
service whose tests only run when somebody has an OpenAI key is a RAG
service whose tests do not run. This makes the entire pipeline
executable, deterministic, and verifiable offline.

**What it actually is.** Signed feature hashing over character n-grams
and word unigrams, L2-normalised. That gives a vector with real
properties -- identical text always produces the identical vector,
similar text produces nearer vectors, and cosine similarity behaves the
way the rest of the pipeline expects -- without any learned semantics.
It will match "backup" to "backups" through shared character n-grams; it
will not match "car" to "automobile". Every downstream component treats
it exactly as it treats a real provider's vectors, which is the point:
the plumbing is proven, and swapping in a real model changes only the
quality of the matches, not whether the machinery works.

Named ``builtin`` rather than ``local``: ``LOCAL`` already means "a
self-hosted OpenAI-compatible endpoint" elsewhere in this platform, which
is a network call with a credential.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

BUILTIN_PROVIDER = "builtin"
BUILTIN_MODEL = "builtin-hashing"

DEFAULT_DIMENSIONS = 1536
"""Matches ``AIConstants.EMBEDDING_DIMENSIONS`` and the ``vector(1536)``
column, so a builtin-encoded corpus occupies the same storage a real
provider's would. Switching providers is then a re-embed, not a
migration."""

_NGRAM_SIZE = 4
"""Character n-gram width. Four is short enough that ``backup`` and
``backups`` share most of their grams, and long enough that unrelated
short words do not collide constantly."""

MIN_DIMENSIONS = 8
"""Below this, feature-hashing collisions dominate and every vector looks
similar to every other, which makes retrieval worse than random rather
than merely coarse."""

_WORD = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")
"""Same tokenisation as the BM25 arm, so ``pg_dump`` is one term to both.
Two arms disagreeing about what a token is makes their scores describe
different things."""


def tokenize(text: str) -> list[str]:
    """Lower-cased word tokens, compounds kept whole."""
    return _WORD.findall(text.lower())


def _features(text: str) -> list[str]:
    """Word unigrams plus character n-grams.

    Both, not either. Unigrams alone cannot see that ``backup`` and
    ``backups`` are related; n-grams alone lose word boundaries so
    ``carpet`` and ``pet`` look similar. Together the two signals cover
    each other's failure.
    """
    words = tokenize(text)
    features = list(words)
    for word in words:
        padded = f" {word} "
        features.extend(
            padded[index : index + _NGRAM_SIZE]
            for index in range(max(len(padded) - _NGRAM_SIZE + 1, 0))
        )
    return features


def _bucket(feature: str, dimensions: int) -> tuple[int, float]:
    """Which dimension a feature lands in, and with which sign.

    The sign comes from a different bit of the same hash than the index.
    Signed hashing matters: with unsigned buckets, two unrelated features
    colliding always *add*, so collisions systematically inflate
    similarity. With signs, collisions cancel on average instead.
    """
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % dimensions, 1.0 if (value >> 63) & 1 else -1.0


@dataclass(frozen=True, slots=True)
class HashingEncoder:
    """Deterministic offline encoder.

    Deterministic across processes and runs, because BLAKE2b is a fixed
    function -- unlike Python's own ``hash()``, which is randomised per
    process by default and would produce a different vector for the same
    text on every restart. Stored vectors have to stay comparable to
    freshly computed ones forever.
    """

    dimensions: int = DEFAULT_DIMENSIONS

    def __post_init__(self) -> None:
        if self.dimensions < MIN_DIMENSIONS:
            raise ValueError(
                f"dimensions must be at least {MIN_DIMENSIONS}, got {self.dimensions!r}."
            )

    @property
    def provider(self) -> str:
        return BUILTIN_PROVIDER

    @property
    def model(self) -> str:
        return BUILTIN_MODEL

    def encode(self, text: str) -> list[float]:
        """Embed one string.

        Empty or feature-less text returns the zero vector. That is the
        honest answer -- there is nothing to encode -- and it is safe
        downstream because :func:`cosine_similarity` treats a zero vector
        as similar to nothing rather than dividing by its zero norm.
        """
        vector = [0.0] * self.dimensions
        for feature in _features(text):
            index, sign = _bucket(feature, self.dimensions)
            vector[index] += sign
        return _l2_normalise(vector)

    def encode_many(self, texts: list[str]) -> list[list[float]]:
        """Embed several strings."""
        return [self.encode(text) for text in texts]


def _l2_normalise(vector: list[float]) -> list[float]:
    """Scale to unit length, leaving the zero vector alone.

    Normalising is what makes cosine similarity reduce to a dot product,
    which is how pgvector's ``<=>`` operator is cheapest to compute.
    """
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Cosine similarity of two vectors, in ``[-1, 1]``.

    Returns ``0.0`` when either is the zero vector: an undefined angle
    reported as "unrelated" is the only answer that does not lie.

    Raises:
        ValueError: If the vectors are different lengths. Comparing
            vectors of different dimensionality is always a bug --
            usually two different embedding models mixed in one index --
            and silently truncating would produce plausible, meaningless
            numbers.
    """
    if len(left) != len(right):
        raise ValueError(
            f"Cannot compare vectors of different dimensionality "
            f"({len(left)} and {len(right)}); this normally means two embedding "
            "models have been mixed in one index, whose distances are not "
            "comparable at all."
        )
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def cosine_distance(left: list[float], right: list[float]) -> float:
    """``1 - cosine_similarity``, matching pgvector's ``<=>`` operator."""
    return 1.0 - cosine_similarity(left, right)


def content_hash(text: str, *, model: str) -> str:
    """Cache key for one (text, model) pair.

    An embedding is a pure function of exactly those two things, so this
    is both the cache key and the proof that a stored vector still
    matches its chunk's current text. The model is included because the
    same string under two models is two different vectors, and a cache
    keyed on text alone would serve one model's vector to the other.
    """
    digest = hashlib.sha256()
    digest.update(model.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


__all__ = [
    "BUILTIN_MODEL",
    "BUILTIN_PROVIDER",
    "DEFAULT_DIMENSIONS",
    "MIN_DIMENSIONS",
    "HashingEncoder",
    "content_hash",
    "cosine_distance",
    "cosine_similarity",
    "tokenize",
]
