"""The service layer: ingestion, the pipeline, review, analytics and reports."""

from app.services.analytics import AnalyticsService, ReportService, WindowSummary, render
from app.services.bundle import Repositories, build_repositories
from app.services.ingestion import DEFAULT_STAGES, IngestionResult, IngestionService
from app.services.pipeline import (
    STAGE_ORDER,
    PipelineConfig,
    PipelineResult,
    PipelineService,
    StageOutcome,
)
from app.services.review import ReviewOutcome, ReviewService

__all__ = [
    "DEFAULT_STAGES",
    "STAGE_ORDER",
    "AnalyticsService",
    "IngestionResult",
    "IngestionService",
    "PipelineConfig",
    "PipelineResult",
    "PipelineService",
    "ReportService",
    "Repositories",
    "ReviewOutcome",
    "ReviewService",
    "StageOutcome",
    "WindowSummary",
    "build_repositories",
    "render",
]
