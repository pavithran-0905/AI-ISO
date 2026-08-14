"""Integration tests for repository query methods, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from shared_core.exceptions.not_found import NotFoundError

from app.models.cli import CliPlugin, CliProfile, CliSession, CliUpdate, CliUsage, CliVersion
from app.models.enums import (
    AuditAction,
    CliAuthMethod,
    CliUpdateStatus,
    PluginStatus,
    ReleaseStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    SdkLanguage,
)
from app.models.reporting import CliReport, CliStatistic, SdkAudit
from app.models.sdk import SdkDownload, SdkLanguageCatalog, SdkPackage, SdkRelease, SdkVersion

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _sdk_version(organization_id: UUID, **kwargs: object) -> SdkVersion:
    defaults: dict[str, object] = {
        "organization_id": organization_id,
        "language": SdkLanguage.PYTHON,
        "version_label": "1.0.0",
        "api_compatibility_version": "1.0.0",
    }
    defaults.update(kwargs)
    return SdkVersion(**defaults)


class TestSdkVersionRepository:
    async def test_require_in_org(self, repos, organization_id: UUID) -> None:
        created = await repos.sdk_versions.create(_sdk_version(organization_id))
        found = await repos.sdk_versions.require_in_org(organization_id, created.id)
        assert found.id == created.id

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.sdk_versions.require_in_org(organization_id, uuid4())

    async def test_list_for_language_and_recent(self, repos, organization_id: UUID) -> None:
        await repos.sdk_versions.create(_sdk_version(organization_id))
        found = await repos.sdk_versions.list_for_language(
            organization_id, language=SdkLanguage.PYTHON
        )
        assert len(found) == 1
        recent = await repos.sdk_versions.list_recent(organization_id)
        assert len(recent) == 1
        ids = await repos.sdk_versions.list_organization_ids()
        assert organization_id in ids

    async def test_list_with_planned_deprecation(self, repos, organization_id: UUID) -> None:
        await repos.sdk_versions.create(
            _sdk_version(organization_id, deprecated_at=NOW + timedelta(days=30))
        )
        await repos.sdk_versions.create(_sdk_version(organization_id, version_label="2.0.0"))
        found = await repos.sdk_versions.list_with_planned_deprecation(organization_id)
        assert len(found) == 1


class TestSdkLanguageCatalogRepository:
    async def test_find_by_language_and_list(self, repos, organization_id: UUID) -> None:
        await repos.sdk_languages.create(
            SdkLanguageCatalog(
                organization_id=organization_id, language=SdkLanguage.PYTHON, display_name="Python"
            )
        )
        found = await repos.sdk_languages.find_by_language(
            organization_id, language=SdkLanguage.PYTHON
        )
        assert found is not None
        enabled = await repos.sdk_languages.list_enabled(organization_id)
        assert len(enabled) == 1
        all_rows = await repos.sdk_languages.list_all(organization_id)
        assert len(all_rows) == 1


class TestSdkPackageRepository:
    async def test_list_for_version(self, repos, organization_id: UUID) -> None:
        version = await repos.sdk_versions.create(_sdk_version(organization_id))
        await repos.sdk_packages.create(
            SdkPackage(
                organization_id=organization_id,
                sdk_version_id=version.id,
                distribution_channel="pypi",
                package_ref="ai-ios-sdk",
                checksum_sha256="abc",
            )
        )
        found = await repos.sdk_packages.list_for_version(version.id)
        assert len(found) == 1


class TestSdkDownloadRepository:
    async def test_list_recent_and_counts(self, repos, organization_id: UUID) -> None:
        version = await repos.sdk_versions.create(_sdk_version(organization_id))
        await repos.sdk_downloads.create(
            SdkDownload(
                organization_id=organization_id, sdk_version_id=version.id, downloaded_at=NOW
            )
        )
        found = await repos.sdk_downloads.list_recent(organization_id)
        assert len(found) == 1
        count = await repos.sdk_downloads.count_since(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert count == 1
        version_count = await repos.sdk_downloads.count_for_version_since(
            version.id, since=NOW - timedelta(hours=1)
        )
        assert version_count == 1


class TestSdkReleaseRepository:
    async def test_list_for_version_and_recent(self, repos, organization_id: UUID) -> None:
        version = await repos.sdk_versions.create(_sdk_version(organization_id))
        await repos.sdk_releases.create(
            SdkRelease(organization_id=organization_id, sdk_version_id=version.id)
        )
        for_version = await repos.sdk_releases.list_for_version(version.id)
        assert len(for_version) == 1
        recent = await repos.sdk_releases.list_recent(organization_id, status=ReleaseStatus.DRAFT)
        assert len(recent) == 1
        by_status = await repos.sdk_releases.list_by_status(
            organization_id, status=ReleaseStatus.DRAFT
        )
        assert len(by_status) == 1
        ids = await repos.sdk_releases.list_organization_ids()
        assert organization_id in ids


class TestCliVersionRepository:
    async def test_list_recent_and_latest_enabled(self, repos, organization_id: UUID) -> None:
        await repos.cli_versions.create(
            CliVersion(
                organization_id=organization_id,
                version_label="1.0.0",
                api_compatibility_version="1.0.0",
            )
        )
        found = await repos.cli_versions.list_recent(organization_id)
        assert len(found) == 1
        latest = await repos.cli_versions.latest_enabled(organization_id)
        assert latest is not None
        ids = await repos.cli_versions.list_organization_ids()
        assert organization_id in ids

    async def test_list_with_planned_deprecation(self, repos, organization_id: UUID) -> None:
        await repos.cli_versions.create(
            CliVersion(
                organization_id=organization_id,
                version_label="1.0.0",
                api_compatibility_version="1.0.0",
                deprecated_at=NOW + timedelta(days=30),
            )
        )
        found = await repos.cli_versions.list_with_planned_deprecation(organization_id)
        assert len(found) == 1


class TestCliPluginRepository:
    async def test_require_in_org_and_find_by_name(self, repos, organization_id: UUID) -> None:
        created = await repos.cli_plugins.create(
            CliPlugin(
                organization_id=organization_id,
                name="observability",
                version_label="1.0.0",
                checksum_sha256="abc",
            )
        )
        found = await repos.cli_plugins.require_in_org(organization_id, created.id)
        assert found.id == created.id
        by_name = await repos.cli_plugins.find_by_name(organization_id, name="observability")
        assert by_name is not None
        recent = await repos.cli_plugins.list_recent(organization_id, status=PluginStatus.AVAILABLE)
        assert len(recent) == 1
        by_status = await repos.cli_plugins.list_by_status(
            organization_id, status=PluginStatus.AVAILABLE
        )
        assert len(by_status) == 1
        ids = await repos.cli_plugins.list_organization_ids()
        assert organization_id in ids

    async def test_require_in_org_missing_raises(self, repos, organization_id: UUID) -> None:
        with pytest.raises(NotFoundError):
            await repos.cli_plugins.require_in_org(organization_id, uuid4())


class TestCliProfileRepository:
    async def test_list_all_and_default_ids(self, repos, organization_id: UUID) -> None:
        await repos.cli_profiles.create(
            CliProfile(
                organization_id=organization_id,
                profile_name="default",
                auth_method=CliAuthMethod.API_KEY,
                is_default=True,
            )
        )
        found = await repos.cli_profiles.list_all(organization_id)
        assert len(found) == 1
        default_ids = await repos.cli_profiles.list_default_ids(organization_id)
        assert len(default_ids) == 1


class TestCliSessionRepository:
    async def test_list_for_profile_enabled_and_recent(self, repos, organization_id: UUID) -> None:
        profile = await repos.cli_profiles.create(
            CliProfile(
                organization_id=organization_id,
                profile_name="default",
                auth_method=CliAuthMethod.API_KEY,
            )
        )
        await repos.cli_sessions.create(
            CliSession(
                organization_id=organization_id,
                profile_id=profile.id,
                auth_method=CliAuthMethod.API_KEY,
                started_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
        )
        for_profile = await repos.cli_sessions.list_for_profile(profile.id)
        assert len(for_profile) == 1
        enabled = await repos.cli_sessions.list_enabled(organization_id)
        assert len(enabled) == 1
        recent = await repos.cli_sessions.list_recent(organization_id)
        assert len(recent) == 1
        ids = await repos.cli_sessions.list_organization_ids()
        assert organization_id in ids


class TestCliUsageRepository:
    async def test_count_since_and_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.cli_usage.create(
            CliUsage(
                organization_id=organization_id,
                session_id=None,
                command_group="auth",
                command="login",
                executed_at=NOW,
            )
        )
        count = await repos.cli_usage.count_since(organization_id, since=NOW - timedelta(hours=1))
        assert count == 1
        recent = await repos.cli_usage.list_recent(organization_id)
        assert len(recent) == 1


class TestCliUpdateRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.cli_updates.create(
            CliUpdate(
                organization_id=organization_id,
                from_version="1.0.0",
                to_version="1.1.0",
                status=CliUpdateStatus.APPLIED,
                checked_at=NOW,
            )
        )
        found = await repos.cli_updates.list_recent(organization_id)
        assert len(found) == 1


class TestCliStatisticRepository:
    async def test_find_window_and_list_range(self, repos, organization_id: UUID) -> None:
        await repos.statistics.create(
            CliStatistic(
                organization_id=organization_id,
                window_start=NOW,
                window_end=NOW + timedelta(hours=1),
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=NOW)
        assert found is not None
        in_range = await repos.statistics.list_range(
            organization_id, since=NOW - timedelta(hours=1)
        )
        assert len(in_range) == 1

    async def test_find_window_missing_returns_none(self, repos, organization_id: UUID) -> None:
        assert await repos.statistics.find_window(organization_id, window_start=NOW) is None


class TestCliReportRepository:
    async def test_list_recent(self, repos, organization_id: UUID) -> None:
        await repos.reports.create(
            CliReport(
                organization_id=organization_id,
                kind=ReportKind.SDK,
                report_format=ReportFormat.JSON,
                title="SDK Report",
                status=ReportStatus.COMPLETED,
            )
        )
        recent = await repos.reports.list_recent(organization_id, status=ReportStatus.COMPLETED)
        assert len(recent) == 1
        by_kind = await repos.reports.list_recent(organization_id, kind=ReportKind.SDK)
        assert len(by_kind) == 1


class TestSdkAuditRepository:
    async def test_list_recent_and_for_entity(self, repos, organization_id: UUID) -> None:
        entity_id = uuid4()
        await repos.audit.create(
            SdkAudit(
                organization_id=organization_id,
                action=AuditAction.SDK_RELEASED,
                entity_type="sdk_release",
                entity_id=entity_id,
                occurred_at=NOW,
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert len(found) == 1
        for_entity = await repos.audit.list_for_entity("sdk_release", entity_id)
        assert len(for_entity) == 1
        ids = await repos.audit.list_organization_ids()
        assert organization_id in ids

    async def test_list_recent_excludes_before_since(self, repos, organization_id: UUID) -> None:
        await repos.audit.create(
            SdkAudit(
                organization_id=organization_id,
                action=AuditAction.SDK_RELEASED,
                entity_type="sdk_release",
                occurred_at=NOW - timedelta(days=10),
            )
        )
        found = await repos.audit.list_recent(organization_id, since=NOW - timedelta(hours=1))
        assert found == []
