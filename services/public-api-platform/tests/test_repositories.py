"""Integration tests for every repository, against real PostgreSQL."""

from __future__ import annotations

import uuid

from app.models.applications import ApplicationCredential, DeveloperApplication
from app.models.credentials import ApiKey, OAuthClient, OAuthToken, PersonalAccessToken
from app.models.developers import DeveloperAccount
from app.models.documents import ApiChangelogEntry, ApiVersion, GraphQlSchema, OpenApiDocument
from app.models.enums import (
    ApiProductStatus,
    ApiProductType,
    CredentialStatus,
    DeveloperAuditAction,
    MockType,
    OAuthTokenType,
    QuotaResetPolicy,
    QuotaType,
    ReportFormat,
    ReportKind,
    ReportStatus,
)
from app.models.products import ApiPlan, ApiProduct, ApiSubscription
from app.models.reporting import DeveloperAudit, DeveloperReport
from app.models.sandbox import ApiMockService, ApiSandboxSession
from app.models.usage import ApiQuota, ApiRateLimit, ApiUsageEvent
from app.services.bundle import Repositories
from tests.conftest import hours_ago, hours_ahead, utcnow


async def _make_developer(
    repos: Repositories, organization_id: uuid.UUID, **overrides: object
) -> DeveloperAccount:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "email": f"{uuid.uuid4()}@example.com",
    }
    defaults.update(overrides)
    return await repos.developer_accounts.create(DeveloperAccount(**defaults))  # type: ignore[arg-type]


async def _make_application(
    repos: Repositories,
    organization_id: uuid.UUID,
    developer_account_id: uuid.UUID,
    **overrides: object,
) -> DeveloperApplication:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "developer_account_id": developer_account_id,
        "name": "app",
    }
    defaults.update(overrides)
    return await repos.applications.create(DeveloperApplication(**defaults))  # type: ignore[arg-type]


async def _make_product(
    repos: Repositories, organization_id: uuid.UUID, **overrides: object
) -> ApiProduct:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "name": "product",
        "product_type": ApiProductType.PUBLIC,
    }
    defaults.update(overrides)
    return await repos.api_products.create(ApiProduct(**defaults))  # type: ignore[arg-type]


class TestDeveloperAccountRepository:
    async def test_find_by_email(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        account = await _make_developer(repos, organization_id, email="a@example.com")
        found = await repos.developer_accounts.find_by_email(organization_id, email="a@example.com")
        assert found is not None
        assert found.id == account.id

    async def test_tenant_isolation(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        other_org = uuid.uuid4()
        await _make_developer(repos, other_org, email="shared@example.com")
        assert (
            await repos.developer_accounts.find_by_email(
                organization_id, email="shared@example.com"
            )
            is None
        )

    async def test_list_recent_and_count_since(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await _make_developer(repos, organization_id)
        await _make_developer(repos, organization_id)
        rows = await repos.developer_accounts.list_recent(organization_id)
        assert len(rows) == 2
        assert await repos.developer_accounts.count_since(organization_id, since=hours_ago(1)) == 2

    async def test_list_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await _make_developer(repos, organization_id)
        assert organization_id in await repos.developer_accounts.list_organization_ids()


class TestApplicationRepositories:
    async def test_list_for_developer_and_count(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        await _make_application(repos, organization_id, developer.id)
        rows = await repos.applications.list_for_developer(
            organization_id, developer_account_id=developer.id
        )
        assert len(rows) == 1
        assert (
            await repos.applications.count_for_developer(
                organization_id, developer_account_id=developer.id
            )
            == 1
        )

    async def test_list_recent_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        await _make_application(repos, organization_id, developer.id)
        assert len(await repos.applications.list_recent(organization_id)) == 1
        assert organization_id in await repos.applications.list_organization_ids()

    async def test_application_credential_find_by_client_id(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        application = await _make_application(repos, organization_id, developer.id)
        credential = await repos.application_credentials.create(
            ApplicationCredential(
                organization_id=organization_id,
                application_id=application.id,
                client_id="client-1",
                client_secret_hash="hash",
            )
        )
        found = await repos.application_credentials.find_by_client_id(
            organization_id, client_id="client-1"
        )
        assert found is not None
        assert found.id == credential.id
        assert len(await repos.application_credentials.list_for_application(application.id)) == 1


class TestProductRepositories:
    async def test_list_recent_filters_by_status(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await _make_product(repos, organization_id, status=ApiProductStatus.APPROVED)
        await _make_product(repos, organization_id, status=ApiProductStatus.DRAFT)
        approved = await repos.api_products.list_recent(
            organization_id, status=ApiProductStatus.APPROVED
        )
        assert len(approved) == 1

    async def test_plan_list_for_product(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product = await _make_product(repos, organization_id)
        await repos.api_plans.create(
            ApiPlan(organization_id=organization_id, api_product_id=product.id, name="basic")
        )
        rows = await repos.api_plans.list_for_product(product.id)
        assert len(rows) == 1
        assert len(await repos.api_plans.list_recent(organization_id)) == 1

    async def test_subscription_find_active_and_list_for_developer(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        product = await _make_product(repos, organization_id)
        plan = await repos.api_plans.create(
            ApiPlan(organization_id=organization_id, api_product_id=product.id, name="basic")
        )
        await repos.api_subscriptions.create(
            ApiSubscription(
                organization_id=organization_id,
                developer_account_id=developer.id,
                api_plan_id=plan.id,
                activated_at=utcnow(),
            )
        )
        found = await repos.api_subscriptions.find_active(
            organization_id, developer_account_id=developer.id, api_plan_id=plan.id
        )
        assert found is not None
        rows = await repos.api_subscriptions.list_for_developer(
            organization_id, developer_account_id=developer.id
        )
        assert len(rows) == 1


class TestCredentialRepositories:
    async def test_api_key_list_active_and_for_application(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        application = await _make_application(repos, organization_id, developer.id)
        await repos.api_keys.create(
            ApiKey(
                organization_id=organization_id,
                application_id=application.id,
                key_hash="hash1",
                expires_at=hours_ahead(1),
            )
        )
        await repos.api_keys.create(
            ApiKey(
                organization_id=organization_id,
                application_id=application.id,
                key_hash="hash2",
                status=CredentialStatus.REVOKED,
                expires_at=hours_ahead(1),
            )
        )
        active = await repos.api_keys.list_active(organization_id)
        assert len(active) == 1
        assert len(await repos.api_keys.list_for_application(application.id)) == 2
        assert organization_id in await repos.api_keys.list_organization_ids()

    async def test_pat_list_active_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        await repos.personal_access_tokens.create(
            PersonalAccessToken(
                organization_id=organization_id,
                developer_account_id=developer.id,
                token_hash="hash",
                expires_at=hours_ahead(1),
            )
        )
        assert len(await repos.personal_access_tokens.list_active(organization_id)) == 1
        assert organization_id in await repos.personal_access_tokens.list_organization_ids()

    async def test_oauth_client_find_by_client_id(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        application = await _make_application(repos, organization_id, developer.id)
        client = await repos.oauth_clients.create(
            OAuthClient(
                organization_id=organization_id,
                application_id=application.id,
                client_id="oclient-1",
                client_secret_hash="hash",
            )
        )
        found = await repos.oauth_clients.find_by_client_id(organization_id, client_id="oclient-1")
        assert found is not None
        assert found.id == client.id

    async def test_oauth_token_list_active_and_organization_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        application = await _make_application(repos, organization_id, developer.id)
        client = await repos.oauth_clients.create(
            OAuthClient(
                organization_id=organization_id,
                application_id=application.id,
                client_id="oclient-2",
                client_secret_hash="hash",
            )
        )
        await repos.oauth_tokens.create(
            OAuthToken(
                organization_id=organization_id,
                oauth_client_id=client.id,
                token_hash="thash",
                token_type=OAuthTokenType.ACCESS,
                issued_at=utcnow(),
                expires_at=hours_ahead(1),
            )
        )
        assert len(await repos.oauth_tokens.list_active(organization_id)) == 1
        assert organization_id in await repos.oauth_tokens.list_organization_ids()


class TestDocumentRepositories:
    async def test_version_list_for_product_and_planned_dates(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product = await _make_product(repos, organization_id)
        await repos.api_versions.create(
            ApiVersion(
                organization_id=organization_id,
                api_product_id=product.id,
                version_label="1.0.0",
                deprecated_at=hours_ahead(1),
            )
        )
        rows = await repos.api_versions.list_for_product(product.id)
        assert len(rows) == 1
        assert len(await repos.api_versions.list_with_planned_deprecation(organization_id)) == 1
        assert len(await repos.api_versions.list_with_planned_sunset(organization_id)) == 0
        assert organization_id in await repos.api_versions.list_organization_ids()

    async def test_openapi_document_find_published(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product = await _make_product(repos, organization_id)
        version = await repos.api_versions.create(
            ApiVersion(
                organization_id=organization_id, api_product_id=product.id, version_label="1.0.0"
            )
        )
        await repos.openapi_documents.create(
            OpenApiDocument(
                organization_id=organization_id,
                api_product_id=product.id,
                api_version_id=version.id,
                is_published=False,
            )
        )
        assert (
            await repos.openapi_documents.find_published_for_product(
                organization_id, api_product_id=product.id
            )
            is None
        )
        await repos.openapi_documents.create(
            OpenApiDocument(
                organization_id=organization_id,
                api_product_id=product.id,
                api_version_id=version.id,
                is_published=True,
                published_at=utcnow(),
            )
        )
        found = await repos.openapi_documents.find_published_for_product(
            organization_id, api_product_id=product.id
        )
        assert found is not None

    async def test_graphql_schema_find_published(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product = await _make_product(repos, organization_id)
        version = await repos.api_versions.create(
            ApiVersion(
                organization_id=organization_id, api_product_id=product.id, version_label="1.0.0"
            )
        )
        await repos.graphql_schemas.create(
            GraphQlSchema(
                organization_id=organization_id,
                api_product_id=product.id,
                api_version_id=version.id,
                is_published=True,
                published_at=utcnow(),
            )
        )
        found = await repos.graphql_schemas.find_published_for_product(
            organization_id, api_product_id=product.id
        )
        assert found is not None

    async def test_changelog_list_for_product(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product = await _make_product(repos, organization_id)
        version = await repos.api_versions.create(
            ApiVersion(
                organization_id=organization_id, api_product_id=product.id, version_label="1.0.0"
            )
        )
        await repos.api_changelog.create(
            ApiChangelogEntry(
                organization_id=organization_id,
                api_product_id=product.id,
                api_version_id=version.id,
                summary="initial",
                published_at=utcnow(),
            )
        )
        rows = await repos.api_changelog.list_for_product(
            organization_id, api_product_id=product.id
        )
        assert len(rows) == 1


class TestUsageRepositories:
    async def test_usage_list_since_and_for_developer(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        application = await _make_application(repos, organization_id, developer.id)
        product = await _make_product(repos, organization_id)
        await repos.api_usage.create(
            ApiUsageEvent(
                organization_id=organization_id,
                developer_account_id=developer.id,
                application_id=application.id,
                api_product_id=product.id,
                endpoint="/x",
                status_code=200,
                latency_ms=10.0,
                occurred_at=utcnow(),
            )
        )
        assert len(await repos.api_usage.list_since(organization_id, since=hours_ago(1))) == 1
        assert (
            len(
                await repos.api_usage.list_for_developer(
                    organization_id, developer_account_id=developer.id, since=hours_ago(1)
                )
            )
            == 1
        )
        assert organization_id in await repos.api_usage.list_organization_ids()

    async def test_rate_limit_find_for_plan(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product = await _make_product(repos, organization_id)
        plan = await repos.api_plans.create(
            ApiPlan(organization_id=organization_id, api_product_id=product.id, name="basic")
        )
        await repos.api_rate_limits.create(
            ApiRateLimit(organization_id=organization_id, api_plan_id=plan.id)
        )
        found = await repos.api_rate_limits.find_for_plan(plan.id)
        assert found is not None

    async def test_quota_find_list_and_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        period_start, period_end = utcnow(), hours_ahead(24)
        await repos.api_quotas.create(
            ApiQuota(
                organization_id=organization_id,
                developer_account_id=developer.id,
                quota_type=QuotaType.API_CALLS,
                limit_value=100,
                reset_policy=QuotaResetPolicy.DAILY,
                period_start=period_start,
                period_end=period_end,
            )
        )
        found = await repos.api_quotas.find(
            organization_id, developer_account_id=developer.id, quota_type=QuotaType.API_CALLS
        )
        assert found is not None
        assert (
            len(
                await repos.api_quotas.list_for_developer(
                    organization_id, developer_account_id=developer.id
                )
            )
            == 1
        )
        assert len(await repos.api_quotas.list_all(organization_id)) == 1
        assert organization_id in await repos.api_quotas.list_organization_ids()


class TestSandboxRepositories:
    async def test_sandbox_list_active_and_find(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        developer = await _make_developer(repos, organization_id)
        product = await _make_product(repos, organization_id)
        await repos.api_sandbox.create(
            ApiSandboxSession(
                organization_id=organization_id,
                developer_account_id=developer.id,
                api_product_id=product.id,
                last_reset_at=utcnow(),
            )
        )
        assert len(await repos.api_sandbox.list_active(organization_id)) == 1
        found = await repos.api_sandbox.find_active_for_product(
            organization_id, developer_account_id=developer.id, api_product_id=product.id
        )
        assert found is not None
        assert organization_id in await repos.api_sandbox.list_organization_ids()

    async def test_mock_service_list_and_find(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        product = await _make_product(repos, organization_id)
        await repos.api_mock_services.create(
            ApiMockService(
                organization_id=organization_id,
                api_product_id=product.id,
                endpoint_path="/mock",
                mock_type=MockType.STATIC,
            )
        )
        assert len(await repos.api_mock_services.list_for_product(product.id)) == 1
        found = await repos.api_mock_services.find_for_endpoint(
            organization_id, api_product_id=product.id, endpoint_path="/mock"
        )
        assert found is not None


class TestReportingRepositories:
    async def test_statistic_find_window_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        from app.models.reporting import DeveloperStatistic

        window_start = utcnow()
        await repos.statistics.create(
            DeveloperStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=hours_ahead(1),
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert found is not None
        assert len(await repos.statistics.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_list_recent_filters(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.reports.create(
            DeveloperReport(
                organization_id=organization_id,
                kind=ReportKind.API_USAGE,
                report_format=ReportFormat.JSON,
                title="Usage",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        rows = await repos.reports.list_recent(organization_id, kind=ReportKind.API_USAGE)
        assert len(rows) == 1
        completed = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(completed) == 1

    async def test_audit_list_recent_and_for_entity(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        entity_id = uuid.uuid4()
        await repos.audit.create(
            DeveloperAudit(
                organization_id=organization_id,
                action=DeveloperAuditAction.DEVELOPER_REGISTRATION,
                entity_type="developer_account",
                entity_id=entity_id,
                summary="registered",
                occurred_at=utcnow(),
            )
        )
        assert len(await repos.audit.list_recent(organization_id)) == 1
        assert len(await repos.audit.list_for_entity("developer_account", entity_id)) == 1

    async def test_audit_since_filter(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.audit.create(
            DeveloperAudit(
                organization_id=organization_id,
                action=DeveloperAuditAction.ADMINISTRATIVE,
                entity_type="x",
                entity_id=uuid.uuid4(),
                summary="old",
                occurred_at=hours_ago(48),
            )
        )
        assert len(await repos.audit.list_recent(organization_id, since=hours_ago(1))) == 0
