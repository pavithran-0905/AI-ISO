"""Integration tests for the service layer, against real PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.events.domain_events import (
    AuthenticationSucceededEvent,
    CliDownloadedEvent,
    CliReleasedEvent,
    PluginInstalledEvent,
    PluginUpdatedEvent,
    ProfileCreatedEvent,
    SdkDownloadedEvent,
    SdkReleasedEvent,
)
from app.generator.engine import FieldSpec
from app.models.enums import (
    CliAuthMethod,
    PluginStatus,
    ReleaseStatus,
    ReportFormat,
    ReportKind,
    SdkLanguage,
)
from app.services.audit import AuditService
from app.services.cli_plugins import CliPluginService
from app.services.cli_plugins import TransitionRefusedError as PluginTransitionRefusedError
from app.services.cli_profiles import CliProfileService
from app.services.cli_sessions import AuthenticationFailedError, CliSessionService
from app.services.cli_updates import CliUpdateService
from app.services.cli_usage import CliUsageService
from app.services.cli_versions import CliVersionService
from app.services.generator import CodeGenerationService, ModelSpec
from app.services.reports import ReportService
from app.services.sdk_releases import SdkReleaseService
from app.services.sdk_releases import TransitionRefusedError as SdkTransitionRefusedError
from app.services.sdk_versions import (
    SdkDownloadService,
    SdkLanguageCatalogService,
    SdkPackageService,
    SdkVersionService,
)
from app.services.statistics import StatisticsService

NOW = datetime(2026, 6, 1, tzinfo=UTC)


class TestSdkVersionService:
    async def test_create_and_deprecate(self, repos, organization_id) -> None:
        service = SdkVersionService(repos.sdk_versions)
        version = await service.create_version(
            organization_id,
            language=SdkLanguage.PYTHON,
            version="1.0.0",
            api_compatibility_version="1.0.0",
        )
        assert version.deprecated_at is None
        deprecated = await service.deprecate(version, now=NOW)
        assert deprecated.deprecated_at == NOW


class TestSdkLanguageCatalogService:
    async def test_register_is_idempotent(self, repos, organization_id) -> None:
        service = SdkLanguageCatalogService(repos.sdk_languages)
        first = await service.register_language(
            organization_id, language=SdkLanguage.PYTHON, display_name="Python"
        )
        second = await service.register_language(
            organization_id, language=SdkLanguage.PYTHON, display_name="Python"
        )
        assert first.id == second.id

    async def test_set_latest_version(self, repos, organization_id) -> None:
        version_service = SdkVersionService(repos.sdk_versions)
        version = await version_service.create_version(
            organization_id,
            language=SdkLanguage.PYTHON,
            version="1.0.0",
            api_compatibility_version="1.0.0",
        )
        service = SdkLanguageCatalogService(repos.sdk_languages)
        catalog_entry = await service.register_language(
            organization_id, language=SdkLanguage.PYTHON, display_name="Python"
        )
        updated = await service.set_latest_version(catalog_entry, sdk_version_id=version.id)
        assert updated.latest_version_id == version.id


class TestSdkPackageService:
    async def test_add_package(self, repos, organization_id) -> None:
        version_service = SdkVersionService(repos.sdk_versions)
        version = await version_service.create_version(
            organization_id,
            language=SdkLanguage.PYTHON,
            version="1.0.0",
            api_compatibility_version="1.0.0",
        )
        service = SdkPackageService(repos.sdk_packages)
        package = await service.add_package(
            organization_id,
            sdk_version_id=version.id,
            distribution_channel="pypi",
            package_ref="ai-ios-sdk",
            checksum_sha256="abc",
        )
        assert package.package_ref == "ai-ios-sdk"


class TestSdkDownloadService:
    async def test_record_download_publishes_event(self, repos, organization_id, publisher) -> None:
        version_service = SdkVersionService(repos.sdk_versions)
        version = await version_service.create_version(
            organization_id,
            language=SdkLanguage.PYTHON,
            version="1.0.0",
            api_compatibility_version="1.0.0",
        )
        service = SdkDownloadService(repos.sdk_downloads, publish=publisher)
        download = await service.record_download(
            organization_id, sdk_version_id=version.id, language=SdkLanguage.PYTHON, now=NOW
        )
        assert download.sdk_version_id == version.id
        assert publisher.names() == [SdkDownloadedEvent.event_name]


class TestSdkReleaseService:
    async def test_publish_publishes_event(self, repos, organization_id, publisher) -> None:
        version_service = SdkVersionService(repos.sdk_versions)
        version = await version_service.create_version(
            organization_id,
            language=SdkLanguage.PYTHON,
            version="1.0.0",
            api_compatibility_version="1.0.0",
        )
        service = SdkReleaseService(
            repos.sdk_releases, publish=publisher, audit=AuditService(repos.audit)
        )
        release = await service.create_draft(
            organization_id, sdk_version_id=version.id, release_notes="notes"
        )
        assert release.status == ReleaseStatus.DRAFT
        published = await service.transition(
            release,
            target=ReleaseStatus.PUBLISHED,
            language=SdkLanguage.PYTHON,
            version="1.0.0",
            actor_id="tester",
            now=NOW,
        )
        assert published.status == ReleaseStatus.PUBLISHED
        assert published.published_at == NOW
        assert publisher.names() == [SdkReleasedEvent.event_name]

    async def test_breaking_changes_carried_in_payload(
        self, repos, organization_id, publisher
    ) -> None:
        version_service = SdkVersionService(repos.sdk_versions)
        version = await version_service.create_version(
            organization_id,
            language=SdkLanguage.PYTHON,
            version="2.0.0",
            api_compatibility_version="2.0.0",
        )
        service = SdkReleaseService(repos.sdk_releases, publish=publisher)
        release = await service.create_draft(
            organization_id, sdk_version_id=version.id, release_notes="", breaking_changes=True
        )
        await service.transition(
            release,
            target=ReleaseStatus.PUBLISHED,
            language=SdkLanguage.PYTHON,
            version="2.0.0",
            actor_id=None,
            now=NOW,
        )
        assert publisher.payloads(SdkReleasedEvent.event_name)[0]["breaking_changes"] is True

    async def test_invalid_transition_raises(self, repos, organization_id, publisher) -> None:
        version_service = SdkVersionService(repos.sdk_versions)
        version = await version_service.create_version(
            organization_id,
            language=SdkLanguage.PYTHON,
            version="1.0.0",
            api_compatibility_version="1.0.0",
        )
        service = SdkReleaseService(repos.sdk_releases, publish=publisher)
        release = await service.create_draft(
            organization_id, sdk_version_id=version.id, release_notes=""
        )
        with pytest.raises(SdkTransitionRefusedError):
            await service.transition(
                release,
                target=ReleaseStatus.DEPRECATED,
                language=SdkLanguage.PYTHON,
                version="1.0.0",
                actor_id=None,
                now=NOW,
            )


class TestCodeGenerationService:
    async def test_generate_models(self) -> None:
        service = CodeGenerationService()
        artifacts = service.generate_models(
            SdkLanguage.PYTHON, [ModelSpec(class_name="User", fields=[FieldSpec("id", "uuid")])]
        )
        assert len(artifacts) == 1
        assert "class User:" in artifacts[0].source

    async def test_empty_model_specs_raises(self) -> None:
        service = CodeGenerationService()
        with pytest.raises(ValueError, match="empty"):
            service.generate_models(SdkLanguage.PYTHON, [])


class TestCliVersionService:
    async def test_register_version_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        service = CliVersionService(repos.cli_versions, publish=publisher)
        version = await service.register_version(
            organization_id, version="1.0.0", api_compatibility_version="1.0.0"
        )
        assert version.version_label == "1.0.0"
        assert publisher.names() == [CliReleasedEvent.event_name]


class TestCliPluginService:
    async def test_register_and_install_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        service = CliPluginService(
            repos.cli_plugins, publish=publisher, audit=AuditService(repos.audit)
        )
        plugin = await service.register(
            organization_id, name="observability", version="1.0.0", checksum_sha256="abc"
        )
        assert plugin.status == PluginStatus.AVAILABLE
        installed = await service.transition(
            plugin, target=PluginStatus.INSTALLED, actor_id="tester", now=NOW
        )
        assert installed.status == PluginStatus.INSTALLED
        assert PluginInstalledEvent.event_name in publisher.names()

    async def test_non_install_transition_publishes_updated(
        self, repos, organization_id, publisher
    ) -> None:
        service = CliPluginService(repos.cli_plugins, publish=publisher)
        plugin = await service.register(
            organization_id, name="observability", version="1.0.0", checksum_sha256="abc"
        )
        installed = await service.transition(
            plugin, target=PluginStatus.INSTALLED, actor_id=None, now=NOW
        )
        deprecated = await service.transition(
            installed, target=PluginStatus.DEPRECATED, actor_id=None, now=NOW
        )
        assert deprecated.status == PluginStatus.DEPRECATED
        assert PluginUpdatedEvent.event_name in publisher.names()

    async def test_invalid_transition_raises(self, repos, organization_id, publisher) -> None:
        service = CliPluginService(repos.cli_plugins, publish=publisher)
        plugin = await service.register(
            organization_id, name="observability", version="1.0.0", checksum_sha256="abc"
        )
        with pytest.raises(PluginTransitionRefusedError):
            await service.transition(plugin, target=PluginStatus.REMOVED, actor_id=None, now=NOW)


class TestCliProfileService:
    async def test_create_profile_publishes_event(self, repos, organization_id, publisher) -> None:
        service = CliProfileService(repos.cli_profiles, publish=publisher)
        profile = await service.create_profile(
            organization_id, profile_name="default", auth_method=CliAuthMethod.API_KEY
        )
        assert profile.profile_name == "default"
        assert publisher.names() == [ProfileCreatedEvent.event_name]

    async def test_only_one_default_at_a_time(self, repos, organization_id, publisher) -> None:
        service = CliProfileService(repos.cli_profiles, publish=publisher)
        first = await service.create_profile(
            organization_id,
            profile_name="first",
            auth_method=CliAuthMethod.API_KEY,
            is_default=True,
        )
        second = await service.create_profile(
            organization_id,
            profile_name="second",
            auth_method=CliAuthMethod.API_KEY,
            is_default=True,
        )
        refreshed_first = await repos.cli_profiles.require_by_id(first.id)
        assert refreshed_first.is_default is False
        assert second.is_default is True

    async def test_make_default_unsets_previous(self, repos, organization_id, publisher) -> None:
        service = CliProfileService(repos.cli_profiles, publish=publisher)
        first = await service.create_profile(
            organization_id,
            profile_name="first",
            auth_method=CliAuthMethod.API_KEY,
            is_default=True,
        )
        second = await service.create_profile(
            organization_id, profile_name="second", auth_method=CliAuthMethod.API_KEY
        )
        await service.make_default(second)
        refreshed_first = await repos.cli_profiles.require_by_id(first.id)
        assert refreshed_first.is_default is False


class TestCliSessionService:
    async def test_authenticate_success_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        profile_service = CliProfileService(repos.cli_profiles)
        profile = await profile_service.create_profile(
            organization_id, profile_name="default", auth_method=CliAuthMethod.API_KEY
        )
        service = CliSessionService(repos.cli_sessions, publish=publisher)
        session = await service.authenticate(profile, succeeded=True, max_age_minutes=60, now=NOW)
        assert session.is_enabled is True
        assert publisher.names() == [AuthenticationSucceededEvent.event_name]
        assert service.is_usable(session, now=NOW)
        assert not service.is_usable(session, now=NOW + timedelta(hours=2))

    async def test_authenticate_failure_notifies_and_raises(
        self, repos, organization_id, notifier
    ) -> None:
        profile_service = CliProfileService(repos.cli_profiles)
        profile = await profile_service.create_profile(
            organization_id, profile_name="default", auth_method=CliAuthMethod.API_KEY
        )
        service = CliSessionService(repos.cli_sessions, notifier=notifier)
        with pytest.raises(AuthenticationFailedError):
            await service.authenticate(profile, succeeded=False, max_age_minutes=60, now=NOW)
        assert any(name == "notify_authentication_failure" for name, _ in notifier.calls)

    async def test_force_logout(self, repos, organization_id) -> None:
        profile_service = CliProfileService(repos.cli_profiles)
        profile = await profile_service.create_profile(
            organization_id, profile_name="default", auth_method=CliAuthMethod.API_KEY
        )
        service = CliSessionService(repos.cli_sessions)
        session = await service.authenticate(profile, succeeded=True, max_age_minutes=60, now=NOW)
        logged_out = await service.force_logout(session)
        assert logged_out.is_enabled is False
        assert not service.is_usable(logged_out, now=NOW)


class TestCliUsageService:
    async def test_record(self, repos, organization_id) -> None:
        service = CliUsageService(repos.cli_usage)
        usage = await service.record(
            organization_id, session_id=None, command_group="auth", command="login", now=NOW
        )
        assert usage.command == "login"


class TestCliUpdateService:
    async def test_successful_attempt_publishes_event(
        self, repos, organization_id, publisher
    ) -> None:
        service = CliUpdateService(repos.cli_updates, publish=publisher)
        update = await service.attempt_update(
            organization_id, from_version="1.0.0", to_version="1.1.0", succeeded=True, now=NOW
        )
        assert update.status.value == "applied"
        assert update.applied_at == NOW
        assert publisher.names() == [CliDownloadedEvent.event_name]

    async def test_failed_attempt_does_not_publish(self, repos, organization_id, publisher) -> None:
        service = CliUpdateService(repos.cli_updates, publish=publisher)
        update = await service.attempt_update(
            organization_id, from_version="1.0.0", to_version="1.1.0", succeeded=False, now=NOW
        )
        assert update.status.value == "failed"
        assert update.applied_at is None
        assert publisher.names() == []


class TestStatisticsService:
    async def test_roll_up_window_is_idempotent(self, repos, organization_id) -> None:
        service = StatisticsService(repos.statistics)
        first = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=NOW + timedelta(hours=1),
            sdk_download_count=1,
            cli_download_count=1,
            command_execution_count=5,
            plugin_install_count=1,
            auth_success_count=1,
            auth_failure_count=0,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=NOW,
            window_end=NOW + timedelta(hours=1),
            sdk_download_count=2,
            cli_download_count=2,
            command_execution_count=10,
            plugin_install_count=2,
            auth_success_count=2,
            auth_failure_count=0,
        )
        assert second.id == first.id
        assert second.sdk_download_count == 2


class TestReportService:
    async def test_generate(self, repos, organization_id) -> None:
        report = await ReportService(repos.reports).generate(
            organization_id,
            kind=ReportKind.SDK,
            title="SDK Report",
            report_format=ReportFormat.JSON,
            period_start=NOW,
            period_end=NOW + timedelta(days=7),
            content={"downloads": 5},
            row_count=1,
            generated_by="tester",
            now=NOW,
        )
        assert report.status.value == "completed"


class TestAuditService:
    async def test_record(self, repos, organization_id) -> None:
        from app.models.enums import AuditAction

        entry = await AuditService(repos.audit).record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="test",
            entity_id=None,
            occurred_at=NOW,
            summary="test entry",
        )
        assert entry.id is not None
        assert entry.succeeded is True
