"""Small text helpers shared by the analysis engines."""

from __future__ import annotations


def vocabulary(words: str) -> frozenset[str]:
    """A word list written as prose rather than as dozens of quoted items.

    Sixty words as a list literal is sixty pairs of quotes and commas to
    read past, and a vocabulary is edited far more often than it is
    parsed.
    """
    return frozenset(words.split())


__all__ = ["vocabulary"]
