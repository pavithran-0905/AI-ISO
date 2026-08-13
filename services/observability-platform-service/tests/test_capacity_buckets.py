"""Tests for app.capacity.buckets -- gridding raw samples for regression."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.capacity.buckets import (
    MIN_SAMPLES_FOR_P95,
    Sample,
    TimeWindow,
    assess_coverage,
    bucket_samples,
    nearest_rank_p95,
)

ORIGIN = datetime(2026, 1, 1, tzinfo=UTC)


class TestSample:
    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-naive"):
            Sample(at=datetime(2026, 1, 1), value=1.0)

    def test_aware_datetime_ok(self) -> None:
        Sample(at=ORIGIN, value=1.0)


class TestTimeWindow:
    def test_end_before_start_raises(self) -> None:
        with pytest.raises(ValueError, match="not after start"):
            TimeWindow(start=ORIGIN, end=ORIGIN - timedelta(hours=1))

    def test_contains(self) -> None:
        window = TimeWindow(start=ORIGIN, end=ORIGIN + timedelta(hours=1))
        assert window.contains(ORIGIN)
        assert not window.contains(ORIGIN + timedelta(hours=1))

    def test_overlaps(self) -> None:
        window = TimeWindow(start=ORIGIN, end=ORIGIN + timedelta(hours=1))
        assert window.overlaps(ORIGIN + timedelta(minutes=30), ORIGIN + timedelta(hours=2))
        assert not window.overlaps(ORIGIN + timedelta(hours=2), ORIGIN + timedelta(hours=3))


class TestNearestRankP95:
    def test_none_below_min_samples(self) -> None:
        assert nearest_rank_p95([1.0] * (MIN_SAMPLES_FOR_P95 - 1)) is None

    def test_computes_at_min_samples(self) -> None:
        values = [float(i) for i in range(1, MIN_SAMPLES_FOR_P95 + 1)]
        result = nearest_rank_p95(values)
        assert result is not None
        assert result <= max(values)


class TestBucketSamples:
    def test_non_positive_bucket_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            bucket_samples([Sample(at=ORIGIN, value=1.0)], bucket=timedelta(0), origin=ORIGIN)

    def test_naive_origin_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-naive"):
            bucket_samples(
                [Sample(at=ORIGIN, value=1.0)],
                bucket=timedelta(hours=1),
                origin=datetime(2026, 1, 1),
            )

    def test_empty_samples_returns_empty(self) -> None:
        assert bucket_samples([], bucket=timedelta(hours=1), origin=ORIGIN) == ()

    def test_gaps_are_emitted_not_dropped(self) -> None:
        samples = [
            Sample(at=ORIGIN, value=1.0),
            Sample(at=ORIGIN + timedelta(hours=3), value=2.0),
        ]
        points = bucket_samples(samples, bucket=timedelta(hours=1), origin=ORIGIN)
        assert len(points) == 4
        assert points[1].sample_count == 0
        assert points[1].peak is None
        assert points[1].mean is None
        assert not points[1].is_measured

    def test_multiple_samples_in_one_bucket_are_reduced(self) -> None:
        samples = [
            Sample(at=ORIGIN + timedelta(minutes=1), value=10.0),
            Sample(at=ORIGIN + timedelta(minutes=2), value=20.0),
            Sample(at=ORIGIN + timedelta(minutes=3), value=30.0),
        ]
        points = bucket_samples(samples, bucket=timedelta(hours=1), origin=ORIGIN)
        assert len(points) == 1
        point = points[0]
        assert point.sample_count == 3
        assert point.peak == 30.0
        assert point.minimum == 10.0
        assert point.mean == pytest.approx(20.0)

    def test_expected_cadence_gives_coverage(self) -> None:
        samples = [Sample(at=ORIGIN + timedelta(minutes=i), value=1.0) for i in range(30)]
        points = bucket_samples(
            samples,
            bucket=timedelta(hours=1),
            origin=ORIGIN,
            expected_cadence=timedelta(minutes=1),
        )
        assert len(points) == 1
        assert points[0].expected_samples == 60
        assert points[0].coverage == pytest.approx(30 / 60)

    def test_excluded_window_marks_bucket_excluded(self) -> None:
        samples = [Sample(at=ORIGIN + timedelta(minutes=30), value=1.0)]
        excluded = [TimeWindow(start=ORIGIN, end=ORIGIN + timedelta(hours=1))]
        points = bucket_samples(
            samples, bucket=timedelta(hours=1), origin=ORIGIN, excluded_windows=excluded
        )
        assert points[0].excluded
        assert not points[0].is_measured


class TestAssessCoverage:
    def test_empty_points(self) -> None:
        report = assess_coverage(())
        assert report.total_buckets == 0
        assert report.ratio == 0.0

    def test_full_coverage(self) -> None:
        samples = [Sample(at=ORIGIN + timedelta(hours=i), value=1.0) for i in range(5)]
        points = bucket_samples(samples, bucket=timedelta(hours=1), origin=ORIGIN)
        report = assess_coverage(points)
        assert report.ratio == 1.0
        assert report.largest_gap_buckets == 0

    def test_gap_is_measured(self) -> None:
        samples = [
            Sample(at=ORIGIN, value=1.0),
            Sample(at=ORIGIN + timedelta(hours=5), value=1.0),
        ]
        points = bucket_samples(samples, bucket=timedelta(hours=1), origin=ORIGIN)
        report = assess_coverage(points)
        assert report.total_buckets == 6
        assert report.measured_buckets == 2
        assert report.largest_gap_buckets == 4
        assert report.largest_gap_ratio == pytest.approx(4 / 6)
