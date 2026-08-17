"""Unit tests for every pure engine module -- the same checks the
hand-verification script already ran, formalized as pytest so they
gate CI, plus edge cases the script didn't cover."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.engine import average_latency_ms, error_rate, growth_rate
from app.api_keys.engine import TransitionRefusal as CredentialTransitionRefusal
from app.api_keys.engine import is_expired as cred_is_expired
from app.api_keys.engine import is_expiring_soon as cred_is_expiring_soon
from app.api_keys.engine import validate_transition as validate_cred_transition
from app.applications.engine import TransitionRefusal as AppTransitionRefusal
from app.applications.engine import validate_transition as validate_app_transition
from app.developers.engine import TransitionRefusal as DevTransitionRefusal
from app.developers.engine import is_eligible_for_activation
from app.developers.engine import validate_transition as validate_dev_transition
from app.models.enums import (
    ApiProductStatus,
    ApiVersionStatus,
    ApplicationStatus,
    CredentialStatus,
    DeveloperAccountStatus,
    MockType,
    QuotaResetPolicy,
)
from app.oauth.engine import (
    compute_pkce_challenge,
    is_grant_type_allowed,
    is_token_expired,
    verify_pkce,
)
from app.products.engine import TransitionRefusal as ProductTransitionRefusal
from app.products.engine import validate_transition as validate_product_transition
from app.quotas.engine import compute_period_window, is_quota_exceeded, is_quota_warning
from app.rate_limits.engine import is_rate_limited, is_within_burst, remaining_capacity
from app.sandbox.engine import is_sandbox_session_stale, resolve_mock_response
from app.versioning.engine import TransitionRefusal as VersionTransitionRefusal
from app.versioning.engine import (
    is_breaking_change,
    is_deprecation_due,
    is_sunset_due,
    parse_version,
)
from app.versioning.engine import validate_transition as validate_version_transition

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)


class TestDevelopersEngine:
    def test_pending_to_active(self) -> None:
        assert validate_dev_transition(
            DeveloperAccountStatus.PENDING_VERIFICATION, DeveloperAccountStatus.ACTIVE
        ).is_allowed

    def test_active_to_suspended(self) -> None:
        assert validate_dev_transition(
            DeveloperAccountStatus.ACTIVE, DeveloperAccountStatus.SUSPENDED
        ).is_allowed

    def test_suspended_reinstated(self) -> None:
        assert validate_dev_transition(
            DeveloperAccountStatus.SUSPENDED, DeveloperAccountStatus.ACTIVE
        ).is_allowed

    def test_active_to_pending_refused(self) -> None:
        result = validate_dev_transition(
            DeveloperAccountStatus.ACTIVE, DeveloperAccountStatus.PENDING_VERIFICATION
        )
        assert not result.is_allowed
        assert result.refusal == DevTransitionRefusal.INVALID_TRANSITION

    def test_coerces_plain_strings(self) -> None:
        assert validate_dev_transition("pending_verification", "active").is_allowed  # type: ignore[arg-type]

    def test_activation_requires_verified_email(self) -> None:
        assert not is_eligible_for_activation(None)

    def test_activation_eligible_once_verified(self) -> None:
        assert is_eligible_for_activation(NOW)


class TestApplicationsEngine:
    def test_pending_to_active(self) -> None:
        assert validate_app_transition(
            ApplicationStatus.PENDING, ApplicationStatus.ACTIVE
        ).is_allowed

    def test_revoked_terminal(self) -> None:
        result = validate_app_transition(ApplicationStatus.REVOKED, ApplicationStatus.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == AppTransitionRefusal.TERMINAL_STATE

    def test_suspended_to_active(self) -> None:
        assert validate_app_transition(
            ApplicationStatus.SUSPENDED, ApplicationStatus.ACTIVE
        ).is_allowed


class TestOAuthEngine:
    def test_pkce_round_trip(self) -> None:
        verifier = "a" * 43
        challenge = compute_pkce_challenge(verifier)
        assert verify_pkce(code_verifier=verifier, code_challenge=challenge)

    def test_pkce_rejects_wrong_verifier(self) -> None:
        challenge = compute_pkce_challenge("a" * 43)
        assert not verify_pkce(code_verifier="b" * 43, code_challenge=challenge)

    def test_token_expiry(self) -> None:
        assert not is_token_expired(expires_at=NOW + timedelta(hours=1), now=NOW)
        assert is_token_expired(expires_at=NOW - timedelta(seconds=1), now=NOW)

    def test_grant_type_allowed(self) -> None:
        assert is_grant_type_allowed("client_credentials", ["client_credentials"])
        assert not is_grant_type_allowed("device_code", ["client_credentials"])


class TestApiKeysEngine:
    def test_active_to_rotated(self) -> None:
        assert validate_cred_transition(
            CredentialStatus.ACTIVE, CredentialStatus.ROTATED
        ).is_allowed

    def test_revoked_terminal(self) -> None:
        result = validate_cred_transition(CredentialStatus.REVOKED, CredentialStatus.ACTIVE)
        assert not result.is_allowed
        assert result.refusal == CredentialTransitionRefusal.TERMINAL_STATE

    def test_rotated_to_revoked(self) -> None:
        assert validate_cred_transition(
            CredentialStatus.ROTATED, CredentialStatus.REVOKED
        ).is_allowed

    def test_expiry(self) -> None:
        assert not cred_is_expired(expires_at=NOW + timedelta(days=1), now=NOW)
        assert cred_is_expired(expires_at=NOW - timedelta(seconds=1), now=NOW)

    def test_expiring_soon(self) -> None:
        assert cred_is_expiring_soon(expires_at=NOW + timedelta(days=5), now=NOW, warning_days=14)
        assert not cred_is_expiring_soon(
            expires_at=NOW + timedelta(days=30), now=NOW, warning_days=14
        )

    def test_already_expired_not_expiring_soon(self) -> None:
        assert not cred_is_expiring_soon(
            expires_at=NOW - timedelta(days=1), now=NOW, warning_days=14
        )


class TestProductsEngine:
    def test_draft_to_pending_approval(self) -> None:
        assert validate_product_transition(
            ApiProductStatus.DRAFT, ApiProductStatus.PENDING_APPROVAL
        ).is_allowed

    def test_rejection_path(self) -> None:
        assert validate_product_transition(
            ApiProductStatus.PENDING_APPROVAL, ApiProductStatus.DRAFT
        ).is_allowed

    def test_deprecated_terminal(self) -> None:
        result = validate_product_transition(ApiProductStatus.DEPRECATED, ApiProductStatus.APPROVED)
        assert not result.is_allowed
        assert result.refusal == ProductTransitionRefusal.TERMINAL_STATE


class TestVersioningEngine:
    def test_parse_version(self) -> None:
        assert parse_version("1.2.3").major == 1

    def test_parse_version_rejects_two_part(self) -> None:
        with pytest.raises(ValueError, match=r"MAJOR\.MINOR\.PATCH"):
            parse_version("1.2")

    def test_parse_version_rejects_garbage(self) -> None:
        with pytest.raises(ValueError, match=r"MAJOR\.MINOR\.PATCH"):
            parse_version("1.2.a")

    def test_parse_version_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="negative version part"):
            parse_version("-1.2.3")

    def test_numeric_not_lexical_comparison(self) -> None:
        assert parse_version("9.0.0") < parse_version("10.0.0")

    def test_major_bump_is_breaking(self) -> None:
        assert is_breaking_change("1.5.0", "2.0.0")

    def test_minor_bump_not_breaking(self) -> None:
        assert not is_breaking_change("1.5.0", "1.6.0")

    def test_draft_to_released(self) -> None:
        assert validate_version_transition(
            ApiVersionStatus.DRAFT, ApiVersionStatus.RELEASED
        ).is_allowed

    def test_skip_to_sunset_refused(self) -> None:
        result = validate_version_transition(ApiVersionStatus.RELEASED, ApiVersionStatus.SUNSET)
        assert not result.is_allowed
        assert result.refusal == VersionTransitionRefusal.INVALID_TRANSITION

    def test_sunset_terminal(self) -> None:
        result = validate_version_transition(ApiVersionStatus.SUNSET, ApiVersionStatus.DRAFT)
        assert not result.is_allowed
        assert result.refusal == VersionTransitionRefusal.TERMINAL_STATE

    def test_deprecation_due(self) -> None:
        assert not is_deprecation_due(deprecated_at=None, now=NOW)
        assert is_deprecation_due(deprecated_at=NOW - timedelta(days=1), now=NOW)
        assert not is_deprecation_due(deprecated_at=NOW + timedelta(days=1), now=NOW)

    def test_sunset_due(self) -> None:
        assert not is_sunset_due(sunset_at=None, now=NOW)
        assert is_sunset_due(sunset_at=NOW - timedelta(days=1), now=NOW)


class TestRateLimitsEngine:
    def test_rate_limited_at_threshold(self) -> None:
        assert is_rate_limited(current_count=60, limit=60)

    def test_not_rate_limited_below(self) -> None:
        assert not is_rate_limited(current_count=59, limit=60)

    def test_within_burst(self) -> None:
        assert is_within_burst(concurrent_count=5, burst_limit=10)
        assert not is_within_burst(concurrent_count=11, burst_limit=10)

    def test_remaining_capacity(self) -> None:
        assert remaining_capacity(current_count=40, limit=60) == 20
        assert remaining_capacity(current_count=100, limit=60) == 0


class TestQuotasEngine:
    def test_daily_window(self) -> None:
        start, end = compute_period_window(QuotaResetPolicy.DAILY, now=NOW)
        assert end - start == timedelta(days=1)

    def test_weekly_window(self) -> None:
        start, end = compute_period_window(QuotaResetPolicy.WEEKLY, now=NOW)
        assert end - start == timedelta(days=7)

    def test_monthly_window_handles_january(self) -> None:
        start, end = compute_period_window(
            QuotaResetPolicy.MONTHLY, now=datetime(2026, 1, 31, tzinfo=UTC)
        )
        assert start.month == 1
        assert end.month == 2

    def test_monthly_window_handles_december(self) -> None:
        _start, end = compute_period_window(
            QuotaResetPolicy.MONTHLY, now=datetime(2026, 12, 15, tzinfo=UTC)
        )
        assert end.year == 2027
        assert end.month == 1

    def test_quota_exceeded(self) -> None:
        assert is_quota_exceeded(used_value=100, limit_value=100)
        assert not is_quota_exceeded(used_value=99, limit_value=100)

    def test_quota_warning(self) -> None:
        assert is_quota_warning(used_value=91, limit_value=100, threshold_percent=90.0)
        assert not is_quota_warning(used_value=100, limit_value=100, threshold_percent=90.0)
        assert not is_quota_warning(used_value=0, limit_value=0, threshold_percent=90.0)


class TestSandboxEngine:
    def test_resolve_mock_response(self) -> None:
        outcome = resolve_mock_response(
            mock_type=MockType.STATIC,
            response_body={"ok": True},
            response_status_code=200,
            simulated_latency_ms=10.0,
            simulate_error=False,
        )
        assert outcome.status_code == 200
        assert outcome.body == {"ok": True}

    def test_resolve_mock_response_error_override(self) -> None:
        outcome = resolve_mock_response(
            mock_type=MockType.STATIC,
            response_body={"ok": True},
            response_status_code=200,
            simulated_latency_ms=10.0,
            simulate_error=True,
        )
        assert outcome.status_code == 500

    def test_sandbox_session_stale(self) -> None:
        assert is_sandbox_session_stale(
            last_reset_at=NOW - timedelta(hours=48), now=NOW, max_age_hours=24
        )
        assert not is_sandbox_session_stale(
            last_reset_at=NOW - timedelta(hours=1), now=NOW, max_age_hours=24
        )


class TestAnalyticsEngine:
    def test_error_rate(self) -> None:
        assert error_rate(5, 100) == pytest.approx(0.05)

    def test_error_rate_empty(self) -> None:
        assert error_rate(0, 0) == 0.0

    def test_average_latency(self) -> None:
        assert average_latency_ms([10.0, 20.0, 30.0]) == pytest.approx(20.0)

    def test_average_latency_empty(self) -> None:
        assert average_latency_ms([]) == 0.0

    def test_growth_rate(self) -> None:
        assert growth_rate(100, 150) == pytest.approx(0.5)

    def test_growth_rate_from_zero(self) -> None:
        assert growth_rate(0, 10) == 1.0
        assert growth_rate(0, 0) == 0.0
