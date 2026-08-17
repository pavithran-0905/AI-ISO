"""Unit/integration tests for every service, against real PostgreSQL."""

from __future__ import annotations

import uuid

import pytest

from app.models.channels import ReleaseChannelConfig
from app.models.enums import (
    ArtifactType,
    ChecksumAlgorithm,
    DistributionType,
    PackageFormat,
    ReleaseAuditAction,
    ReleaseChannelType,
    ReleaseNoteType,
    ReleaseReportKind,
)
from app.models.releases import ReleaseVersion
from app.services import releases as releases_services
from app.services.audit import AuditService
from app.services.builds import ReleaseBuildService
from app.services.bundle import Repositories
from app.services.channels import ReleaseChannelConfigService
from app.services.distribution import ReleaseDistributionService, ReleaseRegionService
from app.services.downloads import DownloadStatisticService
from app.services.lifecycle import EolScheduleService, LtsVersionService
from app.services.notes import ReleaseNoteService
from app.services.packages import ReleaseArtifactService, ReleasePackageService
from app.services.promotions import ReleasePromotionService
from app.services.releases import ReleaseVersionService
from app.services.reports import ReportService
from app.services.statistics import StatisticsService
from app.services.supply_chain import (
    ArtifactChecksumService,
    ArtifactSignatureService,
    SbomPublicationService,
)
from tests.conftest import RecordingNotifier, RecordingPublisher, hours_ago, utcnow


async def _make_channel(repos: Repositories, organization_id: uuid.UUID, name: str = "c1"):
    return await repos.release_channels.create(
        ReleaseChannelConfig(
            organization_id=organization_id, name=name, channel_type=ReleaseChannelType.STABLE
        )
    )


async def _make_version(
    repos: Repositories, organization_id: uuid.UUID, *, channel_name: str, label: str
):
    channel = await _make_channel(repos, organization_id, name=channel_name)
    return await repos.release_versions.create(
        ReleaseVersion(
            organization_id=organization_id, version_label=label, release_channel_id=channel.id
        )
    )


class TestReleaseChannelConfigService:
    async def test_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReleaseChannelConfigService(repos.release_channels)
        channel = await service.create(
            organization_id, name="stable", channel_type=ReleaseChannelType.STABLE
        )
        assert channel.channel_type == "stable"


class TestReleaseVersionServiceLifecycle:
    async def test_create_publishes_and_notifies(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        channel = await _make_channel(repos, organization_id, name="c2")
        service = ReleaseVersionService(
            repos.release_versions, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        version = await service.create(
            organization_id,
            version_label="1.0.0",
            release_channel_id=channel.id,
            channel_type=ReleaseChannelType.STABLE,
        )
        assert version.status == "draft"
        assert "ReleaseCreated" in publisher.names()
        assert any(call[0] == "notify_new_release" for call in notifier.calls)

    async def test_publish_walks_full_lifecycle_and_publishes_each_event(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        channel = await _make_channel(repos, organization_id, name="c3")
        service = ReleaseVersionService(repos.release_versions, publish=publisher)
        version = await service.create(
            organization_id,
            version_label="1.1.0",
            release_channel_id=channel.id,
            channel_type=ReleaseChannelType.STABLE,
        )
        published = await service.publish(
            version, channel_type=ReleaseChannelType.STABLE, now=utcnow()
        )
        assert published.status == "published"
        assert published.released_at is not None
        names = publisher.names()
        assert "ReleaseValidated" in names
        assert "ReleaseSigned" in names
        assert "ReleasePublished" in names

    async def test_publish_lts_notifies_patch_available(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        channel = await _make_channel(repos, organization_id, name="c4")
        service = ReleaseVersionService(repos.release_versions, notifier=notifier)  # type: ignore[arg-type]
        version = await service.create(
            organization_id,
            version_label="1.2.0",
            release_channel_id=channel.id,
            channel_type=ReleaseChannelType.LTS,
        )
        await service.publish(version, channel_type=ReleaseChannelType.LTS, now=utcnow())
        assert any(call[0] == "notify_patch_available" for call in notifier.calls)

    async def test_publish_security_release_on_stable_notifies_critical_update(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        channel = await _make_channel(repos, organization_id, name="c5")
        service = ReleaseVersionService(repos.release_versions, notifier=notifier)  # type: ignore[arg-type]
        version = await service.create(
            organization_id,
            version_label="1.3.0",
            release_channel_id=channel.id,
            channel_type=ReleaseChannelType.STABLE,
            is_security_release=True,
        )
        await service.publish(version, channel_type=ReleaseChannelType.STABLE, now=utcnow())
        assert any(call[0] == "notify_critical_update" for call in notifier.calls)

    async def test_archive_after_publish(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        channel = await _make_channel(repos, organization_id, name="c6")
        service = ReleaseVersionService(repos.release_versions)
        version = await service.create(
            organization_id,
            version_label="1.4.0",
            release_channel_id=channel.id,
            channel_type=ReleaseChannelType.STABLE,
        )
        version = await service.publish(
            version, channel_type=ReleaseChannelType.STABLE, now=utcnow()
        )
        archived = await service.archive(version)
        assert archived.status == "archived"

    async def test_invalid_transition_raises(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        channel = await _make_channel(repos, organization_id, name="c7")
        service = ReleaseVersionService(repos.release_versions)
        version = await service.create(
            organization_id,
            version_label="1.5.0",
            release_channel_id=channel.id,
            channel_type=ReleaseChannelType.STABLE,
        )
        # First walk to published via publish(), then try an invalid step manually.
        version = await service.archive(
            await service.publish(version, channel_type=ReleaseChannelType.STABLE, now=utcnow())
        )
        with pytest.raises(releases_services.TransitionRefusedError):
            await service.validate(version)


class TestReleaseBuildService:
    async def test_start_and_complete_succeeded(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c8", label="2.0.0")
        service = ReleaseBuildService(repos.release_builds)
        build = await service.create(organization_id, release_version_id=version.id)
        build = await service.start(build, now=utcnow())
        completed = await service.complete(build, status="succeeded", now=utcnow())  # type: ignore[arg-type]
        assert completed.status == "succeeded"

    async def test_complete_failed_notifies(
        self, repos: Repositories, organization_id: uuid.UUID, notifier: RecordingNotifier
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c9", label="2.1.0")
        service = ReleaseBuildService(repos.release_builds, notifier=notifier)  # type: ignore[arg-type]
        build = await service.create(organization_id, release_version_id=version.id)
        build = await service.start(build, now=utcnow())
        completed = await service.complete(
            build,
            status="failed",  # type: ignore[arg-type]
            now=utcnow(),
            error_message="compile error",
            version_label="2.1.0",
        )
        assert completed.status == "failed"
        assert any(call[0] == "notify_release_failure" for call in notifier.calls)


class TestPackagesServices:
    async def test_package_and_artifact_create(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c10", label="3.0.0")
        package_service = ReleasePackageService(repos.release_packages)
        package = await package_service.create(
            organization_id,
            release_version_id=version.id,
            artifact_type=ArtifactType.CLI,
            package_format=PackageFormat.ZIP,
            name="cli-bundle",
        )
        artifact_service = ReleaseArtifactService(repos.release_artifacts)
        artifact = await artifact_service.create(
            organization_id, release_package_id=package.id, artifact_name="cli.zip"
        )
        assert artifact.artifact_name == "cli.zip"


class TestReleasePromotionService:
    async def test_promote_valid_path_completes(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c11", label="4.0.0")
        service = ReleasePromotionService(
            repos.release_promotions, publish=publisher, notifier=notifier  # type: ignore[arg-type]
        )
        promotion = await service.promote(
            organization_id,
            release_version_id=version.id,
            version_label="4.0.0",
            from_channel_type=ReleaseChannelType.CANARY,
            to_channel_type=ReleaseChannelType.STABLE,
            approved_by="qa-lead",
            now=utcnow(),
        )
        assert promotion.status == "completed"
        assert "ReleasePromoted" in publisher.names()
        assert any(call[0] == "notify_promotion_complete" for call in notifier.calls)

    async def test_promote_invalid_path_rejects(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c12", label="4.1.0")
        service = ReleasePromotionService(repos.release_promotions, publish=publisher)
        promotion = await service.promote(
            organization_id,
            release_version_id=version.id,
            version_label="4.1.0",
            from_channel_type=ReleaseChannelType.DEVELOPMENT,
            to_channel_type=ReleaseChannelType.LTS,
            approved_by="qa-lead",
            now=utcnow(),
        )
        assert promotion.status == "rejected"
        assert "ReleasePromoted" not in publisher.names()

    async def test_reject(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        version = await _make_version(repos, organization_id, channel_name="c13", label="4.2.0")
        service = ReleasePromotionService(repos.release_promotions)
        promotion = await service.create(
            organization_id,
            release_version_id=version.id,
            from_channel_type=ReleaseChannelType.CANARY,
            to_channel_type=ReleaseChannelType.STABLE,
        )
        rejected = await service.reject(promotion)
        assert rejected.status == "rejected"


class TestDistributionServices:
    async def test_distribution_create_and_complete(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c14", label="5.0.0")
        service = ReleaseDistributionService(repos.release_distributions)
        distribution = await service.create(
            organization_id,
            release_version_id=version.id,
            distribution_type=DistributionType.GLOBAL,
        )
        completed = await service.complete(distribution, now=utcnow())
        assert completed.status == "completed"

    async def test_region_create(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReleaseRegionService(repos.release_regions)
        region = await service.create(organization_id, name="EU West", region_code="eu-west")
        assert region.region_code == "eu-west"


class TestDownloadStatisticService:
    async def test_record_publishes(
        self, repos: Repositories, organization_id: uuid.UUID, publisher: RecordingPublisher
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c15", label="6.0.0")
        package = await repos.release_packages.create(
            __import__("app.models.packages", fromlist=["ReleasePackage"]).ReleasePackage(
                organization_id=organization_id,
                release_version_id=version.id,
                artifact_type=ArtifactType.SDK,
                package_format=PackageFormat.PYTHON_PACKAGE,
                name="sdk",
            )
        )
        artifact = await repos.release_artifacts.create(
            __import__("app.models.packages", fromlist=["ReleaseArtifact"]).ReleaseArtifact(
                organization_id=organization_id,
                release_package_id=package.id,
                artifact_name="sdk.whl",
            )
        )
        service = DownloadStatisticService(repos.download_statistics, publish=publisher)
        download = await service.record(
            organization_id, release_artifact_id=artifact.id, downloaded_at=utcnow()
        )
        assert download.release_artifact_id == artifact.id
        assert "ReleaseDownloaded" in publisher.names()


class TestSupplyChainServices:
    async def test_checksum_compute_and_record(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c16", label="7.0.0")
        package = await repos.release_packages.create(
            __import__("app.models.packages", fromlist=["ReleasePackage"]).ReleasePackage(
                organization_id=organization_id,
                release_version_id=version.id,
                artifact_type=ArtifactType.CLI,
                package_format=PackageFormat.ZIP,
                name="cli",
            )
        )
        artifact = await repos.release_artifacts.create(
            __import__("app.models.packages", fromlist=["ReleaseArtifact"]).ReleaseArtifact(
                organization_id=organization_id,
                release_package_id=package.id,
                artifact_name="cli.zip",
            )
        )
        checksum_service = ArtifactChecksumService(repos.artifact_checksums)
        checksum = await checksum_service.compute_and_record(
            organization_id,
            release_artifact_id=artifact.id,
            data=b"cli contents",
            algorithm=ChecksumAlgorithm.SHA256,
        )
        assert len(checksum.checksum_value) == 64

        signature_service = ArtifactSignatureService(repos.artifact_signatures)
        signature = await signature_service.record(
            organization_id,
            release_artifact_id=artifact.id,
            signature="sig-bytes",
            signed_at=utcnow(),
        )
        assert signature.signature == "sig-bytes"

        sbom_service = SbomPublicationService(repos.sbom_publications)
        sbom = await sbom_service.record(
            organization_id,
            release_version_id=version.id,
            component_count=10,
            published_at=utcnow(),
        )
        assert sbom.component_count == 10


class TestReleaseNoteService:
    async def test_record(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        version = await _make_version(repos, organization_id, channel_name="c17", label="8.0.0")
        service = ReleaseNoteService(repos.release_notes)
        note = await service.record(
            organization_id,
            release_version_id=version.id,
            note_type=ReleaseNoteType.FEATURE,
            summary="New dashboard",
        )
        assert note.summary == "New dashboard"


class TestLifecycleServices:
    async def test_lts_version_create_publishes_and_notifies(
        self,
        repos: Repositories,
        organization_id: uuid.UUID,
        publisher: RecordingPublisher,
        notifier: RecordingNotifier,
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c18", label="9.0.0")
        service = LtsVersionService(repos.lts_versions, publish=publisher, notifier=notifier)  # type: ignore[arg-type]
        lts_version = await service.create(
            organization_id,
            release_version_id=version.id,
            support_ends_at=hours_ago(-24 * 400),
            version_label="9.0.0",
        )
        assert lts_version.release_version_id == version.id
        assert "LTSReleased" in publisher.names()
        assert any(call[0] == "notify_lts_release" for call in notifier.calls)

    async def test_eol_schedule_create(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, channel_name="c19", label="9.1.0")
        service = EolScheduleService(repos.eol_schedule)
        schedule = await service.create(
            organization_id, release_version_id=version.id, eol_date=hours_ago(-24 * 200)
        )
        assert schedule.release_version_id == version.id


class TestStatisticsAndReportsServices:
    async def test_roll_up_window_is_idempotent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = StatisticsService(repos.statistics)
        window_start = utcnow()
        first = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            release_count=1,
            promotion_count=0,
            download_count=0,
            avg_release_success_rate=0.9,
        )
        second = await service.roll_up_window(
            organization_id,
            window_start=window_start,
            window_end=utcnow(),
            release_count=5,
            promotion_count=2,
            download_count=10,
            avg_release_success_rate=0.8,
        )
        assert first.id == second.id
        assert second.release_count == 5
        assert len(await service.list_range(organization_id, since=hours_ago(1))) == 1

    async def test_report_generate(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        service = ReportService(repos.reports)
        report = await service.generate(
            organization_id,
            kind=ReleaseReportKind.RELEASE,
            title="Weekly release report",
            period_start=hours_ago(1),
            period_end=utcnow(),
            row_count=5,
            now=utcnow(),
        )
        assert report.status == "completed"
        assert report.row_count == 5


class TestAuditService:
    async def test_record_and_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        service = AuditService(repos.audit)
        await service.record(
            organization_id=organization_id,
            action=ReleaseAuditAction.ADMINISTRATIVE,
            entity_type="x",
            entity_id=uuid.uuid4(),
            summary="did a thing",
            occurred_at=utcnow(),
        )
        entries = await service.list_recent(organization_id)
        assert len(entries) == 1
        assert entries[0].summary == "did a thing"
