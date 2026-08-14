"""The repository bundle every route works through.

One object rather than fourteen constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cli import (
    CliPluginRepository,
    CliProfileRepository,
    CliSessionRepository,
    CliUpdateRepository,
    CliUsageRepository,
    CliVersionRepository,
)
from app.repositories.reporting import (
    CliReportRepository,
    CliStatisticRepository,
    SdkAuditRepository,
)
from app.repositories.sdk import (
    SdkDownloadRepository,
    SdkLanguageCatalogRepository,
    SdkPackageRepository,
    SdkReleaseRepository,
    SdkVersionRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    sdk_versions: SdkVersionRepository
    sdk_languages: SdkLanguageCatalogRepository
    sdk_packages: SdkPackageRepository
    sdk_downloads: SdkDownloadRepository
    sdk_releases: SdkReleaseRepository

    cli_versions: CliVersionRepository
    cli_plugins: CliPluginRepository
    cli_profiles: CliProfileRepository
    cli_sessions: CliSessionRepository
    cli_usage: CliUsageRepository
    cli_updates: CliUpdateRepository

    statistics: CliStatisticRepository
    reports: CliReportRepository
    audit: SdkAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        sdk_versions=SdkVersionRepository(session, tenant_scope=tenant_scope),
        sdk_languages=SdkLanguageCatalogRepository(session, tenant_scope=tenant_scope),
        sdk_packages=SdkPackageRepository(session, tenant_scope=tenant_scope),
        sdk_downloads=SdkDownloadRepository(session, tenant_scope=tenant_scope),
        sdk_releases=SdkReleaseRepository(session, tenant_scope=tenant_scope),
        cli_versions=CliVersionRepository(session, tenant_scope=tenant_scope),
        cli_plugins=CliPluginRepository(session, tenant_scope=tenant_scope),
        cli_profiles=CliProfileRepository(session, tenant_scope=tenant_scope),
        cli_sessions=CliSessionRepository(session, tenant_scope=tenant_scope),
        cli_usage=CliUsageRepository(session, tenant_scope=tenant_scope),
        cli_updates=CliUpdateRepository(session, tenant_scope=tenant_scope),
        statistics=CliStatisticRepository(session, tenant_scope=tenant_scope),
        reports=CliReportRepository(session, tenant_scope=tenant_scope),
        audit=SdkAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
