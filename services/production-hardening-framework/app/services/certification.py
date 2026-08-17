"""Production certification: risk-scored grant decisions and
revocation.

**Risk score is always computed here**, from the same three rates
(hardening, compliance, operational readiness) the caller measured --
never trusted as a caller-supplied number, so a route cannot grant an
unjustified certification.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from app.certification.engine import compute_risk_score, should_grant
from app.events.domain_events import CertificationGrantedEvent, CertificationRevokedEvent
from app.models.certification import ProductionCertification
from app.models.enums import CertificationStatus
from app.repositories.certification import ProductionCertificationRepository
from app.services.notifications import HardeningNotifier
from app.types import EventPublisher

_SOURCE_SERVICE = "production-hardening-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class ProductionCertificationService:
    def __init__(
        self,
        repo: ProductionCertificationRepository,
        *,
        publish: EventPublisher = _noop_publisher,
        notifier: HardeningNotifier | None = None,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._notifier = notifier

    async def evaluate_and_create(
        self,
        organization_id: UUID,
        *,
        name: str,
        hardening_rate: float,
        compliance_rate: float,
        readiness_rate: float,
        risk_threshold: float,
        now: datetime,
        validity_days: int = 365,
    ) -> ProductionCertification:
        risk_score = compute_risk_score(
            hardening_rate=hardening_rate,
            compliance_rate=compliance_rate,
            readiness_rate=readiness_rate,
        )
        granted = should_grant(risk_score, threshold=risk_threshold)
        certification = await self._repo.create(
            ProductionCertification(
                organization_id=organization_id,
                name=name,
                status=CertificationStatus.GRANTED if granted else CertificationStatus.PENDING,
                risk_score=risk_score,
                granted_at=now if granted else None,
                expires_at=_add_days(now, validity_days) if granted else None,
            )
        )
        if granted:
            await self._publish(
                CertificationGrantedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=organization_id,
                    payload={"production_certification_id": str(certification.id), "name": name},
                )
            )
            if self._notifier is not None:
                await self._notifier.notify_certification_granted(name=name, risk_score=risk_score)
        return certification

    async def revoke(
        self, certification: ProductionCertification, *, reason: str
    ) -> ProductionCertification:
        certification.status = CertificationStatus.REVOKED
        certification = await self._repo.update(certification)
        await self._publish(
            CertificationRevokedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=certification.organization_id,
                payload={
                    "production_certification_id": str(certification.id),
                    "name": certification.name,
                    "reason": reason,
                },
            )
        )
        return certification


def _add_days(now: datetime, days: int) -> datetime:
    return now + timedelta(days=days)


__all__ = ["ProductionCertificationService"]
