"""Retention: what to keep, at what resolution, and what to remove.

**Raw data is never authorized for deletion ahead of its downsample.**
A policy names three windows -- raw, downsampled, coarse -- and the
tempting shortcut is to delete anything older than ``raw_days`` on a
timer. That shortcut destroys data nothing has coarsened yet the moment
the downsample worker falls behind the retention sweep, even briefly.
Instead, raw deletion is bounded by a caller-supplied watermark: the
engine will not authorize deleting raw data past the point downsampling
has actually reached, regardless of what the clock says.

**Cutoffs are computed once, from one ``now``.** A sweep that recomputes
"now" per batch drifts across a long-running job and can skip or
double-touch the boundary rows depending on which side of the drift they
land on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models.enums import SignalKind


class RetentionRefusal:
    """Why a policy could not be applied. Typed, not a free-text message."""

    DISABLED = "disabled"
    NON_MONOTONIC_TIERS = "non_monotonic_tiers"


@dataclass(frozen=True, slots=True)
class RetentionPolicySpec:
    """A validated retention policy, ready to be turned into cutoffs.

    Raises:
        ValueError: When the tiers are not ``raw <= downsampled <= coarse``.
            An inverted policy has no honest reading -- deleting raw data
            *before* the downsampled window closes leaves a gap no coarser
            tier can fill in.
    """

    signal_kind: SignalKind
    environment: str
    raw_days: int
    downsampled_days: int
    coarse_days: int
    downsample_interval: timedelta
    is_enabled: bool = True

    def __post_init__(self) -> None:
        if not (self.raw_days <= self.downsampled_days <= self.coarse_days):
            raise ValueError(
                f"Retention tiers must be non-decreasing; got raw={self.raw_days}, "
                f"downsampled={self.downsampled_days}, coarse={self.coarse_days}. "
                "An inverted policy would delete raw data before anything coarser "
                "has been produced to replace it."
            )
        if self.downsample_interval <= timedelta(0):
            raise ValueError("downsample_interval must be positive.")


@dataclass(frozen=True, slots=True)
class RetentionCutoffs:
    """The three age boundaries a policy resolves to, at one instant."""

    computed_at: datetime
    raw_cutoff: datetime
    """Data older than this should exist only in downsampled form."""
    downsampled_cutoff: datetime
    """Data older than this should exist only in coarse form."""
    coarse_cutoff: datetime
    """Data older than this should not exist at all."""


def compute_cutoffs(policy: RetentionPolicySpec, *, now: datetime) -> RetentionCutoffs:
    """The age boundaries implied by a policy at a fixed instant.

    Raises:
        ValueError: On a naive ``now``, since every downstream comparison
            needs an unambiguous instant.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("compute_cutoffs requires a timezone-aware 'now'.")
    return RetentionCutoffs(
        computed_at=now,
        raw_cutoff=now - timedelta(days=policy.raw_days),
        downsampled_cutoff=now - timedelta(days=policy.downsampled_days),
        coarse_cutoff=now - timedelta(days=policy.coarse_days),
    )


@dataclass(frozen=True, slots=True)
class DownsampleAction:
    """A range that should be reduced to coarser resolution.

    ``window_end`` is exclusive and aligned to ``interval`` so repeated
    aggregation windows never straddle a boundary differently on two
    runs -- which is what makes a downsample idempotent.
    """

    window_start: datetime
    window_end: datetime
    interval: timedelta
    target_resolution: str


@dataclass(frozen=True, slots=True)
class DeleteAction:
    """A range authorized for deletion, and at what resolution."""

    resolution: str
    older_than: datetime


@dataclass(frozen=True, slots=True)
class RetentionPlan:
    """What a sweep should do, or why it did nothing.

    A disabled policy and an empty plan look identical unless the reason
    is carried explicitly -- and "nothing to delete" versus "this policy
    is off" are very different facts for an operator auditing why data
    disappeared or didn't.
    """

    policy: RetentionPolicySpec
    cutoffs: RetentionCutoffs | None
    downsample_actions: tuple[DownsampleAction, ...]
    delete_actions: tuple[DeleteAction, ...]
    refused: str | None

    @property
    def is_noop(self) -> bool:
        return not self.downsample_actions and not self.delete_actions


def _align(moment: datetime, *, epoch: datetime, interval: timedelta) -> datetime:
    """Round down to the nearest interval boundary from a fixed epoch."""
    elapsed = moment - epoch
    steps = elapsed // interval
    return epoch + steps * interval


def plan_retention(
    policy: RetentionPolicySpec,
    *,
    now: datetime,
    epoch: datetime,
    raw_downsampled_watermark: datetime | None,
    downsampled_coarsened_watermark: datetime | None,
) -> RetentionPlan:
    """Decide what a sweep may do, honoring both watermarks.

    ``raw_downsampled_watermark`` is the newest instant up to which raw
    data has actually been reduced to downsampled form. Raw deletion
    never authorizes anything past it, however far past ``raw_cutoff``
    the clock has moved -- a lagging downsample worker must stall raw
    deletion, not race it.
    """
    if not policy.is_enabled:
        return RetentionPlan(
            policy=policy,
            cutoffs=None,
            downsample_actions=(),
            delete_actions=(),
            refused=RetentionRefusal.DISABLED,
        )

    cutoffs = compute_cutoffs(policy, now=now)
    downsamples: list[DownsampleAction] = []
    deletes: list[DeleteAction] = []

    aligned_raw_cutoff = _align(
        cutoffs.raw_cutoff, epoch=epoch, interval=policy.downsample_interval
    )
    downsample_from = (
        epoch
        if raw_downsampled_watermark is None
        else max(
            epoch,
            _align(raw_downsampled_watermark, epoch=epoch, interval=policy.downsample_interval),
        )
    )
    if aligned_raw_cutoff > downsample_from:
        downsamples.append(
            DownsampleAction(
                window_start=downsample_from,
                window_end=aligned_raw_cutoff,
                interval=policy.downsample_interval,
                target_resolution="downsampled",
            )
        )

    raw_delete_bound = cutoffs.raw_cutoff
    if raw_downsampled_watermark is not None:
        raw_delete_bound = min(raw_delete_bound, raw_downsampled_watermark)
    else:
        # Nothing has ever been downsampled: authorizing a raw delete here
        # would remove data with no coarser copy anywhere. Refuse that
        # slice rather than guess.
        raw_delete_bound = epoch

    if raw_delete_bound > epoch:
        deletes.append(DeleteAction(resolution="raw", older_than=raw_delete_bound))

    downsampled_delete_bound = cutoffs.downsampled_cutoff
    if downsampled_coarsened_watermark is not None:
        downsampled_delete_bound = min(downsampled_delete_bound, downsampled_coarsened_watermark)
    else:
        downsampled_delete_bound = epoch
    if downsampled_delete_bound > epoch:
        deletes.append(DeleteAction(resolution="downsampled", older_than=downsampled_delete_bound))

    if cutoffs.coarse_cutoff > epoch:
        deletes.append(DeleteAction(resolution="coarse", older_than=cutoffs.coarse_cutoff))

    return RetentionPlan(
        policy=policy,
        cutoffs=cutoffs,
        downsample_actions=tuple(downsamples),
        delete_actions=tuple(deletes),
        refused=None,
    )


__all__ = [
    "DeleteAction",
    "DownsampleAction",
    "RetentionCutoffs",
    "RetentionPlan",
    "RetentionPolicySpec",
    "RetentionRefusal",
    "compute_cutoffs",
    "plan_retention",
]
