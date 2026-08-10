"""Every repository this service uses, re-exported for one import surface."""

from __future__ import annotations

from app.repositories.analytics import (
    PromptAuditRepository,
    PromptOptimizationRepository,
    PromptReportRepository,
    PromptStatisticRepository,
)
from app.repositories.governance import (
    PromptApprovalRepository,
    PromptReviewRepository,
    PromptSecurityScanRepository,
)
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.repositories.template import (
    PromptCategoryRepository,
    PromptTagRepository,
    PromptTemplateRepository,
    PromptVariableRepository,
)
from app.repositories.testing import (
    PromptAbTestRepository,
    PromptExecutionRepository,
    PromptTestRepository,
    PromptTestResultRepository,
)

__all__ = [
    "PromptAbTestRepository",
    "PromptApprovalRepository",
    "PromptAuditRepository",
    "PromptCategoryRepository",
    "PromptExecutionRepository",
    "PromptOptimizationRepository",
    "PromptReportRepository",
    "PromptRepository",
    "PromptReviewRepository",
    "PromptSecurityScanRepository",
    "PromptStatisticRepository",
    "PromptTagRepository",
    "PromptTemplateRepository",
    "PromptTestRepository",
    "PromptTestResultRepository",
    "PromptVariableRepository",
    "PromptVersionRepository",
]
