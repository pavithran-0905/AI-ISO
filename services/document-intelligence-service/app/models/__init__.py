"""Every table this service owns.

Importing this package registers all seventeen with ``Base.metadata``,
which is what makes Alembic autogenerate see them. A model module nobody
imports is a table Alembic will happily generate a migration to *drop*.
"""

from __future__ import annotations

from app.models.document import Document, DocumentLayout, DocumentPage, DocumentVersion
from app.models.extraction import (
    DocumentClassification,
    DocumentEntity,
    DocumentForm,
    DocumentKeyValue,
    DocumentSummary,
    DocumentTable,
    DocumentTranslation,
)
from app.models.operations import (
    DocumentAudit,
    DocumentProcessingJob,
    DocumentReport,
    DocumentReview,
    DocumentStatistic,
    DocumentValidationResult,
)

__all__ = [
    "Document",
    "DocumentAudit",
    "DocumentClassification",
    "DocumentEntity",
    "DocumentForm",
    "DocumentKeyValue",
    "DocumentLayout",
    "DocumentPage",
    "DocumentProcessingJob",
    "DocumentReport",
    "DocumentReview",
    "DocumentStatistic",
    "DocumentSummary",
    "DocumentTable",
    "DocumentTranslation",
    "DocumentValidationResult",
    "DocumentVersion",
]
