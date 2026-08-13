"""Label fingerprinting -- the seam between a metric's label set and its
stored identity.

A single function, kept apart from the ingestion service so both the
write path (finding or creating a series) and any future read-side tool
(deduplicating a manual import, say) hash labels exactly the same way.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping


def fingerprint_labels(labels: Mapping[str, str]) -> str:
    """A stable hash of a label set, independent of insertion order.

    Sorted before joining: two label dicts built in different orders --
    which is the normal case across two different collectors describing
    the same series -- must hash identically, or the unique constraint on
    ``(organization_id, name, label_fingerprint)`` splits one series into
    two and halves every rate computed from it.
    """
    canonical = "&".join(f"{key}={value}" for key, value in sorted(labels.items()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:64]


__all__ = ["fingerprint_labels"]
