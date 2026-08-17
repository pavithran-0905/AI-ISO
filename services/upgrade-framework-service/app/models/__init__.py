"""Imports every model so ``Base.metadata`` sees every table."""

from __future__ import annotations

from app.models.compatibility import CompatibilityMatrixEntry
from app.models.migrations import ConfigurationMigration, MigrationHistory, PluginMigration
from app.models.releases import ReleaseChannel, ReleaseVersion
from app.models.reporting import UpgradeAudit, UpgradeReport, UpgradeStatistic
from app.models.rollback import RollbackHistory
from app.models.upgrade import (
    UpgradeDependency,
    UpgradeHistory,
    UpgradeJob,
    UpgradePlan,
    UpgradeResult,
    UpgradeTarget,
)
from app.models.verification import VerificationResult

__all__ = [
    "CompatibilityMatrixEntry",
    "ConfigurationMigration",
    "MigrationHistory",
    "PluginMigration",
    "ReleaseChannel",
    "ReleaseVersion",
    "RollbackHistory",
    "UpgradeAudit",
    "UpgradeDependency",
    "UpgradeHistory",
    "UpgradeJob",
    "UpgradePlan",
    "UpgradeReport",
    "UpgradeResult",
    "UpgradeStatistic",
    "UpgradeTarget",
    "VerificationResult",
]
