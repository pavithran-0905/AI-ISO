"""Restore planning: point-in-time selection and restore previews.

**A restore point is chosen, never guessed.** Given a requested instant,
this module finds the latest restore point at or before it and says so
explicitly -- it never rounds forward to "the closest one," which would
silently restore data from *after* the moment a caller is trying to
recover from (typically the exact moment they are trying to recover
*from*, e.g. the instant before a bad deployment).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


class RestoreRefusal:
    """Why no restore point could be selected. Typed, not free text."""

    NO_POINTS_AVAILABLE = "no_points_available"
    REQUESTED_BEFORE_EARLIEST = "requested_before_earliest"
    POINT_EXPIRED = "point_expired"


@dataclass(frozen=True, slots=True)
class RestorePointCandidate:
    """One restore point as the selection engine needs to see it."""

    point_id: str
    available_at: datetime
    is_available: bool
    expires_at: datetime | None
    source_archive_id: str | None


@dataclass(frozen=True, slots=True)
class PointSelection:
    """The chosen restore point, or precisely why none qualified."""

    point: RestorePointCandidate | None
    refusal: str | None
    detail: str

    @property
    def is_selected(self) -> bool:
        return self.point is not None


def select_restore_point(
    requested_at: datetime, points: Sequence[RestorePointCandidate], *, now: datetime
) -> PointSelection:
    """The latest available restore point at or before *requested_at*."""
    candidates = [point for point in points if point.is_available]
    if not candidates:
        return PointSelection(
            point=None,
            refusal=RestoreRefusal.NO_POINTS_AVAILABLE,
            detail="No restore points are currently available for this target.",
        )

    eligible = [point for point in candidates if point.available_at <= requested_at]
    if not eligible:
        earliest = min(candidates, key=lambda point: point.available_at)
        return PointSelection(
            point=None,
            refusal=RestoreRefusal.REQUESTED_BEFORE_EARLIEST,
            detail=(
                f"The earliest available restore point is at "
                f"{earliest.available_at.isoformat()}, after the requested "
                f"{requested_at.isoformat()}. Nothing this old survives; widen the "
                "retention window if this instant must be recoverable."
            ),
        )

    best = max(eligible, key=lambda point: point.available_at)
    if best.expires_at is not None and best.expires_at <= now:
        return PointSelection(
            point=None,
            refusal=RestoreRefusal.POINT_EXPIRED,
            detail=(
                f"The nearest qualifying restore point "
                f"({best.available_at.isoformat()}) expired at "
                f"{best.expires_at.isoformat()}, before this restore was requested."
            ),
        )
    return PointSelection(
        point=best,
        refusal=None,
        detail=f"Selected the restore point at {best.available_at.isoformat()}.",
    )


@dataclass(frozen=True, slots=True)
class RestorePreview:
    """What a restore would do, without doing it.

    ``estimated_size_bytes`` is ``None`` when the source archive's size
    is unknown rather than reported as zero -- a preview showing "0
    bytes will be restored" reads as an empty, useless restore rather
    than an unmeasured one.
    """

    restore_kind: str
    source_ref: str
    target_ref: str
    estimated_size_bytes: int | None
    is_destructive: bool
    warnings: tuple[str, ...]


def build_preview(
    *,
    restore_kind: str,
    source_ref: str,
    target_ref: str,
    source_ref_equals_original: bool,
    estimated_size_bytes: int | None,
) -> RestorePreview:
    """Assemble a restore preview, flagging in-place restores.

    ``is_destructive`` is true exactly when the restore target is the
    original target -- an in-place restore overwrites live data, and a
    caller previewing a restore into a scratch environment must not see
    the same warning a caller about to overwrite production sees.
    """
    warnings: list[str] = []
    if source_ref_equals_original:
        warnings.append(
            "This restore writes to the original target and will overwrite its " "current data."
        )
    if estimated_size_bytes is None:
        warnings.append("The restore size could not be estimated from the source archive.")
    return RestorePreview(
        restore_kind=restore_kind,
        source_ref=source_ref,
        target_ref=target_ref,
        estimated_size_bytes=estimated_size_bytes,
        is_destructive=source_ref_equals_original,
        warnings=tuple(warnings),
    )


__all__ = [
    "PointSelection",
    "RestorePointCandidate",
    "RestorePreview",
    "RestoreRefusal",
    "build_preview",
    "select_restore_point",
]
