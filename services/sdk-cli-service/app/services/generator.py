"""Code generation orchestration.

Wires ``app.generator.engine``'s pure model/enum rendering into a
single call producing every requested artifact -- the one place
``POST /sdk/generate`` (and any future caller) asks for a batch of
typed models rendered in one language.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.generator.engine import FieldSpec, render_model
from app.models.enums import SdkLanguage


@dataclass(frozen=True, slots=True)
class ModelSpec:
    class_name: str
    fields: Sequence[FieldSpec]


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    class_name: str
    source: str


class CodeGenerationService:
    """Renders every requested model for one SDK language."""

    def generate_models(
        self, language: SdkLanguage, model_specs: Sequence[ModelSpec]
    ) -> list[GeneratedArtifact]:
        """Render every model in *model_specs*.

        Raises:
            ValueError: If *model_specs* is empty, or via
                ``render_model`` on an unsupported language or an
                invalid model/field name.
        """
        if not model_specs:
            raise ValueError("model_specs must not be empty.")
        return [
            GeneratedArtifact(
                class_name=spec.class_name,
                source=render_model(language, spec.class_name, spec.fields),
            )
            for spec in model_specs
        ]


__all__ = ["CodeGenerationService", "GeneratedArtifact", "ModelSpec"]
