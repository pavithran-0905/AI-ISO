"""Repositories for every persisted model in this service."""

from app.repositories.document import (
    MAX_PAGE_SIZE,
    DocumentLayoutRepository,
    DocumentPageRepository,
    DocumentRepository,
    DocumentVersionRepository,
)
from app.repositories.extraction import (
    DocumentClassificationRepository,
    DocumentEntityRepository,
    DocumentFormRepository,
    DocumentKeyValueRepository,
    DocumentSummaryRepository,
    DocumentTableRepository,
    DocumentTranslationRepository,
)
from app.repositories.operations import (
    DocumentAuditRepository,
    DocumentProcessingJobRepository,
    DocumentReportRepository,
    DocumentReviewRepository,
    DocumentStatisticRepository,
    DocumentValidationResultRepository,
)

__all__ = [
    "MAX_PAGE_SIZE",
    "DocumentAuditRepository",
    "DocumentClassificationRepository",
    "DocumentEntityRepository",
    "DocumentFormRepository",
    "DocumentKeyValueRepository",
    "DocumentLayoutRepository",
    "DocumentPageRepository",
    "DocumentProcessingJobRepository",
    "DocumentReportRepository",
    "DocumentRepository",
    "DocumentReviewRepository",
    "DocumentStatisticRepository",
    "DocumentSummaryRepository",
    "DocumentTableRepository",
    "DocumentTranslationRepository",
    "DocumentValidationResultRepository",
    "DocumentVersionRepository",
]
