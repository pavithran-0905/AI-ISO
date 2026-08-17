"""Import every model so ``Base.metadata`` sees all 18 tables."""

from __future__ import annotations

from app.models.builds import ReleaseBuild
from app.models.channels import ReleaseChannelConfig
from app.models.distribution import ReleaseDistribution, ReleaseRegion
from app.models.downloads import DownloadStatistic
from app.models.lifecycle import EolSchedule, LtsVersion
from app.models.notes import ReleaseNote
from app.models.packages import ReleaseArtifact, ReleasePackage
from app.models.promotions import ReleasePromotion
from app.models.releases import ReleaseVersion
from app.models.reporting import ReleaseAudit, ReleaseReport, ReleaseStatistic
from app.models.supply_chain import ArtifactChecksum, ArtifactSignature, SbomPublication

__all__ = [
    "ArtifactChecksum",
    "ArtifactSignature",
    "DownloadStatistic",
    "EolSchedule",
    "LtsVersion",
    "ReleaseArtifact",
    "ReleaseAudit",
    "ReleaseBuild",
    "ReleaseChannelConfig",
    "ReleaseDistribution",
    "ReleaseNote",
    "ReleasePackage",
    "ReleasePromotion",
    "ReleaseRegion",
    "ReleaseReport",
    "ReleaseStatistic",
    "ReleaseVersion",
    "SbomPublication",
]
