"""Security finding recording."""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import SecurityIssueDetectedEvent
from app.models.enums import FindingSeverity, HardeningTargetType
from app.models.security_findings import SecurityFinding
from app.repositories.security_findings import SecurityFindingRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "production-hardening-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class SecurityFindingService:
    def __init__(
        self, repo: SecurityFindingRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def record(
        self,
        organization_id: UUID,
        *,
        target_type: HardeningTargetType,
        severity: FindingSeverity,
        title: str,
        detail: str = "",
    ) -> SecurityFinding:
        finding = await self._repo.create(
            SecurityFinding(
                organization_id=organization_id,
                target_type=target_type,
                severity=severity,
                title=title,
                detail=detail,
            )
        )
        await self._publish(
            SecurityIssueDetectedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=organization_id,
                payload={"security_finding_id": str(finding.id), "severity": str(severity)},
            )
        )
        return finding


__all__ = ["SecurityFindingService"]
