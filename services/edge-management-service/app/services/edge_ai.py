"""Edge AI model deployment and promotion.

Wires ``app.edge_ai.engine``'s pure promotion decision and inference
target selection onto the repository that persists model deployments,
publishing ``AIModelDeployed``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.edge_ai.engine import PromotionDecision, select_inference_target, validate_promotion
from app.events.domain_events import AIModelDeployedEvent
from app.models.enums import AiModelStatus
from app.models.operations import EdgeAiModel
from app.repositories.operations import EdgeAiModelRepository
from app.types import EventPublisher

_SOURCE_SERVICE = "edge-management-service"


async def _noop_publisher(event: object) -> None:
    """The default publisher for callers with no messaging backend wired
    up (a hand-verification script, for one)."""


class PromotionRefusedError(Exception):
    def __init__(self, decision: PromotionDecision) -> None:
        super().__init__(decision.detail)
        self.decision = decision


class EdgeAiModelService:
    def __init__(
        self, repo: EdgeAiModelRepository, *, publish: EventPublisher = _noop_publisher
    ) -> None:
        self._repo = repo
        self._publish = publish

    async def stage_model(
        self,
        organization_id: UUID,
        *,
        device_id: UUID,
        name: str,
        version_label: str,
        gpu_available: bool,
        model_requires_gpu: bool,
        rollback_of_id: UUID | None = None,
    ) -> EdgeAiModel:
        target = select_inference_target(
            gpu_available=gpu_available, model_requires_gpu=model_requires_gpu
        )
        return await self._repo.create(
            EdgeAiModel(
                organization_id=organization_id,
                device_id=device_id,
                rollback_of_id=rollback_of_id,
                name=name,
                version_label=version_label,
                status=AiModelStatus.STAGED,
                inference_target=target,
            )
        )

    async def promote(self, model: EdgeAiModel, *, now: datetime) -> EdgeAiModel:
        """Promote *model* from ``STAGED`` to ``DEPLOYED``.

        Raises:
            PromotionRefusedError: If *model* is not currently ``STAGED``.
        """
        decision = validate_promotion(model.status)
        if not decision.is_allowed:
            raise PromotionRefusedError(decision)

        model.status = AiModelStatus.DEPLOYED
        model.deployed_at = now
        await self._repo.update(model)
        await self._publish(
            AIModelDeployedEvent(
                source_service=_SOURCE_SERVICE,
                organization_id=model.organization_id,
                payload={
                    "device_id": str(model.device_id),
                    "model_id": str(model.id),
                    "name": model.name,
                    "version": model.version_label,
                    "status": str(model.status),
                },
            )
        )
        return model

    async def roll_back(self, model: EdgeAiModel) -> EdgeAiModel:
        model.status = AiModelStatus.ROLLED_BACK
        return await self._repo.update(model)


__all__ = ["EdgeAiModelService", "PromotionRefusedError"]
