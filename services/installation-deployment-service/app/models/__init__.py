"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.configuration import ConfigurationProfile
from app.models.deployment import (
    DeploymentArtifact,
    DeploymentHistory,
    DeploymentInventory,
    DeploymentJob,
    DeploymentProfile,
    DeploymentStatusRecord,
    DeploymentTarget,
    DeploymentVersion,
)
from app.models.installation import InstallationLog, InstallationSession
from app.models.reporting import DeploymentAudit, DeploymentReport, DeploymentStatistic
from app.models.secrets_tls import GeneratedSecret, TlsCertificate
from app.models.upgrade_rollback import RollbackHistory, UpgradeHistory
from app.models.validation import DependencyCheck, PreflightResult
from app.models.verification import VerificationResult

__all__ = [
    "ConfigurationProfile",
    "DependencyCheck",
    "DeploymentArtifact",
    "DeploymentAudit",
    "DeploymentHistory",
    "DeploymentInventory",
    "DeploymentJob",
    "DeploymentProfile",
    "DeploymentReport",
    "DeploymentStatistic",
    "DeploymentStatusRecord",
    "DeploymentTarget",
    "DeploymentVersion",
    "GeneratedSecret",
    "InstallationLog",
    "InstallationSession",
    "PreflightResult",
    "RollbackHistory",
    "TlsCertificate",
    "UpgradeHistory",
    "VerificationResult",
]
