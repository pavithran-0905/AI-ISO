"""Repository tests, against real PostgreSQL, exercising every custom
method (not the generic CRUD ``BaseRepository`` already provides)."""

from __future__ import annotations

import uuid

from app.models.builds import ReleaseBuild
from app.models.channels import ReleaseChannelConfig
from app.models.distribution import ReleaseDistribution, ReleaseRegion
from app.models.downloads import DownloadStatistic
from app.models.enums import (
    ArtifactType,
    BuildStatus,
    ChecksumAlgorithm,
    DistributionType,
    PackageFormat,
    PromotionStatus,
    ReleaseAuditAction,
    ReleaseChannelType,
    ReleaseNoteType,
    ReleaseReportKind,
    ReportStatus,
)
from app.models.lifecycle import EolSchedule, LtsVersion
from app.models.notes import ReleaseNote
from app.models.packages import ReleaseArtifact, ReleasePackage
from app.models.promotions import ReleasePromotion
from app.models.releases import ReleaseVersion
from app.models.reporting import ReleaseAudit, ReleaseReport, ReleaseStatistic
from app.models.supply_chain import ArtifactChecksum, ArtifactSignature, SbomPublication
from app.services.bundle import Repositories
from tests.conftest import hours_ago, utcnow


async def _make_channel(
    repos: Repositories, organization_id: uuid.UUID, name: str = "stable-channel"
):
    return await repos.release_channels.create(
        ReleaseChannelConfig(
            organization_id=organization_id, name=name, channel_type=ReleaseChannelType.STABLE
        )
    )


async def _make_version(repos: Repositories, organization_id: uuid.UUID, label: str = "1.0.0"):
    channel = await _make_channel(repos, organization_id, name=f"channel-{label}")
    return await repos.release_versions.create(
        ReleaseVersion(
            organization_id=organization_id, version_label=label, release_channel_id=channel.id
        )
    )


class TestChannelsRepository:
    async def test_find_by_type_and_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await _make_channel(repos, organization_id, name="c1")
        found = await repos.release_channels.find_by_type(
            organization_id, channel_type=ReleaseChannelType.STABLE
        )
        assert found is not None
        rows = await repos.release_channels.list_all(organization_id)
        assert len(rows) == 1


class TestReleasesRepository:
    async def test_find_by_label_and_list_all(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await _make_version(repos, organization_id, label="2.0.0")
        found = await repos.release_versions.find_by_label(organization_id, version_label="2.0.0")
        assert found is not None
        rows = await repos.release_versions.list_all(organization_id)
        assert len(rows) == 1
        org_ids = await repos.release_versions.list_organization_ids()
        assert organization_id in org_ids


class TestBuildsRepository:
    async def test_list_for_version_recent_running_org_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, label="3.0.0")
        await repos.release_builds.create(
            ReleaseBuild(
                organization_id=organization_id,
                release_version_id=version.id,
                status=BuildStatus.RUNNING,
            )
        )
        for_version = await repos.release_builds.list_for_version(version.id)
        assert len(for_version) == 1
        recent = await repos.release_builds.list_recent(organization_id)
        assert len(recent) == 1
        running = await repos.release_builds.list_running(organization_id)
        assert len(running) == 1
        org_ids = await repos.release_builds.list_organization_ids()
        assert organization_id in org_ids


class TestPackagesRepositories:
    async def test_package_and_artifact_lists(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, label="4.0.0")
        package = await repos.release_packages.create(
            ReleasePackage(
                organization_id=organization_id,
                release_version_id=version.id,
                artifact_type=ArtifactType.BACKEND,
                package_format=PackageFormat.TAR_GZ,
                name="backend-bundle",
            )
        )
        await repos.release_artifacts.create(
            ReleaseArtifact(
                organization_id=organization_id,
                release_package_id=package.id,
                artifact_name="backend.tar.gz",
            )
        )
        for_version = await repos.release_packages.list_for_version(version.id)
        assert len(for_version) == 1
        package_rows = await repos.release_packages.list_all(organization_id)
        assert len(package_rows) == 1
        for_package = await repos.release_artifacts.list_for_package(package.id)
        assert len(for_package) == 1
        artifact_rows = await repos.release_artifacts.list_all(organization_id)
        assert len(artifact_rows) == 1


class TestPromotionsRepository:
    async def test_list_all_by_status_org_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, label="5.0.0")
        await repos.release_promotions.create(
            ReleasePromotion(
                organization_id=organization_id,
                release_version_id=version.id,
                from_channel_type=ReleaseChannelType.CANARY,
                to_channel_type=ReleaseChannelType.STABLE,
                status=PromotionStatus.PENDING,
            )
        )
        rows = await repos.release_promotions.list_all(organization_id)
        assert len(rows) == 1
        pending = await repos.release_promotions.list_by_status(
            organization_id, status=PromotionStatus.PENDING
        )
        assert len(pending) == 1
        org_ids = await repos.release_promotions.list_organization_ids()
        assert organization_id in org_ids


class TestDistributionRepositories:
    async def test_distribution_and_region_lists(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, label="6.0.0")
        await repos.release_distributions.create(
            ReleaseDistribution(
                organization_id=organization_id,
                release_version_id=version.id,
                distribution_type=DistributionType.GLOBAL,
            )
        )
        await repos.release_regions.create(
            ReleaseRegion(organization_id=organization_id, name="US East", region_code="us-east")
        )
        for_version = await repos.release_distributions.list_for_version(version.id)
        assert len(for_version) == 1
        dist_rows = await repos.release_distributions.list_all(organization_id)
        assert len(dist_rows) == 1
        region_rows = await repos.release_regions.list_all(organization_id)
        assert len(region_rows) == 1


class TestDownloadsRepository:
    async def test_list_for_artifact_recent_org_ids(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, label="7.0.0")
        package = await repos.release_packages.create(
            ReleasePackage(
                organization_id=organization_id,
                release_version_id=version.id,
                artifact_type=ArtifactType.CLI,
                package_format=PackageFormat.ZIP,
                name="cli-bundle",
            )
        )
        artifact = await repos.release_artifacts.create(
            ReleaseArtifact(
                organization_id=organization_id,
                release_package_id=package.id,
                artifact_name="cli.zip",
            )
        )
        await repos.download_statistics.create(
            DownloadStatistic(
                organization_id=organization_id,
                release_artifact_id=artifact.id,
                downloaded_at=utcnow(),
            )
        )
        for_artifact = await repos.download_statistics.list_for_artifact(artifact.id)
        assert len(for_artifact) == 1
        recent = await repos.download_statistics.list_recent(organization_id)
        assert len(recent) == 1
        org_ids = await repos.download_statistics.list_organization_ids()
        assert organization_id in org_ids


class TestSupplyChainRepositories:
    async def test_checksum_signature_sbom_lists(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        version = await _make_version(repos, organization_id, label="8.0.0")
        package = await repos.release_packages.create(
            ReleasePackage(
                organization_id=organization_id,
                release_version_id=version.id,
                artifact_type=ArtifactType.SDK,
                package_format=PackageFormat.PYTHON_PACKAGE,
                name="sdk-bundle",
            )
        )
        artifact = await repos.release_artifacts.create(
            ReleaseArtifact(
                organization_id=organization_id,
                release_package_id=package.id,
                artifact_name="sdk.whl",
            )
        )
        await repos.artifact_checksums.create(
            ArtifactChecksum(
                organization_id=organization_id,
                release_artifact_id=artifact.id,
                algorithm=ChecksumAlgorithm.SHA256,
                checksum_value="deadbeef",
            )
        )
        await repos.artifact_signatures.create(
            ArtifactSignature(
                organization_id=organization_id,
                release_artifact_id=artifact.id,
                signature="signature-bytes",
                signed_at=utcnow(),
            )
        )
        await repos.sbom_publications.create(
            SbomPublication(
                organization_id=organization_id,
                release_version_id=version.id,
                component_count=42,
                published_at=utcnow(),
            )
        )
        checksum_rows = await repos.artifact_checksums.list_for_artifact(artifact.id)
        assert len(checksum_rows) == 1
        signature_rows = await repos.artifact_signatures.list_for_artifact(artifact.id)
        assert len(signature_rows) == 1
        sbom_for_version = await repos.sbom_publications.list_for_version(version.id)
        assert len(sbom_for_version) == 1
        sbom_rows = await repos.sbom_publications.list_all(organization_id)
        assert len(sbom_rows) == 1


class TestNotesRepository:
    async def test_list_for_version(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        version = await _make_version(repos, organization_id, label="9.0.0")
        await repos.release_notes.create(
            ReleaseNote(
                organization_id=organization_id,
                release_version_id=version.id,
                note_type=ReleaseNoteType.FEATURE,
                summary="Added new dashboard",
            )
        )
        rows = await repos.release_notes.list_for_version(version.id)
        assert len(rows) == 1


class TestLifecycleRepositories:
    async def test_lts_and_eol_lists(self, repos: Repositories, organization_id: uuid.UUID) -> None:
        version = await _make_version(repos, organization_id, label="10.0.0")
        await repos.lts_versions.create(
            LtsVersion(
                organization_id=organization_id,
                release_version_id=version.id,
                support_ends_at=hours_ago(-24),
            )
        )
        await repos.eol_schedule.create(
            EolSchedule(
                organization_id=organization_id,
                release_version_id=version.id,
                eol_date=hours_ago(-48),
            )
        )
        lts_rows = await repos.lts_versions.list_all(organization_id)
        assert len(lts_rows) == 1
        active_rows = await repos.lts_versions.list_active(organization_id)
        assert len(active_rows) == 1
        lts_org_ids = await repos.lts_versions.list_organization_ids()
        assert organization_id in lts_org_ids
        eol_rows = await repos.eol_schedule.list_all(organization_id)
        assert len(eol_rows) == 1
        eol_org_ids = await repos.eol_schedule.list_organization_ids()
        assert organization_id in eol_org_ids


class TestReportingRepositories:
    async def test_statistic_find_and_range(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        window_start = hours_ago(1)
        await repos.statistics.create(
            ReleaseStatistic(
                organization_id=organization_id,
                window_start=window_start,
                window_end=utcnow(),
                release_count=2,
                promotion_count=1,
                download_count=10,
                avg_release_success_rate=0.9,
            )
        )
        found = await repos.statistics.find_window(organization_id, window_start=window_start)
        assert found is not None
        rows = await repos.statistics.list_range(organization_id, since=hours_ago(2))
        assert len(rows) == 1

    async def test_report_list_recent(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        await repos.reports.create(
            ReleaseReport(
                organization_id=organization_id,
                kind=ReleaseReportKind.RELEASE,
                title="Weekly release report",
                status=ReportStatus.COMPLETED,
                period_start=hours_ago(1),
                period_end=utcnow(),
            )
        )
        rows = await repos.reports.list_recent(organization_id)
        assert len(rows) == 1
        by_kind = await repos.reports.list_recent(organization_id, kind=ReleaseReportKind.RELEASE)
        assert len(by_kind) == 1

    async def test_audit_list_recent_and_for_entity(
        self, repos: Repositories, organization_id: uuid.UUID
    ) -> None:
        entity_id = uuid.uuid4()
        await repos.audit.create(
            ReleaseAudit(
                organization_id=organization_id,
                action=ReleaseAuditAction.RELEASE_CREATION,
                entity_type="release_version",
                entity_id=entity_id,
                summary="created a release",
                occurred_at=utcnow(),
            )
        )
        rows = await repos.audit.list_recent(organization_id)
        assert len(rows) == 1
        for_entity = await repos.audit.list_for_entity("release_version", entity_id)
        assert len(for_entity) == 1
