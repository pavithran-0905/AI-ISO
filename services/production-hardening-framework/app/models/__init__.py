"""Import every model so ``Base.metadata`` sees all 16 tables."""

from __future__ import annotations

from app.models.certificates import CertificateInventoryEntry
from app.models.certification import ProductionCertification
from app.models.compliance import ComplianceResult
from app.models.hardening_definitions import HardeningProfile
from app.models.hardening_execution import HardeningResult, HardeningRun
from app.models.readiness import DisasterRecoveryCheck, OperationalReadiness
from app.models.reporting import HardeningAudit, HardeningReport, HardeningStatistic
from app.models.runtime_protection import RuntimeProtectionEvent
from app.models.security_findings import SecurityFinding
from app.models.supply_chain import SbomCatalog, SignedArtifact
from app.models.vulnerabilities import VulnerabilityScan

__all__ = [
    "CertificateInventoryEntry",
    "ComplianceResult",
    "DisasterRecoveryCheck",
    "HardeningAudit",
    "HardeningProfile",
    "HardeningReport",
    "HardeningResult",
    "HardeningRun",
    "HardeningStatistic",
    "OperationalReadiness",
    "ProductionCertification",
    "RuntimeProtectionEvent",
    "SbomCatalog",
    "SecurityFinding",
    "SignedArtifact",
    "VulnerabilityScan",
]
