"""Vulnerability scan result recording.

Publishes ``VulnerabilityDetected`` on every recorded scan result; the
subset with ``CRITICAL`` severity is what ``NotifyingPublisher`` fans
into the Critical Vulnerability notification.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.events.domain_events import VulnerabilityDetectedEvent
from app.models.enums import FindingSeverity, VulnerabilityScanType
from app.models.vulnerabilities import VulnerabilityScan
from app.repositories.vulnerabilities import VulnerabilityScanRepository
from app.types import EventPublisher
from app.vulnerability.engine import is_remediation_overdue

_SOURCE_SERVICE = "production-hardening-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class VulnerabilityScanService:
    def __init__(
        self, repo: VulnerabilityScanRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def record(
        self,
        organization_id: UUID,
        *,
        scan_type: VulnerabilityScanType,
        severity: FindingSeverity,
        package_name: str,
        package_version: str = "",
        cve_id: str = "",
    ) -> VulnerabilityScan:
        scan = await self._repo.create(
            VulnerabilityScan(
                organization_id=organization_id,
                scan_type=scan_type,
                cve_id=cve_id,
                severity=severity,
                package_name=package_name,
                package_version=package_version,
            )
        )
        await self._publish(
            VulnerabilityDetectedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={
                    "vulnerability_scan_id": str(scan.id),
                    "severity": str(severity),
                    "package_name": package_name,
                    "cve_id": cve_id,
                },
            )
        )
        return scan

    async def list_overdue(
        self, organization_id: UUID, *, now: datetime
    ) -> Sequence[VulnerabilityScan]:
        """Every still-open vulnerability that has passed its own
        severity-scaled remediation SLA."""
        open_scans = await self._repo.list_open(organization_id)
        return [
            scan
            for scan in open_scans
            if is_remediation_overdue(
                detected_at=scan.created_at, now=now, severity=FindingSeverity(scan.severity)
            )
        ]


__all__ = ["VulnerabilityScanService"]
