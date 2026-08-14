"""Tests for app.edge_ai.engine: AI model promotion and inference
target selection."""

from __future__ import annotations

from app.edge_ai.engine import PromotionRefusal, select_inference_target, validate_promotion
from app.models.enums import AiModelStatus, InferenceTarget


class TestValidatePromotion:
    def test_staged_can_be_promoted(self) -> None:
        decision = validate_promotion(AiModelStatus.STAGED)
        assert decision.is_allowed

    def test_deployed_cannot_be_promoted(self) -> None:
        decision = validate_promotion(AiModelStatus.DEPLOYED)
        assert not decision.is_allowed
        assert decision.refusal == PromotionRefusal.NOT_STAGED

    def test_failed_cannot_be_promoted(self) -> None:
        decision = validate_promotion(AiModelStatus.FAILED)
        assert not decision.is_allowed

    def test_string_status_value_is_compared_safely(self) -> None:
        decision = validate_promotion("staged")  # type: ignore[arg-type]
        assert decision.is_allowed


class TestSelectInferenceTarget:
    def test_requires_gpu_selects_gpu_even_without_availability(self) -> None:
        target = select_inference_target(gpu_available=False, model_requires_gpu=True)
        assert target == InferenceTarget.GPU

    def test_no_requirement_but_gpu_available_selects_gpu(self) -> None:
        target = select_inference_target(gpu_available=True, model_requires_gpu=False)
        assert target == InferenceTarget.GPU

    def test_no_requirement_and_no_gpu_selects_cpu(self) -> None:
        target = select_inference_target(gpu_available=False, model_requires_gpu=False)
        assert target == InferenceTarget.CPU
