"""The repository bundle every route works through.

One object rather than eighteen constructor arguments, all sharing one
tenant scope: a bundle where one repository was built without it would
enforce tenant isolation everywhere except the one query that forgot,
and that query is the leak.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.builds import ReleaseBuildRepository
from app.repositories.channels import ReleaseChannelConfigRepository
from app.repositories.distribution import ReleaseDistributionRepository, ReleaseRegionRepository
from app.repositories.downloads import DownloadStatisticRepository
from app.repositories.lifecycle import EolScheduleRepository, LtsVersionRepository
from app.repositories.notes import ReleaseNoteRepository
from app.repositories.packages import ReleaseArtifactRepository, ReleasePackageRepository
from app.repositories.promotions import ReleasePromotionRepository
from app.repositories.releases import ReleaseVersionRepository
from app.repositories.reporting import (
    ReleaseAuditRepository,
    ReleaseReportRepository,
    ReleaseStatisticRepository,
)
from app.repositories.supply_chain import (
    ArtifactChecksumRepository,
    ArtifactSignatureRepository,
    SbomPublicationRepository,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    release_channels: ReleaseChannelConfigRepository
    release_versions: ReleaseVersionRepository
    release_builds: ReleaseBuildRepository

    release_packages: ReleasePackageRepository
    release_artifacts: ReleaseArtifactRepository

    release_promotions: ReleasePromotionRepository

    release_distributions: ReleaseDistributionRepository
    release_regions: ReleaseRegionRepository

    download_statistics: DownloadStatisticRepository

    artifact_checksums: ArtifactChecksumRepository
    artifact_signatures: ArtifactSignatureRepository
    sbom_publications: SbomPublicationRepository

    release_notes: ReleaseNoteRepository

    lts_versions: LtsVersionRepository
    eol_schedule: EolScheduleRepository

    statistics: ReleaseStatisticRepository
    reports: ReleaseReportRepository
    audit: ReleaseAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope."""
    return Repositories(
        release_channels=ReleaseChannelConfigRepository(session, tenant_scope=tenant_scope),
        release_versions=ReleaseVersionRepository(session, tenant_scope=tenant_scope),
        release_builds=ReleaseBuildRepository(session, tenant_scope=tenant_scope),
        release_packages=ReleasePackageRepository(session, tenant_scope=tenant_scope),
        release_artifacts=ReleaseArtifactRepository(session, tenant_scope=tenant_scope),
        release_promotions=ReleasePromotionRepository(session, tenant_scope=tenant_scope),
        release_distributions=ReleaseDistributionRepository(session, tenant_scope=tenant_scope),
        release_regions=ReleaseRegionRepository(session, tenant_scope=tenant_scope),
        download_statistics=DownloadStatisticRepository(session, tenant_scope=tenant_scope),
        artifact_checksums=ArtifactChecksumRepository(session, tenant_scope=tenant_scope),
        artifact_signatures=ArtifactSignatureRepository(session, tenant_scope=tenant_scope),
        sbom_publications=SbomPublicationRepository(session, tenant_scope=tenant_scope),
        release_notes=ReleaseNoteRepository(session, tenant_scope=tenant_scope),
        lts_versions=LtsVersionRepository(session, tenant_scope=tenant_scope),
        eol_schedule=EolScheduleRepository(session, tenant_scope=tenant_scope),
        statistics=ReleaseStatisticRepository(session, tenant_scope=tenant_scope),
        reports=ReleaseReportRepository(session, tenant_scope=tenant_scope),
        audit=ReleaseAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
