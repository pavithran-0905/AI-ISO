"""Integration tests for every service class, against real PostgreSQL."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import (
    ApiProductStatus,
    ApiProductType,
    ApiVersionStatus,
    ApplicationStatus,
    DeveloperAccountStatus,
    DeveloperAuditAction,
    MockType,
    QuotaResetPolicy,
    QuotaType,
    ReportKind,
)
from app.services.applications import ApplicationService
from app.services.applications import TransitionRefusedError as AppTransitionRefusedError
from app.services.audit import AuditService
from app.services.bundle import Repositories
from app.services.credentials import ApiKeyService, OAuthClientService, PersonalAccessTokenService
from app.services.credentials import TransitionRefusedError as CredentialTransitionRefusedError
from app.services.developers import ActivationNotEligibleError, DeveloperAccountService
from app.services.developers import TransitionRefusedError as DevTransitionRefusedError
from app.services.documents import ApiChangelogService, GraphQlSchemaService, OpenApiDocumentService
from app.services.products import ApiPlanService, ApiProductService, ApiSubscriptionService
from app.services.products import TransitionRefusedError as ProductTransitionRefusedError
from app.services.quotas import QuotaService
from app.services.reports import ReportService
from app.services.sandbox import MockServiceConfig, SandboxService
from app.services.statistics import StatisticsService
from app.services.usage import UsageService
from app.services.versioning import ApiVersionService
from app.services.versioning import TransitionRefusedError as VersionTransitionRefusedError
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, hours_ahead, utcnow

pytestmark = pytest.mark.asyncio


class TestAuditService:
    async def test_record_and_list(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = AuditService(repos.audit)
        await service.record(
            organization_id=organization_id,
            action=DeveloperAuditAction.DEVELOPER_REGISTRATION,
            entity_type="developer_account",
            entity_id=uuid.uuid4(),
            summary="registered",
            occurred_at=utcnow(),
        )
        assert len(await service.list_recent(organization_id)) == 1


class TestDeveloperAccountService:
    async def test_register_publishes_event(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        audit = AuditService(repos.audit)
        service = DeveloperAccountService(repos.developer_accounts, publish=publisher, audit=audit)
        account = await service.register(organization_id, email="a@example.com", now=utcnow())
        assert account.status == DeveloperAccountStatus.PENDING_VERIFICATION
        assert publisher.names() == ["DeveloperRegistered"]
        assert len(await audit.list_recent(organization_id)) == 1

    async def test_activation_requires_email_verification(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = DeveloperAccountService(repos.developer_accounts, publish=publisher)
        account = await service.register(organization_id, email="b@example.com", now=utcnow())
        with pytest.raises(ActivationNotEligibleError):
            await service.transition(account, target=DeveloperAccountStatus.ACTIVE, now=utcnow())

    async def test_activation_after_verification_notifies(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        service = DeveloperAccountService(
            repos.developer_accounts, publish=publisher, notifier=notifier
        )
        account = await service.register(organization_id, email="c@example.com", now=utcnow())
        account = await service.verify_email(account, now=utcnow())
        account = await service.transition(
            account, target=DeveloperAccountStatus.ACTIVE, now=utcnow()
        )
        assert account.approved_at is not None
        assert any(name == "notify_developer_approved" for name, _ in notifier.calls)

    async def test_suspend_then_reinstate(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = DeveloperAccountService(repos.developer_accounts, publish=publisher)
        account = await service.register(organization_id, email="d@example.com", now=utcnow())
        account = await service.verify_email(account, now=utcnow())
        account = await service.transition(
            account, target=DeveloperAccountStatus.ACTIVE, now=utcnow()
        )
        account = await service.transition(
            account, target=DeveloperAccountStatus.SUSPENDED, now=utcnow()
        )
        assert account.suspended_at is not None
        account = await service.transition(
            account, target=DeveloperAccountStatus.ACTIVE, now=utcnow()
        )
        assert account.status == DeveloperAccountStatus.ACTIVE

    async def test_invalid_transition_refused(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        service = DeveloperAccountService(repos.developer_accounts, publish=publisher)
        account = await service.register(organization_id, email="e@example.com", now=utcnow())
        with pytest.raises(DevTransitionRefusedError):
            await service.transition(
                account, target=DeveloperAccountStatus.PENDING_VERIFICATION, now=utcnow()
            )


class TestApplicationService:
    async def test_register_and_approve(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts, publish=publisher)
        developer = await dev_service.register(organization_id, email="f@example.com", now=utcnow())
        service = ApplicationService(repos.applications, publish=publisher, notifier=notifier)
        application = await service.register(
            organization_id, developer_account_id=developer.id, name="My App", now=utcnow()
        )
        assert application.status == ApplicationStatus.PENDING
        assert "ApplicationCreated" in publisher.names()
        application = await service.transition(
            application, target=ApplicationStatus.ACTIVE, now=utcnow()
        )
        assert application.approved_at is not None
        assert any(name == "notify_application_approved" for name, _ in notifier.calls)

    async def test_revoked_terminal(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts, publish=publisher)
        developer = await dev_service.register(organization_id, email="g@example.com", now=utcnow())
        service = ApplicationService(repos.applications, publish=publisher)
        application = await service.register(
            organization_id, developer_account_id=developer.id, name="App2", now=utcnow()
        )
        application = await service.transition(
            application, target=ApplicationStatus.REVOKED, now=utcnow()
        )
        with pytest.raises(AppTransitionRefusedError):
            await service.transition(application, target=ApplicationStatus.ACTIVE, now=utcnow())


class TestCredentialServices:
    async def _make_application(self, repos: Repositories, organization_id: uuid.UUID):  # type: ignore[no-untyped-def]
        dev_service = DeveloperAccountService(repos.developer_accounts)
        developer = await dev_service.register(
            organization_id, email=f"{uuid.uuid4()}@example.com", now=utcnow()
        )
        app_service = ApplicationService(repos.applications)
        return await app_service.register(
            organization_id, developer_account_id=developer.id, name="App", now=utcnow()
        )

    async def test_api_key_issue_and_revoke(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        application = await self._make_application(repos, organization_id)
        service = ApiKeyService(repos.api_keys, publish=publisher)
        key, raw = await service.issue(
            organization_id, application_id=application.id, now=utcnow(), max_age_days=365
        )
        assert len(raw) >= 32
        assert key.key_hash != raw
        assert "APIKeyGenerated" in publisher.names()
        key = await service.revoke(key, now=utcnow())
        assert key.revoked_at is not None
        with pytest.raises(CredentialTransitionRefusedError):
            await service.revoke(key, now=utcnow())

    async def test_pat_issue_and_revoke(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts)
        developer = await dev_service.register(
            organization_id, email="pat@example.com", now=utcnow()
        )
        service = PersonalAccessTokenService(repos.personal_access_tokens)
        token, raw = await service.issue(
            organization_id,
            developer_account_id=developer.id,
            name="my token",
            scopes=["read"],
            now=utcnow(),
            max_age_days=90,
        )
        assert token.token_hash != raw
        token = await service.revoke(token, now=utcnow())
        assert token.revoked_at is not None

    async def test_oauth_client_register(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        application = await self._make_application(repos, organization_id)
        service = OAuthClientService(repos.oauth_clients, publish=publisher)
        client, raw_secret = await service.register(
            organization_id,
            application_id=application.id,
            grant_types=["client_credentials"],
            redirect_uris=[],
            now=utcnow(),
        )
        assert client.client_secret_hash != raw_secret
        assert "OAuthClientCreated" in publisher.names()


class TestProductServices:
    async def test_product_governance_workflow(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        audit = AuditService(repos.audit)
        service = ApiProductService(repos.api_products, audit=audit)
        product = await service.create(
            organization_id,
            name="Weather API",
            description="d",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        assert product.status == ApiProductStatus.DRAFT
        product = await service.transition(
            product, target=ApiProductStatus.PENDING_APPROVAL, now=utcnow()
        )
        product = await service.transition(product, target=ApiProductStatus.APPROVED, now=utcnow())
        assert product.approved_at is not None
        with pytest.raises(ProductTransitionRefusedError):
            await service.transition(
                product, target=ApiProductStatus.PENDING_APPROVAL, now=utcnow()
            )

    async def test_plan_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        plan_service = ApiPlanService(repos.api_plans)
        plan = await plan_service.create(
            organization_id,
            api_product_id=product.id,
            name="Free",
            rate_limit_per_minute=60,
            quota_per_month=1000,
        )
        assert plan.name == "Free"

    async def test_subscription_publishes_event(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts)
        developer = await dev_service.register(
            organization_id, email="sub@example.com", now=utcnow()
        )
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        plan_service = ApiPlanService(repos.api_plans)
        plan = await plan_service.create(
            organization_id,
            api_product_id=product.id,
            name="Free",
            rate_limit_per_minute=60,
            quota_per_month=1000,
        )
        sub_service = ApiSubscriptionService(repos.api_subscriptions, publish=publisher)
        subscription = await sub_service.subscribe(
            organization_id, developer_account_id=developer.id, api_plan_id=plan.id, now=utcnow()
        )
        assert subscription.activated_at is not None
        assert "SubscriptionActivated" in publisher.names()


class TestApiVersionService:
    async def test_release_publishes_event(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        version_service = ApiVersionService(repos.api_versions, publish=publisher)
        version = await version_service.create_draft(
            organization_id, api_product_id=product.id, version="1.0.0"
        )
        assert version.status == ApiVersionStatus.DRAFT
        version = await version_service.transition(
            version, target=ApiVersionStatus.RELEASED, product=product, now=utcnow()
        )
        assert version.released_at is not None
        assert "APIVersionReleased" in publisher.names()

    async def test_skip_transition_refused(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        version_service = ApiVersionService(repos.api_versions)
        version = await version_service.create_draft(
            organization_id, api_product_id=product.id, version="1.0.0"
        )
        with pytest.raises(VersionTransitionRefusedError):
            await version_service.transition(
                version, target=ApiVersionStatus.DEPRECATED, product=product, now=utcnow()
            )


class TestDocumentServices:
    async def test_openapi_publish(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        version_service = ApiVersionService(repos.api_versions)
        version = await version_service.create_draft(
            organization_id, api_product_id=product.id, version="1.0.0"
        )
        service = OpenApiDocumentService(repos.openapi_documents)
        document = await service.publish(
            organization_id,
            api_product_id=product.id,
            api_version_id=version.id,
            document={"openapi": "3.1.0"},
            now=utcnow(),
        )
        assert document.is_published is True

    async def test_graphql_publish(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        version_service = ApiVersionService(repos.api_versions)
        version = await version_service.create_draft(
            organization_id, api_product_id=product.id, version="1.0.0"
        )
        service = GraphQlSchemaService(repos.graphql_schemas)
        schema = await service.publish(
            organization_id,
            api_product_id=product.id,
            api_version_id=version.id,
            schema_sdl="type Query { hello: String }",
            now=utcnow(),
        )
        assert schema.is_published is True

    async def test_changelog_publish(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        version_service = ApiVersionService(repos.api_versions)
        version = await version_service.create_draft(
            organization_id, api_product_id=product.id, version="1.0.0"
        )
        service = ApiChangelogService(repos.api_changelog)
        entry = await service.publish(
            organization_id,
            api_product_id=product.id,
            api_version_id=version.id,
            summary="Initial release",
            is_breaking=False,
            now=utcnow(),
        )
        assert entry.summary == "Initial release"


class TestUsageAndQuotaServices:
    async def test_usage_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts)
        developer = await dev_service.register(organization_id, email="u@example.com", now=utcnow())
        app_service = ApplicationService(repos.applications)
        application = await app_service.register(
            organization_id, developer_account_id=developer.id, name="App", now=utcnow()
        )
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        service = UsageService(repos.api_usage)
        event = await service.record(
            organization_id,
            developer_account_id=developer.id,
            application_id=application.id,
            api_product_id=product.id,
            endpoint="/x",
            status_code=200,
            latency_ms=15.0,
            occurred_at=utcnow(),
        )
        assert event.status_code == 200

    async def test_quota_provision_and_consume_exceeds(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts)
        developer = await dev_service.register(organization_id, email="q@example.com", now=utcnow())
        service = QuotaService(repos.api_quotas, publish=publisher)
        quota = await service.provision(
            organization_id,
            developer_account_id=developer.id,
            quota_type=QuotaType.API_CALLS,
            limit_value=2,
            reset_policy=QuotaResetPolicy.DAILY,
            now=utcnow(),
        )
        quota = await service.consume(quota)
        assert not publisher.names()
        quota = await service.consume(quota)
        assert quota.used_value == 2
        assert "QuotaExceeded" in publisher.names()
        # Consuming again past the limit does not re-publish.
        await service.consume(quota)
        assert publisher.names().count("QuotaExceeded") == 1

    async def test_quota_reset_for_new_period(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts)
        developer = await dev_service.register(
            organization_id, email="q2@example.com", now=utcnow()
        )
        service = QuotaService(repos.api_quotas)
        quota = await service.provision(
            organization_id,
            developer_account_id=developer.id,
            quota_type=QuotaType.STORAGE,
            limit_value=10,
            reset_policy=QuotaResetPolicy.DAILY,
            now=utcnow(),
        )
        quota = await service.consume(quota, amount=5)
        quota = await service.reset_for_new_period(quota, now=hours_ahead(25))
        assert quota.used_value == 0


class TestSandboxServices:
    async def test_start_and_reset(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        dev_service = DeveloperAccountService(repos.developer_accounts)
        developer = await dev_service.register(
            organization_id, email="sb@example.com", now=utcnow()
        )
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        service = SandboxService(repos.api_sandbox)
        session = await service.start(
            organization_id,
            developer_account_id=developer.id,
            api_product_id=product.id,
            now=utcnow(),
        )
        session = await service.reset(session, now=utcnow())
        assert session.call_count == 0

    async def test_mock_define_and_resolve(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product_service = ApiProductService(repos.api_products)
        product = await product_service.create(
            organization_id,
            name="P",
            description="",
            product_type=ApiProductType.PUBLIC,
            now=utcnow(),
        )
        config = MockServiceConfig(repos.api_mock_services)
        mock = await config.define(
            organization_id,
            api_product_id=product.id,
            endpoint_path="/mock",
            mock_type=MockType.STATIC,
            response_body={"ok": True},
        )
        outcome = MockServiceConfig.resolve(mock)
        assert outcome.status_code == 200
        assert outcome.body == {"ok": True}


class TestStatisticsAndReportServices:
    async def test_roll_up_window_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = StatisticsService(repos.statistics)
        window_start = utcnow()
        window_end = hours_ahead(1)
        await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=window_end,
            api_call_count=5,
            registration_count=1,
            application_count=1,
            sdk_download_count=0,
            error_count=0,
            average_latency_ms=10.0,
        )
        await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=window_end,
            api_call_count=10,
            registration_count=2,
            application_count=1,
            sdk_download_count=0,
            error_count=1,
            average_latency_ms=12.0,
        )
        rows = await service.list_range(organization_id, since=hours_ago(1))
        assert len(rows) == 1
        assert rows[0].api_call_count == 10

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReportKind.API_USAGE,
            title="Usage",
            period_start=hours_ago(1),
            period_end=utcnow(),
            row_count=10,
            now=utcnow(),
        )
        assert report.row_count == 10
