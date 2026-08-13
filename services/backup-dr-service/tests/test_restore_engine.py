"""Tests for app.restore.engine: restore point selection and preview building."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.restore.engine import (
    RestorePointCandidate,
    RestoreRefusal,
    build_preview,
    select_restore_point,
)

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def _point(
    point_id: str,
    available_at: datetime,
    *,
    is_available: bool = True,
    expires_at: datetime | None = None,
) -> RestorePointCandidate:
    return RestorePointCandidate(
        point_id=point_id,
        available_at=available_at,
        is_available=is_available,
        expires_at=expires_at,
        source_archive_id=f"archive-{point_id}",
    )


class TestSelectRestorePoint:
    def test_no_points_at_all(self) -> None:
        result = select_restore_point(NOW, [], now=NOW)
        assert not result.is_selected
        assert result.refusal == RestoreRefusal.NO_POINTS_AVAILABLE

    def test_all_points_unavailable(self) -> None:
        points = [_point("p1", NOW - timedelta(hours=1), is_available=False)]
        result = select_restore_point(NOW, points, now=NOW)
        assert not result.is_selected
        assert result.refusal == RestoreRefusal.NO_POINTS_AVAILABLE

    def test_requested_before_earliest(self) -> None:
        points = [_point("p1", NOW)]
        requested = NOW - timedelta(days=1)
        result = select_restore_point(requested, points, now=NOW)
        assert not result.is_selected
        assert result.refusal == RestoreRefusal.REQUESTED_BEFORE_EARLIEST
        assert "earliest available restore point" in result.detail

    def test_selects_latest_at_or_before_requested(self) -> None:
        points = [
            _point("p1", NOW - timedelta(hours=3)),
            _point("p2", NOW - timedelta(hours=1)),
            _point("p3", NOW + timedelta(hours=1)),
        ]
        result = select_restore_point(NOW, points, now=NOW)
        assert result.is_selected
        assert result.point is not None
        assert result.point.point_id == "p2"

    def test_never_rounds_forward_to_future_point(self) -> None:
        points = [_point("future", NOW + timedelta(hours=1))]
        result = select_restore_point(NOW, points, now=NOW)
        assert not result.is_selected
        assert result.refusal == RestoreRefusal.REQUESTED_BEFORE_EARLIEST

    def test_exact_match_at_requested_instant(self) -> None:
        points = [_point("exact", NOW)]
        result = select_restore_point(NOW, points, now=NOW)
        assert result.is_selected
        assert result.point is not None
        assert result.point.point_id == "exact"

    def test_expired_point_refused(self) -> None:
        points = [
            _point(
                "expired",
                NOW - timedelta(hours=1),
                expires_at=NOW - timedelta(minutes=1),
            )
        ]
        result = select_restore_point(NOW, points, now=NOW)
        assert not result.is_selected
        assert result.refusal == RestoreRefusal.POINT_EXPIRED

    def test_not_yet_expired_point_selected(self) -> None:
        points = [
            _point(
                "still-good",
                NOW - timedelta(hours=1),
                expires_at=NOW + timedelta(hours=1),
            )
        ]
        result = select_restore_point(NOW, points, now=NOW)
        assert result.is_selected

    def test_no_expiry_never_expires(self) -> None:
        points = [_point("forever", NOW - timedelta(days=100), expires_at=None)]
        result = select_restore_point(NOW, points, now=NOW)
        assert result.is_selected


class TestBuildPreview:
    def test_in_place_restore_is_destructive(self) -> None:
        preview = build_preview(
            restore_kind="full",
            source_ref="archive-1",
            target_ref="target-1",
            source_ref_equals_original=True,
            estimated_size_bytes=1024,
        )
        assert preview.is_destructive
        assert any("overwrite" in w for w in preview.warnings)

    def test_restore_to_scratch_is_not_destructive(self) -> None:
        preview = build_preview(
            restore_kind="full",
            source_ref="archive-1",
            target_ref="scratch-env",
            source_ref_equals_original=False,
            estimated_size_bytes=1024,
        )
        assert not preview.is_destructive
        assert not any("overwrite" in w for w in preview.warnings)

    def test_unknown_size_warns(self) -> None:
        preview = build_preview(
            restore_kind="full",
            source_ref="archive-1",
            target_ref="scratch-env",
            source_ref_equals_original=False,
            estimated_size_bytes=None,
        )
        assert preview.estimated_size_bytes is None
        assert any("could not be estimated" in w for w in preview.warnings)

    def test_known_size_no_size_warning(self) -> None:
        preview = build_preview(
            restore_kind="full",
            source_ref="archive-1",
            target_ref="scratch-env",
            source_ref_equals_original=False,
            estimated_size_bytes=2048,
        )
        assert not any("could not be estimated" in w for w in preview.warnings)

    def test_both_warnings_present_when_applicable(self) -> None:
        preview = build_preview(
            restore_kind="full",
            source_ref="archive-1",
            target_ref="target-1",
            source_ref_equals_original=True,
            estimated_size_bytes=None,
        )
        assert len(preview.warnings) == 2
