"""Tests for app.ingestion.pipeline -- validate, clamp, dedupe."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.ingestion.pipeline import (
    IngestionLimits,
    RawSignal,
    RejectionReason,
    ingest_batch,
)
from app.models.enums import IngestionStatus, SignalKind

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _limits(**overrides: object) -> IngestionLimits:
    defaults: dict[str, object] = {
        "max_batch_size": 100,
        "max_label_count": 10,
        "max_label_value_length": 100,
        "max_message_length": 1000,
        "clock_skew_tolerance": timedelta(minutes=5),
        "max_age": timedelta(days=30),
    }
    defaults.update(overrides)
    return IngestionLimits(**defaults)  # type: ignore[arg-type]


def _signal(key: str, **overrides: object) -> RawSignal:
    defaults: dict[str, object] = {
        "dedupe_key": key,
        "signal_kind": SignalKind.METRIC,
        "occurred_at": NOW,
    }
    defaults.update(overrides)
    return RawSignal(**defaults)  # type: ignore[arg-type]


class TestIngestBatch:
    def test_batch_too_large_raises(self) -> None:
        limits = _limits(max_batch_size=1)
        with pytest.raises(ValueError, match="exceeds"):
            ingest_batch([_signal("a"), _signal("b")], limits, now=NOW)

    def test_naive_now_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ingest_batch([], _limits(), now=datetime(2026, 1, 1))

    def test_empty_batch_is_accepted_status(self) -> None:
        result = ingest_batch([], _limits(), now=NOW)
        assert result.status is IngestionStatus.ACCEPTED
        assert result.accepted_count == 0

    def test_all_accepted(self) -> None:
        result = ingest_batch([_signal("a"), _signal("b")], _limits(), now=NOW)
        assert result.status is IngestionStatus.ACCEPTED
        assert result.accepted_count == 2
        assert result.rejected_count == 0
        assert not result.is_complete_failure

    def test_missing_required_fields_rejected(self) -> None:
        result = ingest_batch([_signal("a", required_fields_present=False)], _limits(), now=NOW)
        assert result.status is IngestionStatus.REJECTED
        assert result.outcomes[0].reason == RejectionReason.MISSING_REQUIRED_FIELD
        assert result.is_complete_failure

    def test_missing_timestamp_rejected(self) -> None:
        result = ingest_batch([_signal("a", occurred_at=None)], _limits(), now=NOW)
        assert result.outcomes[0].reason == RejectionReason.MISSING_REQUIRED_FIELD

    def test_naive_timestamp_rejected(self) -> None:
        result = ingest_batch([_signal("a", occurred_at=datetime(2026, 1, 1))], _limits(), now=NOW)
        assert result.outcomes[0].reason == RejectionReason.NAIVE_TIMESTAMP

    def test_too_many_labels_rejected(self) -> None:
        labels = {f"k{i}": "v" for i in range(20)}
        result = ingest_batch([_signal("a", labels=labels)], _limits(max_label_count=5), now=NOW)
        assert result.outcomes[0].reason == RejectionReason.TOO_MANY_LABELS

    def test_label_value_too_long_rejected(self) -> None:
        result = ingest_batch(
            [_signal("a", labels={"k": "x" * 200})], _limits(max_label_value_length=10), now=NOW
        )
        assert result.outcomes[0].reason == RejectionReason.LABEL_VALUE_TOO_LONG

    def test_message_too_long_rejected(self) -> None:
        result = ingest_batch(
            [_signal("a", message="x" * 200)], _limits(max_message_length=10), now=NOW
        )
        assert result.outcomes[0].reason == RejectionReason.MESSAGE_TOO_LONG

    def test_timestamp_too_old_rejected(self) -> None:
        old = NOW - timedelta(days=365)
        result = ingest_batch(
            [_signal("a", occurred_at=old)], _limits(max_age=timedelta(days=30)), now=NOW
        )
        assert result.outcomes[0].reason == RejectionReason.TIMESTAMP_TOO_OLD

    def test_future_timestamp_clamped_not_rejected(self) -> None:
        future = NOW + timedelta(hours=1)
        result = ingest_batch(
            [_signal("a", occurred_at=future)],
            _limits(clock_skew_tolerance=timedelta(minutes=5)),
            now=NOW,
        )
        assert result.accepted_count == 1
        assert result.accepted[0].was_clamped
        assert result.accepted[0].occurred_at == NOW + timedelta(minutes=5)

    def test_within_skew_tolerance_not_clamped(self) -> None:
        near_future = NOW + timedelta(minutes=1)
        result = ingest_batch(
            [_signal("a", occurred_at=near_future)],
            _limits(clock_skew_tolerance=timedelta(minutes=5)),
            now=NOW,
        )
        assert result.accepted_count == 1
        assert not result.accepted[0].was_clamped

    def test_duplicate_within_batch_rejected(self) -> None:
        result = ingest_batch([_signal("a"), _signal("a")], _limits(), now=NOW)
        assert result.accepted_count == 1
        assert result.duplicate_count == 1
        assert result.outcomes[1].reason == RejectionReason.DUPLICATE

    def test_invalid_record_does_not_consume_dedupe_slot(self) -> None:
        # A malformed record sharing a dedupe key with a valid one must not
        # be silently absorbed as "already seen".
        bad = _signal("a", required_fields_present=False)
        good = _signal("a")
        result = ingest_batch([bad, good], _limits(), now=NOW)
        assert result.accepted_count == 1
        assert result.outcomes[0].reason == RejectionReason.MISSING_REQUIRED_FIELD
        assert result.outcomes[1].accepted

    def test_partial_status_when_mixed(self) -> None:
        result = ingest_batch(
            [_signal("a"), _signal("b", required_fields_present=False)], _limits(), now=NOW
        )
        assert result.status is IngestionStatus.PARTIAL

    def test_one_outcome_per_input_record(self) -> None:
        signals = [_signal("a"), _signal("b", required_fields_present=False), _signal("a")]
        result = ingest_batch(signals, _limits(), now=NOW)
        assert len(result.outcomes) == len(signals)
