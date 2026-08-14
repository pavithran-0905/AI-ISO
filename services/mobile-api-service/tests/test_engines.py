"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import (
    average_session_duration,
    crash_rate,
    distinct_user_count,
    engagement_rate,
    offline_usage_ratio,
    success_rate,
)
from app.authentication.engine import (
    is_offline_authentication_allowed,
    is_session_expired,
    is_session_expiring_soon,
)
from app.configuration.engine import ConfigurationEntry, matches_scope, resolve_configuration
from app.deep_links.engine import build_deep_link, parse_deep_link
from app.devices.engine import TransitionRefusal as DeviceTransitionRefusal
from app.devices.engine import validate_transition as validate_device_transition
from app.models.enums import (
    ConflictResolutionStrategy,
    DeepLinkCategory,
    DeviceTrustStatus,
    MobilePlatform,
    NotificationDeliveryStatus,
    PushTokenStatus,
    SyncJobStatus,
    SyncQueueStatus,
)
from app.push.engine import is_push_token_usable
from app.push.engine import is_retry_eligible as push_retry_eligible
from app.push.engine import validate_transition as validate_push_transition
from app.qr.engine import compute_qr_expiry, generate_qr_token, is_qr_token_expired
from app.security.engine import (
    compute_integrity_risk_score,
    is_device_integrity_acceptable,
    is_replay_attack,
    is_valid_certificate_fingerprint,
)
from app.sync.engine import (
    compute_backoff_seconds,
    detect_conflict,
    resolve_conflict,
    validate_job_transition,
    validate_queue_transition,
)
from app.sync.engine import (
    is_retry_eligible as sync_retry_eligible,
)
from app.versions.engine import (
    compare_versions,
    is_below_minimum,
    is_update_recommended,
    parse_version,
)

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)


class TestAuthenticationEngine:
    def test_not_expired_before_expiry(self) -> None:
        assert not is_session_expired(expires_at=NOW + timedelta(hours=1), now=NOW)

    def test_expired_after_expiry(self) -> None:
        assert is_session_expired(expires_at=NOW - timedelta(seconds=1), now=NOW)

    def test_expired_at_exact_instant(self) -> None:
        assert is_session_expired(expires_at=NOW, now=NOW)

    def test_expiring_soon_inside_window(self) -> None:
        assert is_session_expiring_soon(
            expires_at=NOW + timedelta(minutes=10), now=NOW, warning_minutes=30
        )

    def test_not_expiring_soon_outside_window(self) -> None:
        assert not is_session_expiring_soon(
            expires_at=NOW + timedelta(hours=2), now=NOW, warning_minutes=30
        )

    def test_already_expired_not_expiring_soon(self) -> None:
        assert not is_session_expiring_soon(
            expires_at=NOW - timedelta(minutes=1), now=NOW, warning_minutes=30
        )

    def test_offline_auth_allowed_within_window(self) -> None:
        assert is_offline_authentication_allowed(
            last_seen_at=NOW - timedelta(hours=1), now=NOW, max_offline_hours=24
        )

    def test_offline_auth_denied_outside_window(self) -> None:
        assert not is_offline_authentication_allowed(
            last_seen_at=NOW - timedelta(hours=48), now=NOW, max_offline_hours=24
        )

    def test_offline_auth_denied_never_seen(self) -> None:
        assert not is_offline_authentication_allowed(
            last_seen_at=None, now=NOW, max_offline_hours=24
        )


class TestDevicesEngine:
    def test_pending_to_approved_allowed(self) -> None:
        assert validate_device_transition(
            DeviceTrustStatus.PENDING, DeviceTrustStatus.APPROVED
        ).is_allowed

    def test_pending_to_revoked_allowed(self) -> None:
        assert validate_device_transition(
            DeviceTrustStatus.PENDING, DeviceTrustStatus.REVOKED
        ).is_allowed

    def test_approved_to_revoked_allowed(self) -> None:
        assert validate_device_transition(
            DeviceTrustStatus.APPROVED, DeviceTrustStatus.REVOKED
        ).is_allowed

    def test_revoked_is_terminal(self) -> None:
        result = validate_device_transition(DeviceTrustStatus.REVOKED, DeviceTrustStatus.APPROVED)
        assert not result.is_allowed
        assert result.refusal == DeviceTransitionRefusal.TERMINAL_STATE

    def test_approved_to_pending_refused(self) -> None:
        result = validate_device_transition(DeviceTrustStatus.APPROVED, DeviceTrustStatus.PENDING)
        assert not result.is_allowed
        assert result.refusal == DeviceTransitionRefusal.INVALID_TRANSITION

    def test_coerces_plain_strings(self) -> None:
        assert validate_device_transition("pending", "approved").is_allowed  # type: ignore[arg-type]


class TestSyncEngine:
    def test_job_pending_to_running(self) -> None:
        assert validate_job_transition(SyncJobStatus.PENDING, SyncJobStatus.RUNNING).is_allowed

    def test_job_running_to_completed(self) -> None:
        assert validate_job_transition(SyncJobStatus.RUNNING, SyncJobStatus.COMPLETED).is_allowed

    def test_job_completed_terminal(self) -> None:
        assert not validate_job_transition(
            SyncJobStatus.COMPLETED, SyncJobStatus.RUNNING
        ).is_allowed

    def test_job_failed_terminal(self) -> None:
        assert not validate_job_transition(SyncJobStatus.FAILED, SyncJobStatus.RUNNING).is_allowed

    def test_queue_queued_to_processing(self) -> None:
        assert validate_queue_transition(
            SyncQueueStatus.QUEUED, SyncQueueStatus.PROCESSING
        ).is_allowed

    def test_queue_failed_to_queued_retry(self) -> None:
        assert validate_queue_transition(SyncQueueStatus.FAILED, SyncQueueStatus.QUEUED).is_allowed

    def test_queue_applied_terminal(self) -> None:
        assert not validate_queue_transition(
            SyncQueueStatus.APPLIED, SyncQueueStatus.QUEUED
        ).is_allowed

    def test_queue_conflict_to_applied(self) -> None:
        assert validate_queue_transition(
            SyncQueueStatus.CONFLICT, SyncQueueStatus.APPLIED
        ).is_allowed

    def test_conflict_detected_when_server_newer(self) -> None:
        assert detect_conflict(client_updated_at=NOW - timedelta(hours=1), server_updated_at=NOW)

    def test_no_conflict_no_server_state(self) -> None:
        assert not detect_conflict(client_updated_at=NOW, server_updated_at=None)

    def test_no_conflict_client_newer(self) -> None:
        assert not detect_conflict(
            client_updated_at=NOW, server_updated_at=NOW - timedelta(hours=1)
        )

    def test_server_wins_strategy(self) -> None:
        assert not resolve_conflict(
            ConflictResolutionStrategy.SERVER_WINS,
            client_updated_at=NOW,
            server_updated_at=NOW - timedelta(hours=1),
        )

    def test_client_wins_strategy(self) -> None:
        assert resolve_conflict(
            ConflictResolutionStrategy.CLIENT_WINS,
            client_updated_at=NOW - timedelta(hours=1),
            server_updated_at=NOW,
        )

    def test_manual_strategy_is_recency_based(self) -> None:
        assert resolve_conflict(
            ConflictResolutionStrategy.MANUAL,
            client_updated_at=NOW,
            server_updated_at=NOW - timedelta(hours=1),
        )
        assert not resolve_conflict(
            ConflictResolutionStrategy.MANUAL,
            client_updated_at=NOW - timedelta(hours=1),
            server_updated_at=NOW,
        )

    def test_retry_eligible_below_max(self) -> None:
        assert sync_retry_eligible(retry_count=2, max_retry_count=5)

    def test_retry_not_eligible_at_max(self) -> None:
        assert not sync_retry_eligible(retry_count=5, max_retry_count=5)

    def test_backoff_grows_exponentially(self) -> None:
        assert compute_backoff_seconds(retry_count=0, base_seconds=30) == 30
        assert compute_backoff_seconds(retry_count=3, base_seconds=30) == 240


class TestPushEngine:
    def test_pending_to_delivered(self) -> None:
        assert validate_push_transition(
            NotificationDeliveryStatus.PENDING, NotificationDeliveryStatus.DELIVERED
        ).is_allowed

    def test_pending_to_failed(self) -> None:
        assert validate_push_transition(
            NotificationDeliveryStatus.PENDING, NotificationDeliveryStatus.FAILED
        ).is_allowed

    def test_failed_to_pending_retry(self) -> None:
        assert validate_push_transition(
            NotificationDeliveryStatus.FAILED, NotificationDeliveryStatus.PENDING
        ).is_allowed

    def test_delivered_to_read(self) -> None:
        assert validate_push_transition(
            NotificationDeliveryStatus.DELIVERED, NotificationDeliveryStatus.READ
        ).is_allowed

    def test_read_terminal(self) -> None:
        assert not validate_push_transition(
            NotificationDeliveryStatus.READ, NotificationDeliveryStatus.PENDING
        ).is_allowed

    def test_retry_eligible(self) -> None:
        assert push_retry_eligible(retry_count=1, max_retry_count=5)
        assert not push_retry_eligible(retry_count=5, max_retry_count=5)

    def test_token_usable_active(self) -> None:
        assert is_push_token_usable(PushTokenStatus.ACTIVE)
        assert is_push_token_usable("active")  # type: ignore[arg-type]

    def test_token_not_usable_revoked(self) -> None:
        assert not is_push_token_usable(PushTokenStatus.REVOKED)
        assert not is_push_token_usable("invalid")  # type: ignore[arg-type]


class TestVersionsEngine:
    def test_parse_version(self) -> None:
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_parse_version_single_part(self) -> None:
        assert parse_version("5") == (5,)

    def test_parse_version_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="not a valid dotted version"):
            parse_version("")

    def test_parse_version_rejects_garbage(self) -> None:
        with pytest.raises(ValueError, match="not a valid dotted version"):
            parse_version("abc")

    def test_parse_version_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="negative version part"):
            parse_version("-1.2.3")

    def test_numeric_not_lexical_comparison(self) -> None:
        assert compare_versions("9.0.0", "10.0.0") == -1

    def test_compare_equal(self) -> None:
        assert compare_versions("1.5.0", "1.5.0") == 0

    def test_compare_greater(self) -> None:
        assert compare_versions("2.0.0", "1.9.9") == 1

    def test_compare_differing_part_counts(self) -> None:
        assert compare_versions("1.2", "1.2.0") == 0
        assert compare_versions("1.2.1", "1.2") == 1

    def test_is_below_minimum(self) -> None:
        assert is_below_minimum("1.0.0", "1.5.0")
        assert not is_below_minimum("1.5.0", "1.5.0")

    def test_is_update_recommended(self) -> None:
        assert is_update_recommended("2.0.0", "2.1.0")
        assert not is_update_recommended("2.1.0", "2.1.0")


class TestConfigurationEngine:
    def test_matches_scope_disabled_excluded(self) -> None:
        entry = ConfigurationEntry(
            key="k", value={}, environment="production", platform=None, is_enabled=False
        )
        assert not matches_scope(entry, platform=MobilePlatform.ANDROID, environment="production")

    def test_matches_scope_wrong_environment_excluded(self) -> None:
        entry = ConfigurationEntry(
            key="k", value={}, environment="staging", platform=None, is_enabled=True
        )
        assert not matches_scope(entry, platform=MobilePlatform.ANDROID, environment="production")

    def test_matches_scope_global_matches_any_platform(self) -> None:
        entry = ConfigurationEntry(
            key="k", value={}, environment="production", platform=None, is_enabled=True
        )
        assert matches_scope(entry, platform=MobilePlatform.IOS, environment="production")

    def test_matches_scope_platform_specific_only_matches_that_platform(self) -> None:
        entry = ConfigurationEntry(
            key="k",
            value={},
            environment="production",
            platform=MobilePlatform.IOS,
            is_enabled=True,
        )
        assert matches_scope(entry, platform=MobilePlatform.IOS, environment="production")
        assert not matches_scope(entry, platform=MobilePlatform.ANDROID, environment="production")

    def test_resolve_platform_override_wins(self) -> None:
        entries = [
            ConfigurationEntry(
                key="x", value={"v": 1}, environment="production", platform=None, is_enabled=True
            ),
            ConfigurationEntry(
                key="x",
                value={"v": 2},
                environment="production",
                platform=MobilePlatform.IOS,
                is_enabled=True,
            ),
        ]
        resolved = resolve_configuration(
            entries, platform=MobilePlatform.IOS, environment="production"
        )
        assert resolved["x"] == {"v": 2}

    def test_resolve_platform_override_independent_of_order(self) -> None:
        entries = [
            ConfigurationEntry(
                key="x",
                value={"v": 2},
                environment="production",
                platform=MobilePlatform.IOS,
                is_enabled=True,
            ),
            ConfigurationEntry(
                key="x", value={"v": 1}, environment="production", platform=None, is_enabled=True
            ),
        ]
        resolved = resolve_configuration(
            entries, platform=MobilePlatform.IOS, environment="production"
        )
        assert resolved["x"] == {"v": 2}


class TestDeepLinksEngine:
    BASE_URL = "https://m.aiios.example"

    def test_build_and_parse_round_trip(self) -> None:
        link = build_deep_link(
            DeepLinkCategory.APPROVAL, resource_id="abc123", base_url=self.BASE_URL
        )
        assert link == f"{self.BASE_URL}/link/approval/abc123"
        category, resource_id = parse_deep_link(link, base_url=self.BASE_URL)
        assert category == DeepLinkCategory.APPROVAL
        assert resource_id == "abc123"

    def test_build_rejects_empty_resource_id(self) -> None:
        with pytest.raises(ValueError, match="not a valid deep-link resource id"):
            build_deep_link(DeepLinkCategory.REPORT, resource_id="", base_url=self.BASE_URL)

    def test_build_rejects_slash_in_resource_id(self) -> None:
        with pytest.raises(ValueError, match="not a valid deep-link resource id"):
            build_deep_link(DeepLinkCategory.REPORT, resource_id="a/b", base_url=self.BASE_URL)

    def test_parse_rejects_wrong_prefix(self) -> None:
        with pytest.raises(ValueError, match="not a recognized deep link"):
            parse_deep_link("https://other.example/link/report/1", base_url=self.BASE_URL)

    def test_parse_rejects_malformed_remainder(self) -> None:
        with pytest.raises(ValueError, match="not a well-formed deep link"):
            parse_deep_link(f"{self.BASE_URL}/link/report", base_url=self.BASE_URL)

    def test_parse_rejects_unknown_category(self) -> None:
        with pytest.raises(ValueError, match="not a recognized deep link category"):
            parse_deep_link(f"{self.BASE_URL}/link/bogus/1", base_url=self.BASE_URL)


class TestQrEngine:
    def test_tokens_are_unique(self) -> None:
        assert generate_qr_token() != generate_qr_token()

    def test_token_reasonably_long(self) -> None:
        assert len(generate_qr_token()) >= 32

    def test_not_expired_within_ttl(self) -> None:
        assert not is_qr_token_expired(
            issued_at=NOW, ttl_minutes=15, now=NOW + timedelta(minutes=5)
        )

    def test_expired_past_ttl(self) -> None:
        assert is_qr_token_expired(issued_at=NOW, ttl_minutes=15, now=NOW + timedelta(minutes=16))

    def test_compute_expiry(self) -> None:
        assert compute_qr_expiry(issued_at=NOW, ttl_minutes=15) == NOW + timedelta(minutes=15)


class TestSecurityEngine:
    def test_pristine_device_zero_risk(self) -> None:
        assert compute_integrity_risk_score(is_jailbroken=False, is_rooted=False) == 0

    def test_jailbroken_scores_risk(self) -> None:
        assert compute_integrity_risk_score(is_jailbroken=True, is_rooted=False) == 60

    def test_rooted_scores_risk(self) -> None:
        assert compute_integrity_risk_score(is_jailbroken=False, is_rooted=True) == 60

    def test_score_capped_at_max(self) -> None:
        assert (
            compute_integrity_risk_score(
                is_jailbroken=True, is_rooted=True, certificate_valid=False
            )
            == 100
        )

    def test_pristine_acceptable(self) -> None:
        assert is_device_integrity_acceptable(0)

    def test_high_risk_not_acceptable(self) -> None:
        assert not is_device_integrity_acceptable(90)

    def test_at_threshold_not_acceptable(self) -> None:
        assert not is_device_integrity_acceptable(50, threshold=50)

    def test_valid_fingerprint(self) -> None:
        assert is_valid_certificate_fingerprint("a" * 64)

    def test_wrong_length_fingerprint(self) -> None:
        assert not is_valid_certificate_fingerprint("a" * 63)

    def test_non_hex_fingerprint(self) -> None:
        assert not is_valid_certificate_fingerprint("z" * 64)

    def test_replay_seen_nonce_always_rejected(self) -> None:
        assert is_replay_attack(
            request_timestamp=NOW, now=NOW, max_skew_seconds=60, nonce_already_seen=True
        )

    def test_replay_within_skew_accepted(self) -> None:
        assert not is_replay_attack(
            request_timestamp=NOW,
            now=NOW + timedelta(seconds=30),
            max_skew_seconds=60,
            nonce_already_seen=False,
        )

    def test_replay_outside_skew_rejected(self) -> None:
        assert is_replay_attack(
            request_timestamp=NOW,
            now=NOW + timedelta(seconds=120),
            max_skew_seconds=60,
            nonce_already_seen=False,
        )


class TestAnalyticsEngine:
    def test_success_rate(self) -> None:
        assert success_rate(3, 4) == pytest.approx(0.75)

    def test_success_rate_empty_population(self) -> None:
        assert success_rate(0, 0) == 0.0

    def test_engagement_rate(self) -> None:
        assert engagement_rate(2, 8) == pytest.approx(0.25)

    def test_crash_rate(self) -> None:
        assert crash_rate(1, 100) == pytest.approx(0.01)

    def test_offline_usage_ratio(self) -> None:
        assert offline_usage_ratio(5, 20) == pytest.approx(0.25)

    def test_average_session_duration(self) -> None:
        assert average_session_duration([10.0, 20.0, 30.0]) == pytest.approx(20.0)

    def test_average_session_duration_empty(self) -> None:
        assert average_session_duration([]) == 0.0

    def test_distinct_user_count(self) -> None:
        assert distinct_user_count(["a", "b", "a", "c"]) == 3

    def test_distinct_user_count_empty(self) -> None:
        assert distinct_user_count([]) == 0
