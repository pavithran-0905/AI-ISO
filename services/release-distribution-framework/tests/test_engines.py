"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import build_success_rate, promotion_success_rate, release_health_score
from app.distribution.engine import is_air_gapped, requires_region
from app.download.engine import downloads_per_day
from app.eol.engine import is_eol_approaching, is_past_eol
from app.lts.engine import is_support_expired, is_support_expiring_soon
from app.models.enums import (
    BuildStatus,
    ChecksumAlgorithm,
    DistributionType,
    ReleaseChannelType,
    ReleaseNoteType,
    ReleaseStatus,
)
from app.notes.engine import is_breaking_note, is_security_note
from app.promotion.engine import is_valid_promotion
from app.release.engine import TransitionRefusal as ReleaseTransitionRefusal
from app.release.engine import next_status_toward
from app.release.engine import validate_transition as validate_release_transition
from app.release_build.engine import TransitionRefusal as BuildTransitionRefusal
from app.release_build.engine import is_job_stuck
from app.release_build.engine import validate_transition as validate_build_transition
from app.signing.engine import compute_checksum, verify_checksum

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


class TestReleaseEngine:
    def test_draft_to_validated_allowed(self) -> None:
        assert validate_release_transition(ReleaseStatus.DRAFT, ReleaseStatus.VALIDATED).is_allowed

    def test_archived_is_terminal(self) -> None:
        result = validate_release_transition(ReleaseStatus.ARCHIVED, ReleaseStatus.PUBLISHED)
        assert not result.is_allowed
        assert result.refusal == ReleaseTransitionRefusal.TERMINAL_STATE

    def test_draft_cannot_skip_to_published(self) -> None:
        result = validate_release_transition(ReleaseStatus.DRAFT, ReleaseStatus.PUBLISHED)
        assert not result.is_allowed
        assert result.refusal == ReleaseTransitionRefusal.INVALID_TRANSITION

    def test_next_status_toward_walks_one_step(self) -> None:
        assert (
            next_status_toward(ReleaseStatus.DRAFT, ReleaseStatus.PUBLISHED)
            == ReleaseStatus.VALIDATED
        )

    def test_next_status_toward_same_status(self) -> None:
        assert next_status_toward(ReleaseStatus.DRAFT, ReleaseStatus.DRAFT) is None

    def test_next_status_toward_backwards(self) -> None:
        assert next_status_toward(ReleaseStatus.PUBLISHED, ReleaseStatus.DRAFT) is None


class TestBuildEngine:
    def test_pending_to_running_allowed(self) -> None:
        assert validate_build_transition(BuildStatus.PENDING, BuildStatus.RUNNING).is_allowed

    def test_succeeded_is_terminal(self) -> None:
        result = validate_build_transition(BuildStatus.SUCCEEDED, BuildStatus.RUNNING)
        assert not result.is_allowed
        assert result.refusal == BuildTransitionRefusal.TERMINAL_STATE

    def test_job_stuck_past_max_age(self) -> None:
        assert is_job_stuck(
            BuildStatus.RUNNING, started_at=NOW - timedelta(hours=5), now=NOW, max_age_hours=4
        )

    def test_job_not_stuck_within_max_age(self) -> None:
        assert not is_job_stuck(
            BuildStatus.RUNNING, started_at=NOW - timedelta(hours=1), now=NOW, max_age_hours=4
        )


class TestSigningEngine:
    def test_checksum_is_hex(self) -> None:
        checksum = compute_checksum(b"hello world", algorithm=ChecksumAlgorithm.SHA256)
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_checksum_deterministic(self) -> None:
        assert compute_checksum(b"hello world") == compute_checksum(b"hello world")

    def test_verify_checksum_match_case_insensitive(self) -> None:
        checksum = compute_checksum(b"hello world")
        assert verify_checksum(expected=checksum, actual=checksum.upper())

    def test_verify_checksum_mismatch(self) -> None:
        checksum = compute_checksum(b"hello world")
        assert not verify_checksum(expected=checksum, actual="deadbeef")


class TestPromotionEngine:
    def test_canary_to_stable_valid(self) -> None:
        assert is_valid_promotion(
            from_channel=ReleaseChannelType.CANARY, to_channel=ReleaseChannelType.STABLE
        )

    def test_stable_to_lts_valid(self) -> None:
        assert is_valid_promotion(
            from_channel=ReleaseChannelType.STABLE, to_channel=ReleaseChannelType.LTS
        )

    def test_development_to_beta_invalid(self) -> None:
        assert not is_valid_promotion(
            from_channel=ReleaseChannelType.DEVELOPMENT, to_channel=ReleaseChannelType.BETA
        )

    def test_lts_has_no_further_promotion(self) -> None:
        assert not is_valid_promotion(
            from_channel=ReleaseChannelType.LTS, to_channel=ReleaseChannelType.STABLE
        )


class TestDistributionEngine:
    def test_air_gapped_type_is_air_gapped(self) -> None:
        assert is_air_gapped(DistributionType.AIR_GAPPED)

    def test_offline_export_type_is_air_gapped(self) -> None:
        assert is_air_gapped(DistributionType.OFFLINE_EXPORT)

    def test_global_type_not_air_gapped(self) -> None:
        assert not is_air_gapped(DistributionType.GLOBAL)

    def test_regional_requires_region(self) -> None:
        assert requires_region(DistributionType.REGIONAL)

    def test_oem_does_not_require_region(self) -> None:
        assert not requires_region(DistributionType.OEM)


class TestLtsEngine:
    def test_support_expiring_soon(self) -> None:
        assert is_support_expiring_soon(
            support_ends_at=NOW + timedelta(days=10), now=NOW, warning_days=30
        )

    def test_support_not_expiring_soon(self) -> None:
        assert not is_support_expiring_soon(
            support_ends_at=NOW + timedelta(days=60), now=NOW, warning_days=30
        )

    def test_support_expired(self) -> None:
        assert is_support_expired(support_ends_at=NOW - timedelta(days=1), now=NOW)

    def test_support_not_expired(self) -> None:
        assert not is_support_expired(support_ends_at=NOW + timedelta(days=1), now=NOW)


class TestEolEngine:
    def test_eol_approaching(self) -> None:
        assert is_eol_approaching(eol_date=NOW + timedelta(days=10), now=NOW, warning_days=30)

    def test_eol_not_approaching(self) -> None:
        assert not is_eol_approaching(eol_date=NOW + timedelta(days=60), now=NOW, warning_days=30)

    def test_past_eol(self) -> None:
        assert is_past_eol(eol_date=NOW - timedelta(days=1), now=NOW)

    def test_not_past_eol(self) -> None:
        assert not is_past_eol(eol_date=NOW + timedelta(days=1), now=NOW)


class TestDownloadEngine:
    def test_downloads_per_day_basic(self) -> None:
        assert downloads_per_day(download_count=240, window_hours=24.0) == 240.0

    def test_downloads_per_day_zero_window_honest_zero(self) -> None:
        assert downloads_per_day(download_count=10, window_hours=0.0) == 0.0


class TestNotesEngine:
    def test_security_fix_is_security_note(self) -> None:
        assert is_security_note(ReleaseNoteType.SECURITY_FIX)

    def test_feature_is_not_security_note(self) -> None:
        assert not is_security_note(ReleaseNoteType.FEATURE)

    def test_breaking_change_is_breaking_note(self) -> None:
        assert is_breaking_note(ReleaseNoteType.BREAKING_CHANGE)

    def test_bug_fix_is_not_breaking_note(self) -> None:
        assert not is_breaking_note(ReleaseNoteType.BUG_FIX)


class TestAnalyticsEngine:
    def test_build_success_rate_basic(self) -> None:
        assert build_success_rate(8, 10) == pytest.approx(0.8)

    def test_build_success_rate_honest_zero(self) -> None:
        assert build_success_rate(0, 0) == 0.0

    def test_promotion_success_rate_basic(self) -> None:
        assert promotion_success_rate(9, 10) == pytest.approx(0.9)

    def test_promotion_success_rate_vacuous(self) -> None:
        assert promotion_success_rate(0, 0) == 1.0

    def test_release_health_score_average(self) -> None:
        score = release_health_score(build_success_rate_value=0.8, promotion_success_rate_value=1.0)
        assert score == pytest.approx(0.9)
