"""The repository bundle the pipeline works through.

One object rather than eleven constructor arguments. The pipeline touches
most of the schema in a single run, and threading each repository through
separately makes every signature change a change to every call site --
and makes it easy to build a service missing the one repository the stage
that runs least often needs.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_core.database.tenant import TenantScope
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document import (
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


@dataclass(frozen=True, slots=True)
class Repositories:
    """Every repository this service uses, over one session."""

    documents: DocumentRepository
    versions: DocumentVersionRepository
    pages: DocumentPageRepository
    layouts: DocumentLayoutRepository
    entities: DocumentEntityRepository
    tables: DocumentTableRepository
    forms: DocumentFormRepository
    key_values: DocumentKeyValueRepository
    classifications: DocumentClassificationRepository
    summaries: DocumentSummaryRepository
    translations: DocumentTranslationRepository
    reviews: DocumentReviewRepository
    validations: DocumentValidationResultRepository
    jobs: DocumentProcessingJobRepository
    statistics: DocumentStatisticRepository
    reports: DocumentReportRepository
    audits: DocumentAuditRepository


def build_repositories(
    session: AsyncSession, *, tenant_scope: TenantScope | None = None
) -> Repositories:
    """Every repository over one session, sharing one tenant scope.

    Sharing the scope matters: a bundle where one repository was built
    without it would enforce tenant isolation everywhere except the one
    query that forgot, and that query is the leak.
    """
    return Repositories(
        documents=DocumentRepository(session, tenant_scope=tenant_scope),
        versions=DocumentVersionRepository(session, tenant_scope=tenant_scope),
        pages=DocumentPageRepository(session, tenant_scope=tenant_scope),
        layouts=DocumentLayoutRepository(session, tenant_scope=tenant_scope),
        entities=DocumentEntityRepository(session, tenant_scope=tenant_scope),
        tables=DocumentTableRepository(session, tenant_scope=tenant_scope),
        forms=DocumentFormRepository(session, tenant_scope=tenant_scope),
        key_values=DocumentKeyValueRepository(session, tenant_scope=tenant_scope),
        classifications=DocumentClassificationRepository(session, tenant_scope=tenant_scope),
        summaries=DocumentSummaryRepository(session, tenant_scope=tenant_scope),
        translations=DocumentTranslationRepository(session, tenant_scope=tenant_scope),
        reviews=DocumentReviewRepository(session, tenant_scope=tenant_scope),
        validations=DocumentValidationResultRepository(session, tenant_scope=tenant_scope),
        jobs=DocumentProcessingJobRepository(session, tenant_scope=tenant_scope),
        statistics=DocumentStatisticRepository(session, tenant_scope=tenant_scope),
        reports=DocumentReportRepository(session, tenant_scope=tenant_scope),
        audits=DocumentAuditRepository(session, tenant_scope=tenant_scope),
    )


__all__ = ["Repositories", "build_repositories"]
