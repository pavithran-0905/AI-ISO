"""Combining ranked lists (docs/062 "HYBRID SEARCH": Hybrid Ranking,
Weighted Scoring).

**The scores from different retrieval arms are not comparable numbers.**
A cosine similarity lives in ``[0, 1]`` and clusters tightly near the
top; a BM25 score is unbounded and depends on corpus statistics; a graph
relevance is whatever the traversal decided. Adding or averaging them
directly lets whichever arm happens to have the widest numeric range
decide every ranking, and that arm is BM25 by a wide margin -- so a
"hybrid" search built that way is a keyword search wearing a costume.

Reciprocal Rank Fusion avoids the problem entirely by discarding the
scores and using only the *ranks*, which are comparable by construction.
It is the default here for that reason.

Weighted scoring is also offered, because docs/062 names it, but it
normalises each list to ``[0, 1]`` first -- and even then it is the more
fragile choice, because normalisation is sensitive to outliers in a way
ranks are not. The default stays RRF.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.models.enums import FusionMethod

DEFAULT_RRF_K = 60
"""RRF's smoothing constant, from the original TREC work. It controls how
sharply rank 1 beats rank 2: smaller values make the top of each list
dominate, larger values flatten the contribution across ranks. 60 is also
what ai-assistant-service uses, so a query answered by either service
fuses identically."""


@dataclass(frozen=True, slots=True)
class RankedItem:
    """One entry in one arm's ranked list."""

    key: str
    score: float
    rank: int
    """1-based, matching how ranks are stored and cited. A 0-based rank
    fed into RRF's ``1/(k + rank)`` would give the top hit a different
    weight than intended."""


@dataclass(frozen=True, slots=True)
class FusedItem:
    """One item's combined standing across every arm."""

    key: str
    score: float
    rank: int
    contributions: dict[str, float] = field(default_factory=dict)
    """Per-arm contribution to the fused score. Kept because a fused
    number with nothing behind it is unauditable -- this is what lets
    "why did this rank third?" be answered."""
    source_ranks: dict[str, int] = field(default_factory=dict)

    @property
    def arms(self) -> tuple[str, ...]:
        """Which arms found this item at all."""
        return tuple(sorted(self.source_ranks))

    @property
    def arm_count(self) -> int:
        """How many arms agreed. The signal RRF is really exploiting: an
        item found by three arms at middling rank usually beats one found
        by a single arm at rank 1."""
        return len(self.source_ranks)


def to_ranked(items: Sequence[tuple[str, float]]) -> list[RankedItem]:
    """Turn ``(key, score)`` pairs into a ranked list, best first.

    Sorts descending by score, breaking ties on the key so the ranking
    never depends on dictionary iteration order.
    """
    ordered = sorted(items, key=lambda pair: (-pair[1], pair[0]))
    return [
        RankedItem(key=key, score=score, rank=index + 1)
        for index, (key, score) in enumerate(ordered)
    ]


def reciprocal_rank_fusion(
    arms: Mapping[str, Sequence[RankedItem]], *, k: int = DEFAULT_RRF_K
) -> list[FusedItem]:
    """Fuse ranked lists by ``sum(1 / (k + rank))``.

    Raises:
        ValueError: If *k* is negative. ``k`` is added to a 1-based rank,
            so ``k = -1`` would divide by zero on the top hit.
    """
    if k < 0:
        raise ValueError(f"k must not be negative, got {k!r}.")

    totals: dict[str, float] = {}
    contributions: dict[str, dict[str, float]] = {}
    ranks: dict[str, dict[str, int]] = {}

    for arm, items in arms.items():
        for item in items:
            contribution = 1.0 / (k + item.rank)
            totals[item.key] = totals.get(item.key, 0.0) + contribution
            contributions.setdefault(item.key, {})[arm] = contribution
            ranks.setdefault(item.key, {})[arm] = item.rank

    return _finalise(totals, contributions, ranks)


def weighted_fusion(
    arms: Mapping[str, Sequence[RankedItem]], weights: Mapping[str, float]
) -> list[FusedItem]:
    """Fuse by weighted sum of min-max normalised scores.

    Each arm's scores are rescaled to ``[0, 1]`` before weighting, which
    is what makes the weights mean what they say. Without it a weight of
    0.25 on BM25 and 0.6 on cosine still lets BM25 dominate, because its
    raw numbers are an order of magnitude larger.

    An arm whose scores are all identical normalises to ``1.0``
    throughout rather than dividing by a zero range: every item did
    equally well by that arm, so none should be penalised.

    Raises:
        ValueError: If any weight is negative.
    """
    for arm, weight in weights.items():
        if weight < 0:
            raise ValueError(f"weight for {arm!r} must not be negative, got {weight!r}.")

    totals: dict[str, float] = {}
    contributions: dict[str, dict[str, float]] = {}
    ranks: dict[str, dict[str, int]] = {}

    for arm, items in arms.items():
        weight = weights.get(arm, 0.0)
        for item, normalised in zip(items, _normalise([i.score for i in items]), strict=True):
            contribution = weight * normalised
            totals[item.key] = totals.get(item.key, 0.0) + contribution
            contributions.setdefault(item.key, {})[arm] = contribution
            ranks.setdefault(item.key, {})[arm] = item.rank

    return _finalise(totals, contributions, ranks)


def max_score_fusion(arms: Mapping[str, Sequence[RankedItem]]) -> list[FusedItem]:
    """Fuse by taking each item's best normalised score across arms.

    Useful when the arms are genuinely alternative strategies rather than
    complementary evidence -- being found convincingly by one arm is
    enough, and agreement across arms adds nothing.
    """
    totals: dict[str, float] = {}
    contributions: dict[str, dict[str, float]] = {}
    ranks: dict[str, dict[str, int]] = {}

    for arm, items in arms.items():
        for item, normalised in zip(items, _normalise([i.score for i in items]), strict=True):
            totals[item.key] = max(totals.get(item.key, 0.0), normalised)
            contributions.setdefault(item.key, {})[arm] = normalised
            ranks.setdefault(item.key, {})[arm] = item.rank

    return _finalise(totals, contributions, ranks)


def fuse(
    arms: Mapping[str, Sequence[RankedItem]],
    *,
    method: FusionMethod = FusionMethod.RRF,
    weights: Mapping[str, float] | None = None,
    k: int = DEFAULT_RRF_K,
) -> list[FusedItem]:
    """Fuse *arms* by the named method.

    Raises:
        ValueError: If ``WEIGHTED_SCORE`` is requested with no weights --
            every weight would default to zero and the fused ranking
            would be arbitrary, which is worse than refusing.
    """
    chosen = FusionMethod(method)
    if chosen is FusionMethod.RRF:
        return reciprocal_rank_fusion(arms, k=k)
    if chosen is FusionMethod.MAX_SCORE:
        return max_score_fusion(arms)
    if not weights:
        raise ValueError(
            "WEIGHTED_SCORE fusion requires weights; with none supplied every "
            "arm would contribute zero and the resulting order would be arbitrary."
        )
    return weighted_fusion(arms, weights)


def _normalise(scores: Sequence[float]) -> list[float]:
    """Min-max rescale *scores* into ``[0, 1]``.

    Returns all-``1.0`` for a constant list. Dividing by a zero range
    would raise; returning all-zero would erase an arm that ranked
    everything equally well.
    """
    if not scores:
        return []
    low, high = min(scores), max(scores)
    spread = high - low
    if spread <= 0:
        return [1.0] * len(scores)
    return [(score - low) / spread for score in scores]


def _finalise(
    totals: Mapping[str, float],
    contributions: Mapping[str, Mapping[str, float]],
    ranks: Mapping[str, Mapping[str, int]],
) -> list[FusedItem]:
    """Order by fused score and assign final 1-based ranks.

    Ties break on the best rank any arm gave the item, then on the key --
    so the order is fully determined and never depends on dictionary
    iteration.
    """
    ordered = sorted(
        totals,
        key=lambda key: (-totals[key], min(ranks[key].values()), key),
    )
    return [
        FusedItem(
            key=key,
            score=totals[key],
            rank=index + 1,
            contributions=dict(contributions[key]),
            source_ranks=dict(ranks[key]),
        )
        for index, key in enumerate(ordered)
    ]


__all__ = [
    "DEFAULT_RRF_K",
    "FusedItem",
    "RankedItem",
    "fuse",
    "max_score_fusion",
    "reciprocal_rank_fusion",
    "to_ranked",
    "weighted_fusion",
]
