"""The repository bundle every route works through.

One object rather than twenty-three constructor arguments, all sharing
one tenant scope: a bundle where one repository was built without it
would enforce tenant isolation everywhere except the one query that
forgot, and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.applications import (
    ApplicationCredentialRepository,
    DeveloperApplicationRepository,
)
from app.repositories.credentials import (
    ApiKeyRepository,
    OAuthClientRepository,
    OAuthTokenRepository,
    PersonalAccessTokenRepository,
)
from app.repositories.developers import DeveloperAccountRepository, DeveloperOrganizationRepository
from app.repositories.documents import (
    ApiChangelogEntryRepository,
    ApiVersionRepository,
    GraphQlSchemaRepository,
    OpenApiDocumentRepository,
)
from app.repositories.products import (
    ApiPlanRepository,
    ApiProductRepository,
    ApiSubscriptionRepository,
)
from app.repositories.reporting import (
    DeveloperAuditRepository,
    DeveloperReportRepository,
    DeveloperStatisticRepository,
)
from app.repositories.sandbox import ApiMockServiceRepository, ApiSandboxSessionRepository
from app.repositories.usage import (
    ApiQuotaRepository,
    ApiRateLimitRepository,
    ApiUsageEventRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    developer_accounts: DeveloperAccountRepository
    developer_organizations: DeveloperOrganizationRepository

    applications: DeveloperApplicationRepository
    application_credentials: ApplicationCredentialRepository

    api_products: ApiProductRepository
    api_plans: ApiPlanRepository
    api_subscriptions: ApiSubscriptionRepository

    api_keys: ApiKeyRepository
    personal_access_tokens: PersonalAccessTokenRepository
    oauth_clients: OAuthClientRepository
    oauth_tokens: OAuthTokenRepository

    api_versions: ApiVersionRepository
    openapi_documents: OpenApiDocumentRepository
    graphql_schemas: GraphQlSchemaRepository
    api_changelog: ApiChangelogEntryRepository

    api_usage: ApiUsageEventRepository
    api_rate_limits: ApiRateLimitRepository
    api_quotas: ApiQuotaRepository

    api_sandbox: ApiSandboxSessionRepository
    api_mock_services: ApiMockServiceRepository

    statistics: DeveloperStatisticRepository
    reports: DeveloperReportRepository
    audit: DeveloperAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        developer_accounts=DeveloperAccountRepository(session, tenant_scope=tenant_scope),
        developer_organizations=DeveloperOrganizationRepository(session, tenant_scope=tenant_scope),
        applications=DeveloperApplicationRepository(session, tenant_scope=tenant_scope),
        application_credentials=ApplicationCredentialRepository(session, tenant_scope=tenant_scope),
        api_products=ApiProductRepository(session, tenant_scope=tenant_scope),
        api_plans=ApiPlanRepository(session, tenant_scope=tenant_scope),
        api_subscriptions=ApiSubscriptionRepository(session, tenant_scope=tenant_scope),
        api_keys=ApiKeyRepository(session, tenant_scope=tenant_scope),
        personal_access_tokens=PersonalAccessTokenRepository(session, tenant_scope=tenant_scope),
        oauth_clients=OAuthClientRepository(session, tenant_scope=tenant_scope),
        oauth_tokens=OAuthTokenRepository(session, tenant_scope=tenant_scope),
        api_versions=ApiVersionRepository(session, tenant_scope=tenant_scope),
        openapi_documents=OpenApiDocumentRepository(session, tenant_scope=tenant_scope),
        graphql_schemas=GraphQlSchemaRepository(session, tenant_scope=tenant_scope),
        api_changelog=ApiChangelogEntryRepository(session, tenant_scope=tenant_scope),
        api_usage=ApiUsageEventRepository(session, tenant_scope=tenant_scope),
        api_rate_limits=ApiRateLimitRepository(session, tenant_scope=tenant_scope),
        api_quotas=ApiQuotaRepository(session, tenant_scope=tenant_scope),
        api_sandbox=ApiSandboxSessionRepository(session, tenant_scope=tenant_scope),
        api_mock_services=ApiMockServiceRepository(session, tenant_scope=tenant_scope),
        statistics=DeveloperStatisticRepository(session, tenant_scope=tenant_scope),
        reports=DeveloperReportRepository(session, tenant_scope=tenant_scope),
        audit=DeveloperAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
