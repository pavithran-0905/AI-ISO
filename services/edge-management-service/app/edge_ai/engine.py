"""Edge AI model deployment decisions.

**A model deployment is never promoted from `STAGED` to `DEPLOYED`
without an explicit promotion decision.** Staging a model is a
reversible, low-risk step; deploying it to run inference is not, and the
two must never be conflated into one implicit action.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import AiModelStatus, InferenceTarget


class PromotionRefusal:
    NOT_STAGED = "not_staged"


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    is_allowed: bool
    refusal: str | None
    detail: str


def validate_promotion(current_status: AiModelStatus) -> PromotionDecision:
    """Whether a model may be promoted from ``STAGED`` to ``DEPLOYED``.

    Only a model actually in ``STAGED`` may be promoted -- an already-
    ``DEPLOYED`` model is promoted by *replacing* it with a new
    deployment (a new row referencing this one via ``rollback_of_id`` if
    it is later rolled back), never by re-promoting the same row.
    """
    current_status = AiModelStatus(current_status)
    if current_status != AiModelStatus.STAGED:
        return PromotionDecision(
            is_allowed=False,
            refusal=PromotionRefusal.NOT_STAGED,
            detail=f"A model in status {current_status.value} cannot be promoted; only a "
            "staged model can be.",
        )
    return PromotionDecision(is_allowed=True, refusal=None, detail="Promotion is allowed.")


def select_inference_target(*, gpu_available: bool, model_requires_gpu: bool) -> InferenceTarget:
    """Which inference target a model should run on.

    A model that requires a GPU on a device with none is still assigned
    ``GPU`` -- the mismatch is a deployment-time validation concern for
    the caller to catch explicitly, not something this pure decision
    should paper over by silently falling back to CPU inference the
    model was never validated to run correctly on.
    """
    if model_requires_gpu:
        return InferenceTarget.GPU
    return InferenceTarget.GPU if gpu_available else InferenceTarget.CPU


__all__ = ["PromotionDecision", "PromotionRefusal", "select_inference_target", "validate_promotion"]
