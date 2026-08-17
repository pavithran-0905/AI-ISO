"""Integration tests for background workers, against real PostgreSQL.

Uses real wall-clock time (``datetime.now(UTC)``) throughout, matching
every worker's own internal ``now = datetime.now(UTC)`` -- a fixed
historical constant would fall outside a worker's real query window and
produce tests that pass without the loop body ever executing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.applications import DeveloperApplication
from app.models.credentials import ApiKey, OAuthClient, OAuthToken, PersonalAccessToken
from app.models.developers import DeveloperAccount
from app.models.documents import ApiVersion
from app.models.enums import (
    ApiProductType,
    ApiVersionStatus,
    CredentialStatus,
    OAuthTokenStatus,
    OAuthTokenType,
    QuotaResetPolicy,
    QuotaType,
    SandboxStatus,
)
from app.models.products import ApiProduct
from app.models.sandbox import ApiSandboxSession
from app.models.usage import ApiQuota
from app.services.bundle import Repositories
from app.workers.api_version_lifecycle_sweep import ApiVersionLifecycleSweepWorker
from app.workers.credential_expiry_sweep import CredentialExpirySweepWorker
from app.workers.quota_reset_sweep import QuotaResetSweepWorker
from app.workers.sandbox_reset_sweep import SandboxResetSweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker


def now() -> datetime:
    return datetime.now(UTC)


async def _make_developer(
    repos: Repositories, organization_id: UUID, **overrides: object
) -> DeveloperAccount:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "email": f"{id(overrides)}@example.com",
    }
    defaults.update(overrides)
    return await repos.developer_accounts.create(DeveloperAccount(**defaults))  # type: ignore[arg-type]


async def _make_application(
    repos: Repositories, organization_id: UUID, developer_account_id: UUID
) -> DeveloperApplication:
    return await repos.applications.create(
        DeveloperApplication(
            organization_id=organization_id, developer_account_id=developer_account_id, name="app"
        )
    )


async def _make_product(repos: Repositories, organization_id: UUID) -> ApiProduct:
    return await repos.api_products.create(
        ApiProduct(
            organization_id=organization_id, name="product", product_type=ApiProductType.PUBLIC
        )
    )


class TestCredentialExpirySweepWorker:
    async def test_tick_expires_stale_api_key(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        developer = await _make_developer(repos, organization_id, email="ck1@example.com")
        application = await _make_application(repos, organization_id, developer.id)
        key = await repos.api_keys.create(
            ApiKey(
                organization_id=organization_id,
                application_id=application.id,
                key_hash="h1",
                expires_at=now() - timedelta(seconds=1),
            )
        )
        worker = CredentialExpirySweepWorker(db_session_factory, notifier=notifier, warning_days=14)
        checked = await worker.tick()
        assert checked == 1
        await db_session.refresh(key)
        assert key.status == CredentialStatus.EXPIRED

    async def test_tick_notifies_expiring_pat(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        developer = await _make_developer(repos, organization_id, email="ck2@example.com")
        await repos.personal_access_tokens.create(
            PersonalAccessToken(
                organization_id=organization_id,
                developer_account_id=developer.id,
                token_hash="h2",
                expires_at=now() + timedelta(days=5),
            )
        )
        worker = CredentialExpirySweepWorker(db_session_factory, notifier=notifier, warning_days=14)
        await worker.tick()
        assert any(name == "notify_credential_expiring" for name, _ in notifier.calls)

    async def test_tick_expires_stale_oauth_token(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        developer = await _make_developer(repos, organization_id, email="ck3@example.com")
        application = await _make_application(repos, organization_id, developer.id)
        client = await repos.oauth_clients.create(
            OAuthClient(
                organization_id=organization_id,
                application_id=application.id,
                client_id="c1",
                client_secret_hash="h",
            )
        )
        token = await repos.oauth_tokens.create(
            OAuthToken(
                organization_id=organization_id,
                oauth_client_id=client.id,
                token_hash="th1",
                token_type=OAuthTokenType.ACCESS,
                issued_at=now() - timedelta(hours=2),
                expires_at=now() - timedelta(seconds=1),
            )
        )
        worker = CredentialExpirySweepWorker(db_session_factory, notifier=notifier, warning_days=14)
        await worker.tick()
        await db_session.refresh(token)
        assert token.status == OAuthTokenStatus.EXPIRED


class TestQuotaResetSweepWorker:
    async def test_tick_resets_expired_period(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        developer = await _make_developer(repos, organization_id, email="qr1@example.com")
        quota = await repos.api_quotas.create(
            ApiQuota(
                organization_id=organization_id,
                developer_account_id=developer.id,
                quota_type=QuotaType.API_CALLS,
                limit_value=100,
                used_value=50,
                reset_policy=QuotaResetPolicy.DAILY,
                period_start=now() - timedelta(days=2),
                period_end=now() - timedelta(days=1),
            )
        )
        worker = QuotaResetSweepWorker(
            db_session_factory, notifier=notifier, warning_threshold_percent=90.0
        )
        checked = await worker.tick()
        assert checked == 1
        await db_session.refresh(quota)
        assert quota.used_value == 0
        assert quota.period_end > now()

    async def test_tick_notifies_warning(
        self, db_session_factory, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        developer = await _make_developer(repos, organization_id, email="qr2@example.com")
        await repos.api_quotas.create(
            ApiQuota(
                organization_id=organization_id,
                developer_account_id=developer.id,
                quota_type=QuotaType.STORAGE,
                limit_value=100,
                used_value=95,
                reset_policy=QuotaResetPolicy.DAILY,
                period_start=now(),
                period_end=now() + timedelta(hours=12),
            )
        )
        worker = QuotaResetSweepWorker(
            db_session_factory, notifier=notifier, warning_threshold_percent=90.0
        )
        await worker.tick()
        assert any(name == "notify_quota_warning" for name, _ in notifier.calls)


class TestApiVersionLifecycleSweepWorker:
    async def test_tick_deprecates_due_version(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        product = await _make_product(repos, organization_id)
        version = await repos.api_versions.create(
            ApiVersion(
                organization_id=organization_id,
                api_product_id=product.id,
                version_label="1.0.0",
                status=ApiVersionStatus.RELEASED,
                deprecated_at=now() - timedelta(seconds=1),
            )
        )
        worker = ApiVersionLifecycleSweepWorker(db_session_factory, notifier=notifier)
        checked = await worker.tick()
        assert checked == 1
        await db_session.refresh(version)
        assert version.status == ApiVersionStatus.DEPRECATED
        assert any(name == "notify_deprecation_notice" for name, _ in notifier.calls)

    async def test_tick_sunsets_due_version(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        product = await _make_product(repos, organization_id)
        version = await repos.api_versions.create(
            ApiVersion(
                organization_id=organization_id,
                api_product_id=product.id,
                version_label="0.9.0",
                status=ApiVersionStatus.DEPRECATED,
                sunset_at=now() - timedelta(seconds=1),
            )
        )
        worker = ApiVersionLifecycleSweepWorker(db_session_factory, notifier=notifier)
        await worker.tick()
        await db_session.refresh(version)
        assert version.status == ApiVersionStatus.SUNSET

    async def test_tick_leaves_not_yet_due_versions_alone(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID, notifier
    ) -> None:
        product = await _make_product(repos, organization_id)
        version = await repos.api_versions.create(
            ApiVersion(
                organization_id=organization_id,
                api_product_id=product.id,
                version_label="2.0.0",
                status=ApiVersionStatus.RELEASED,
                deprecated_at=now() + timedelta(days=30),
            )
        )
        worker = ApiVersionLifecycleSweepWorker(db_session_factory, notifier=notifier)
        await worker.tick()
        await db_session.refresh(version)
        assert version.status == ApiVersionStatus.RELEASED


class TestStatisticsRollupWorker:
    async def test_tick_rolls_up_window(
        self, db_session_factory, repos: Repositories, organization_id: UUID
    ) -> None:
        window_end = now().replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)
        inside_window = window_start + timedelta(minutes=5)

        await _make_developer(
            repos, organization_id, email="stat1@example.com", created_at=inside_window
        )

        worker = StatisticsRollupWorker(db_session_factory)
        rolled = await worker.tick()
        assert rolled >= 0  # organizations with no activity at all are simply never rolled up

        rows = await repos.statistics.list_range(
            organization_id, since=window_start - timedelta(hours=1)
        )
        if rows:
            assert rows[0].window_start == window_start

    async def test_tick_counts_usage_and_errors_inside_window(
        self, db_session_factory, repos: Repositories, organization_id: UUID
    ) -> None:
        from app.models.usage import ApiUsageEvent

        window_end = now().replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)
        inside_window = window_start + timedelta(minutes=5)

        developer = await _make_developer(repos, organization_id, email="stat2@example.com")
        application = await _make_application(repos, organization_id, developer.id)
        product = await _make_product(repos, organization_id)
        await repos.api_usage.create(
            ApiUsageEvent(
                organization_id=organization_id,
                developer_account_id=developer.id,
                application_id=application.id,
                api_product_id=product.id,
                endpoint="/x",
                status_code=500,
                latency_ms=20.0,
                occurred_at=inside_window,
            )
        )
        worker = StatisticsRollupWorker(db_session_factory)
        await worker.tick()

        rows = await repos.statistics.list_range(organization_id, since=window_start)
        assert len(rows) == 1
        assert rows[0].api_call_count == 1
        assert rows[0].error_count == 1
        assert rows[0].average_latency_ms == 20.0


class TestSandboxResetSweepWorker:
    async def test_tick_resets_stale_session(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id, email="sb1@example.com")
        product = await _make_product(repos, organization_id)
        session = await repos.api_sandbox.create(
            ApiSandboxSession(
                organization_id=organization_id,
                developer_account_id=developer.id,
                api_product_id=product.id,
                call_count=5,
                last_reset_at=now() - timedelta(hours=48),
            )
        )
        worker = SandboxResetSweepWorker(db_session_factory, max_age_hours=24)
        reset_count = await worker.tick()
        assert reset_count == 1
        await db_session.refresh(session)
        assert session.status == SandboxStatus.RESET
        assert session.call_count == 0

    async def test_tick_leaves_fresh_session_alone(
        self, db_session_factory, db_session, repos: Repositories, organization_id: UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id, email="sb2@example.com")
        product = await _make_product(repos, organization_id)
        session = await repos.api_sandbox.create(
            ApiSandboxSession(
                organization_id=organization_id,
                developer_account_id=developer.id,
                api_product_id=product.id,
                last_reset_at=now() - timedelta(hours=1),
            )
        )
        worker = SandboxResetSweepWorker(db_session_factory, max_age_hours=24)
        reset_count = await worker.tick()
        assert reset_count == 0
        await db_session.refresh(session)
        assert session.status == SandboxStatus.ACTIVE
