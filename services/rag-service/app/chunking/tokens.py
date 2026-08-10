"""Token estimation.

Ported from ``prompt-management-service/app/optimization/tokens.py``
rather than imported: services in this monorepo cannot import each
other, and this estimator is not in ``shared_core``. Keeping the two
implementations identical matters more than avoiding the duplication --
a chunk sized at 1000 tokens here and measured at 1200 tokens there
would silently overflow whichever context window was budgeted from the
other number.

**Deliberately not tiktoken.** The exact count depends on the model's own
BPE vocabulary, so no single estimator is right for every provider; the
choice is between a dependency that is exact for OpenAI and wrong
elsewhere, or one estimator that is consistently close for all of them.
This service embeds under providers with entirely different tokenizers,
so consistency wins. It is calibrated better than the widespread
``len(text) // 4`` rule: that rule is roughly 25% low on prose and
badly low on code and non-ASCII text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
"""Words and individual punctuation marks. BPE keeps common words whole
and splits punctuation off, so this matches its shape far more closely
than splitting on whitespace alone."""

_LONG_WORD_THRESHOLD = 6
"""A word longer than this is usually split into multiple BPE tokens.
Six is where common English words stop being single-token in the
vocabularies this was calibrated against."""

_CHARS_PER_SUBTOKEN = 4
"""Within a long word, roughly this many characters per extra piece."""

_NON_ASCII_MULTIPLIER = 2
"""Non-Latin scripts consume markedly more tokens per character in every
Latin-centric BPE vocabulary. Counting them double is crude but closer
than treating them as equivalent to ASCII."""


@dataclass(frozen=True, slots=True)
class TokenEstimate:
    """One text's measured size."""

    tokens: int
    characters: int
    words: int

    @property
    def characters_per_token(self) -> float:
        """Observed density. ``0.0`` for empty text rather than a
        division error."""
        return self.characters / self.tokens if self.tokens else 0.0


def estimate_tokens(text: str) -> int:
    """Estimate how many tokens *text* will consume.

    Deterministic: the same string always estimates the same count, so a
    chunk boundary computed once is stable across re-runs.

    **This is a byte-for-byte port of prompt-management-service's own
    estimator, and is kept that way on purpose.** The two are verified
    equal across prose, code, punctuation-dense text, long words, and
    CJK; a divergence would mean a chunk sized at 1000 tokens here and
    measured at 1200 there, silently overflowing whichever context
    window was budgeted from the other number.
    """
    if not text:
        return 0

    pieces = _WORD_PATTERN.findall(text)
    tokens = 0
    for piece in pieces:
        if len(piece) > _LONG_WORD_THRESHOLD:
            tokens += 1 + (len(piece) - _LONG_WORD_THRESHOLD + _CHARS_PER_SUBTOKEN - 1) // (
                _CHARS_PER_SUBTOKEN
            )
        else:
            tokens += 1
        if not piece.isascii():
            tokens += (len(piece) + _NON_ASCII_MULTIPLIER - 1) // _NON_ASCII_MULTIPLIER
    return max(tokens, 1)


def estimate(text: str) -> TokenEstimate:
    """A full :class:`TokenEstimate` for *text*.

    ``words`` counts the same word-and-punctuation pieces the token
    estimate is built from, not whitespace-separated runs. Those differ
    sharply on code -- ``def f(x): return x`` is four whitespace runs but
    eight pieces -- and reporting one while estimating from the other
    makes ``characters_per_token`` describe a split that was never used.
    """
    return TokenEstimate(
        tokens=estimate_tokens(text),
        characters=len(text),
        words=len(_WORD_PATTERN.findall(text)),
    )


def estimate_cost_usd(tokens: int, *, usd_per_1k_tokens: float) -> float:
    """What *tokens* cost at a given price.

    Raises:
        ValueError: If *tokens* or the price is negative. A negative cost
            would flow straight into an analytics rollup and quietly
            reduce a reported total.
    """
    if tokens < 0:
        raise ValueError(f"tokens must not be negative, got {tokens!r}.")
    if usd_per_1k_tokens < 0:
        raise ValueError(f"usd_per_1k_tokens must not be negative, got {usd_per_1k_tokens!r}.")
    return tokens / 1_000 * usd_per_1k_tokens


def fits_within(text: str, *, budget: int) -> bool:
    """Whether *text* fits in a *budget* of tokens."""
    return estimate_tokens(text) <= budget


def truncate_to_tokens(text: str, *, budget: int) -> str:
    """Cut *text* down until it fits *budget*, on a word boundary.

    Cuts on whitespace rather than mid-word: a truncated chunk ending in
    ``"the configura"`` is worse than one ending in ``"the"``, because a
    fragment reads as a real word to whatever consumes it next.

    Raises:
        ValueError: If *budget* is negative.
    """
    if budget < 0:
        raise ValueError(f"budget must not be negative, got {budget!r}.")
    if budget == 0:
        return ""
    if fits_within(text, budget=budget):
        return text

    words = text.split()
    kept: list[str] = []
    for word in words:
        candidate = [*kept, word]
        if estimate_tokens(" ".join(candidate)) > budget:
            break
        kept = candidate
    return " ".join(kept)


__all__ = [
    "TokenEstimate",
    "estimate",
    "estimate_cost_usd",
    "estimate_tokens",
    "fits_within",
    "truncate_to_tokens",
]
