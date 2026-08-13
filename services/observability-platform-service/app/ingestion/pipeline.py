"""Signal ingestion: validate, clamp, dedupe, and never silently drop.

**A batch of a thousand where three are malformed is neither accepted
nor rejected.** Reporting either loses the three or loses the nine
hundred and ninety-seven. Every batch returns one record per input item,
so a caller can always reconcile what they sent against what happened to
each one.

**Order matters.** Validation runs before deduplication: a malformed
record that happens to share a dedupe key with a good one must not be
silently absorbed into an "already seen" bucket, which would report
success for a record that was never actually accepted.

**Clock skew is clamped, not trusted.** A client's clock can be minutes
or days wrong, and a span claiming to end next Tuesday corrupts every
duration and every window it lands into for as long as the data lives.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models.enums import IngestionStatus, SignalKind


class RejectionReason:
    """Typed rejection reasons -- not a free-text message.

    A caller retrying on a generic "invalid" string cannot tell a
    transient problem (batch too large, try smaller batches) from a
    permanent one (timestamp too old, this record can never be accepted).
    """

    BATCH_TOO_LARGE = "batch_too_large"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    TIMESTAMP_TOO_OLD = "timestamp_too_old"
    TOO_MANY_LABELS = "too_many_labels"
    LABEL_VALUE_TOO_LONG = "label_value_too_long"
    MESSAGE_TOO_LONG = "message_too_long"
    NAIVE_TIMESTAMP = "naive_timestamp"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class RawSignal:
    """One signal as it arrives, before any correction is applied."""

    dedupe_key: str
    signal_kind: SignalKind
    occurred_at: datetime | None
    labels: dict[str, str] = field(default_factory=dict)
    message: str | None = None
    required_fields_present: bool = True


@dataclass(frozen=True, slots=True)
class AcceptedSignal:
    """A signal that passed every gate, with its timestamp corrected.

    ``occurred_at`` may have been clamped; ``was_clamped`` says so rather
    than leaving the correction invisible in a field that looks like raw
    client data.
    """

    dedupe_key: str
    signal_kind: SignalKind
    occurred_at: datetime
    received_at: datetime
    was_clamped: bool
    labels: dict[str, str]
    message: str | None


@dataclass(frozen=True, slots=True)
class SignalOutcome:
    """What happened to exactly one input record."""

    dedupe_key: str
    accepted: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class IngestionLimits:
    """The gates a batch and its members must pass.

    Mirrors :class:`app.config.settings.ObservabilityPlatformServiceSettings`
    field-for-field so the pipeline and the settings that govern it cannot
    drift apart silently.
    """

    max_batch_size: int
    max_label_count: int
    max_label_value_length: int
    max_message_length: int
    clock_skew_tolerance: timedelta
    max_age: timedelta


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """The outcome of one batch, with the raw counts a report needs."""

    status: IngestionStatus
    accepted: tuple[AcceptedSignal, ...]
    outcomes: tuple[SignalOutcome, ...]
    accepted_count: int
    rejected_count: int
    duplicate_count: int

    @property
    def is_complete_failure(self) -> bool:
        return self.accepted_count == 0 and self.rejected_count > 0


def _validate(  # noqa: PLR0911 - one exit per gate, by design
    signal: RawSignal, limits: IngestionLimits, *, now: datetime
) -> tuple[AcceptedSignal, None] | tuple[None, str]:
    """One record through every gate but deduplication.

    Deduplication is not here: it needs to see every *valid* record
    together, and running it per-record would make the dedupe key of a
    rejected record consume a slot a valid duplicate should have filled.
    """
    if not signal.required_fields_present:
        return None, RejectionReason.MISSING_REQUIRED_FIELD
    if signal.occurred_at is None:
        return None, RejectionReason.MISSING_REQUIRED_FIELD
    if signal.occurred_at.tzinfo is None or signal.occurred_at.utcoffset() is None:
        return None, RejectionReason.NAIVE_TIMESTAMP
    if len(signal.labels) > limits.max_label_count:
        return None, RejectionReason.TOO_MANY_LABELS
    if any(len(value) > limits.max_label_value_length for value in signal.labels.values()):
        return None, RejectionReason.LABEL_VALUE_TOO_LONG
    if signal.message is not None and len(signal.message) > limits.max_message_length:
        return None, RejectionReason.MESSAGE_TOO_LONG

    age = now - signal.occurred_at
    if age > limits.max_age:
        # Accepting this would silently rewrite a window somebody has
        # already reported on, so it is rejected rather than backdated.
        return None, RejectionReason.TIMESTAMP_TOO_OLD

    clamped_at = signal.occurred_at
    was_clamped = False
    if signal.occurred_at - now > limits.clock_skew_tolerance:
        # A future timestamp is clamped rather than rejected: the record
        # itself may be legitimate telemetry with a wrong clock, and
        # discarding it loses real data a rejection-only policy would not.
        clamped_at = now + limits.clock_skew_tolerance
        was_clamped = True

    return (
        AcceptedSignal(
            dedupe_key=signal.dedupe_key,
            signal_kind=signal.signal_kind,
            occurred_at=clamped_at,
            received_at=now,
            was_clamped=was_clamped,
            labels=dict(signal.labels),
            message=signal.message,
        ),
        None,
    )


def ingest_batch(
    signals: Sequence[RawSignal], limits: IngestionLimits, *, now: datetime
) -> IngestionResult:
    """Validate, clamp and dedupe one batch, accounting for every record.

    Raises:
        ValueError: When the batch itself exceeds the size limit. This is
            the one gate applied before any per-record work, because a
            batch this large should not be partially processed and then
            rejected -- the caller needs to resend in smaller pieces, not
            reconcile which of ten thousand records landed.
    """
    if len(signals) > limits.max_batch_size:
        raise ValueError(
            f"Batch of {len(signals)} exceeds the {limits.max_batch_size} limit. "
            f"{RejectionReason.BATCH_TOO_LARGE}: resend in smaller batches rather "
            "than have this one partially accepted."
        )
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("ingest_batch requires a timezone-aware 'now'.")

    outcomes: list[SignalOutcome] = []
    accepted: list[AcceptedSignal] = []
    seen: set[str] = set()
    duplicates = 0

    for signal in signals:
        record, reason = _validate(signal, limits, now=now)
        if record is None:
            outcomes.append(SignalOutcome(signal.dedupe_key, accepted=False, reason=reason))
            continue
        if record.dedupe_key in seen:
            duplicates += 1
            outcomes.append(
                SignalOutcome(signal.dedupe_key, accepted=False, reason=RejectionReason.DUPLICATE)
            )
            continue
        seen.add(record.dedupe_key)
        accepted.append(record)
        outcomes.append(SignalOutcome(signal.dedupe_key, accepted=True))

    rejected = len(outcomes) - len(accepted)
    if not signals:
        status = IngestionStatus.ACCEPTED
    elif not accepted:
        status = IngestionStatus.REJECTED
    elif rejected:
        status = IngestionStatus.PARTIAL
    else:
        status = IngestionStatus.ACCEPTED

    return IngestionResult(
        status=status,
        accepted=tuple(accepted),
        outcomes=tuple(outcomes),
        accepted_count=len(accepted),
        rejected_count=rejected,
        duplicate_count=duplicates,
    )


__all__ = [
    "AcceptedSignal",
    "IngestionLimits",
    "IngestionResult",
    "RawSignal",
    "RejectionReason",
    "SignalOutcome",
    "ingest_batch",
]
