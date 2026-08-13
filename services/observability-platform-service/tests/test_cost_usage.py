"""Tests for app.cost.usage -- usage records, coverage, storage integral."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.cost.enums import MeterBasis
from app.cost.usage import (
    BYTES_PER_GIB,
    CoverageWindow,
    StorageSample,
    UsageRecord,
    dedupe_usage,
    detect_overlaps,
    integrate_storage,
    observed_fraction,
    split_at_boundaries,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _record(
    record_id: str, quantity: str, *, start: datetime = T0, minutes: int = 60, **overrides: object
) -> UsageRecord:
    defaults = {
        "record_id": record_id,
        "source": "collector-1",
        "meter": "cpu_hours",
        "unit": "hour",
        "quantity": Decimal(quantity),
        "window_start": start,
        "window_end": start + timedelta(minutes=minutes),
    }
    defaults.update(overrides)
    return UsageRecord(**defaults)  # type: ignore[arg-type]


class TestUsageRecord:
    def test_end_before_start_raises(self) -> None:
        with pytest.raises(ValueError, match="ends before"):
            UsageRecord(
                record_id="r1",
                source="s",
                meter="m",
                unit="u",
                quantity=Decimal(1),
                window_start=T0,
                window_end=T0 - timedelta(hours=1),
            )

    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-naive"):
            UsageRecord(
                record_id="r1",
                source="s",
                meter="m",
                unit="u",
                quantity=Decimal(1),
                window_start=datetime(2026, 1, 1),
                window_end=datetime(2026, 1, 1, 1),
            )

    def test_dedupe_key(self) -> None:
        record = _record("r1", "1")
        assert record.dedupe_key == ("collector-1", "r1")

    def test_duration(self) -> None:
        record = _record("r1", "1", minutes=30)
        assert record.duration == timedelta(minutes=30)

    def test_negative_quantity_allowed(self) -> None:
        record = _record("r1", "-5")
        assert record.quantity == Decimal("-5")


class TestCoverageWindow:
    def test_covers_matching_meter(self) -> None:
        window = CoverageWindow(
            source="s", start=T0, end=T0 + timedelta(hours=1), meter="cpu_hours"
        )
        assert window.covers(T0, "cpu_hours")
        assert not window.covers(T0, "gpu_hours")

    def test_none_meter_covers_any(self) -> None:
        window = CoverageWindow(source="s", start=T0, end=T0 + timedelta(hours=1))
        assert window.covers(T0, "anything")


class TestDedupeUsage:
    def test_no_duplicates(self) -> None:
        result = dedupe_usage([_record("r1", "1"), _record("r2", "2")])
        assert len(result.kept) == 2
        assert result.duplicates_dropped == 0
        assert result.conflicting == ()

    def test_identical_duplicate_dropped(self) -> None:
        result = dedupe_usage([_record("r1", "1"), _record("r1", "1")])
        assert len(result.kept) == 1
        assert result.duplicates_dropped == 1
        assert result.conflicting == ()

    def test_conflicting_duplicate_reported(self) -> None:
        result = dedupe_usage([_record("r1", "1"), _record("r1", "2")])
        assert len(result.kept) == 1
        assert result.kept[0].quantity == Decimal("1")  # first kept
        assert len(result.conflicting) == 1
        assert result.conflicting[0].quantities == (Decimal("1"), Decimal("2"))


class TestDetectOverlaps:
    def test_no_resource_id_skipped(self) -> None:
        assert detect_overlaps([_record("r1", "1", resource_id=None)]) == ()

    def test_non_overlapping_windows(self) -> None:
        r1 = _record("r1", "1", resource_id="res-1", start=T0, minutes=60)
        r2 = _record("r2", "1", resource_id="res-1", start=T0 + timedelta(hours=1), minutes=60)
        assert detect_overlaps([r1, r2]) == ()

    def test_overlapping_windows_detected(self) -> None:
        r1 = _record("r1", "1", resource_id="res-1", start=T0, minutes=90)
        r2 = _record("r2", "1", resource_id="res-1", start=T0 + timedelta(minutes=30), minutes=60)
        issues = detect_overlaps([r1, r2])
        assert len(issues) == 1
        assert issues[0].resource_id == "res-1"
        assert issues[0].overlap_seconds == pytest.approx(60 * 60)


class TestSplitAtBoundaries:
    def test_no_boundaries_returns_unchanged(self) -> None:
        record = _record("r1", "10", minutes=120)
        result = split_at_boundaries(record, [])
        assert result.parts == (record,)
        assert result.quantity_residual == Decimal(0)

    def test_point_event_never_split(self) -> None:
        record = _record("r1", "1", minutes=120, basis=MeterBasis.POINT_EVENT)
        boundary = T0 + timedelta(minutes=60)
        result = split_at_boundaries(record, [boundary])
        assert result.parts == (record,)

    def test_splits_at_midpoint_and_sums_to_original(self) -> None:
        record = _record("r1", "10", minutes=120)
        boundary = T0 + timedelta(minutes=60)
        result = split_at_boundaries(record, [boundary])
        assert len(result.parts) == 2
        total_quantity = sum((part.quantity for part in result.parts), Decimal(0))
        assert total_quantity == Decimal("10")
        assert result.quantity_residual == Decimal(0)
        total_duration = sum((part.duration for part in result.parts), timedelta(0))
        assert total_duration == record.duration

    def test_boundary_outside_window_is_ignored(self) -> None:
        record = _record("r1", "10", minutes=60)
        boundary = T0 + timedelta(hours=5)
        result = split_at_boundaries(record, [boundary])
        assert result.parts == (record,)


class TestIntegrateStorage:
    def test_non_positive_period_raises(self) -> None:
        with pytest.raises(ValueError, match="positive length"):
            integrate_storage(
                [],
                period_start=T0,
                period_end=T0,
                sample_interval=timedelta(hours=1),
                seconds_per_month=Decimal(2_628_000),
            )

    def test_non_positive_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            integrate_storage(
                [],
                period_start=T0,
                period_end=T0 + timedelta(days=1),
                sample_interval=timedelta(0),
                seconds_per_month=Decimal(2_628_000),
            )

    def test_no_samples_fully_uncovered(self) -> None:
        result = integrate_storage(
            [],
            period_start=T0,
            period_end=T0 + timedelta(days=1),
            sample_interval=timedelta(hours=1),
            seconds_per_month=Decimal(2_628_000),
        )
        assert result.gib_months == Decimal(0)
        assert len(result.uncovered) == 1
        assert result.is_partial

    def test_late_first_sample_reports_leading_gap(self) -> None:
        samples = [StorageSample(at=T0 + timedelta(hours=2), stored_bytes=BYTES_PER_GIB)]
        result = integrate_storage(
            samples,
            period_start=T0,
            period_end=T0 + timedelta(hours=4),
            sample_interval=timedelta(hours=1),
            seconds_per_month=Decimal(2_628_000),
        )
        assert any("starts before the first sample" in gap.reason for gap in result.uncovered)

    def test_full_coverage_zero_order_hold(self) -> None:
        samples = [
            StorageSample(at=T0, stored_bytes=BYTES_PER_GIB),
            StorageSample(at=T0 + timedelta(hours=1), stored_bytes=BYTES_PER_GIB),
        ]
        result = integrate_storage(
            samples,
            period_start=T0,
            period_end=T0 + timedelta(hours=2),
            sample_interval=timedelta(hours=1),
            seconds_per_month=Decimal(2_628_000),
        )
        assert not result.is_partial
        assert result.gib_months > Decimal(0)
        assert result.covered_fraction == pytest.approx(Decimal(1), abs=1e-6)

    def test_gap_exceeding_max_multiplier_uncovered(self) -> None:
        samples = [
            StorageSample(at=T0, stored_bytes=BYTES_PER_GIB),
            StorageSample(at=T0 + timedelta(hours=10), stored_bytes=BYTES_PER_GIB),
        ]
        result = integrate_storage(
            samples,
            period_start=T0,
            period_end=T0 + timedelta(hours=11),
            sample_interval=timedelta(hours=1),
            seconds_per_month=Decimal(2_628_000),
        )
        assert result.is_partial
        assert any("collector stopped" in gap.reason for gap in result.uncovered)

    def test_covered_fraction_zero_period(self) -> None:
        from app.cost.usage import StorageIntegral

        integral = StorageIntegral(
            gib_months=Decimal(0),
            covered_seconds=Decimal(0),
            period_seconds=Decimal(0),
            uncovered=(),
        )
        assert integral.covered_fraction == Decimal(0)


class TestObservedFraction:
    def test_none_when_no_windows(self) -> None:
        result = observed_fraction(
            [], period_start=T0, period_end=T0 + timedelta(hours=1), meter="cpu_hours"
        )
        assert result is None

    def test_full_coverage(self) -> None:
        window = CoverageWindow(
            source="s", start=T0, end=T0 + timedelta(hours=2), meter="cpu_hours"
        )
        result = observed_fraction(
            [window], period_start=T0, period_end=T0 + timedelta(hours=2), meter="cpu_hours"
        )
        assert result == pytest.approx(Decimal(1), abs=1e-6)

    def test_partial_coverage_merges_overlapping_windows(self) -> None:
        windows = [
            CoverageWindow(source="a", start=T0, end=T0 + timedelta(hours=1), meter="cpu_hours"),
            CoverageWindow(
                source="b",
                start=T0 + timedelta(minutes=30),
                end=T0 + timedelta(hours=2),
                meter="cpu_hours",
            ),
        ]
        result = observed_fraction(
            windows, period_start=T0, period_end=T0 + timedelta(hours=4), meter="cpu_hours"
        )
        assert result == pytest.approx(Decimal(2) / Decimal(4), abs=1e-6)

    def test_mismatched_meter_excluded(self) -> None:
        window = CoverageWindow(
            source="s", start=T0, end=T0 + timedelta(hours=2), meter="gpu_hours"
        )
        result = observed_fraction(
            [window], period_start=T0, period_end=T0 + timedelta(hours=2), meter="cpu_hours"
        )
        assert result is None
