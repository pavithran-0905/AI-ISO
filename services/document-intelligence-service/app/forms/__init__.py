"""Form and key-value extraction."""

from app.forms.extractor import (
    FieldRule,
    FormConfig,
    FormExtractionResult,
    FormField,
    FormTemplate,
    extract_fields,
    extract_key_values,
    merge_pages,
    normalize_label,
)

__all__ = [
    "FieldRule",
    "FormConfig",
    "FormExtractionResult",
    "FormField",
    "FormTemplate",
    "extract_fields",
    "extract_key_values",
    "merge_pages",
    "normalize_label",
]
