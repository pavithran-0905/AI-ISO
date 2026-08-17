"""Quality gate definitions and evaluation.

Publishes ``QualityGatePassed``/``QualityGateFailed`` on every
evaluation. ``QualityGateFailed`` is the one event this build fans
into a notification (Quality Gate Failed) via ``NotifyingPublisher``.
"""

from __future__ import annotations

from uuid import UUID

from app.events.domain_events import QualityGateFailedEvent, QualityGatePassedEvent
from app.models.enums import QualityGateStatus, QualityGateType
from app.models.quality_gates import QualityGate
from app.quality_gates.engine import evaluate_gate
from app.repositories.quality_gates import QualityGateRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "testing-quality-framework"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class QualityGateService:
    def __init__(
        self, repo: QualityGateRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def create(
        self, organization_id: UUID, *, name: str, gate_type: QualityGateType, threshold: float
    ) -> QualityGate:
        return await self._repo.create(
            QualityGate(
                organization_id=organization_id, name=name, gate_type=gate_type, threshold=threshold
            )
        )

    async def evaluate(
        self, gate: QualityGate, *, value: float, higher_is_better: bool = True, detail: str = ""
    ) -> QualityGate:
        status = evaluate_gate(
            value=value, threshold=gate.threshold, higher_is_better=higher_is_better
        )
        gate.status = status
        gate.detail = detail
        gate = await self._repo.update(gate)

        if status == QualityGateStatus.PASSED:
            await self._publish(
                QualityGatePassedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=gate.organization_id,
                    payload={"quality_gate_id": str(gate.id), "gate_type": str(gate.gate_type)},
                )
            )
        else:
            await self._publish(
                QualityGateFailedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=gate.organization_id,
                    payload={"quality_gate_id": str(gate.id), "gate_type": str(gate.gate_type)},
                )
            )
        return gate


__all__ = ["QualityGateService"]
