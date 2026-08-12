"""Tests for the service layer against real PostgreSQL and MinIO.

Repositories, ingestion, the pipeline, review, analytics and reports. The
worker ticks are here too, because each manages its own sessions and so
cannot be exercised through the HTTP client's overridden one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from shared_core.exceptions.not_found import NotFoundError
from shared_core.exceptions.validation import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.document import Document, DocumentLayout, DocumentPage, DocumentVersion
from app.models.enums import (
    ClassificationMethod,
    DocumentCategory,
    DocumentFormat,
    DocumentStatus,
    EntityKind,
    ExtractionMethod,
    FormFieldKind,
    JobStatus,
    LayoutRegionKind,
    ProcessingStage,
    ReportFormat,
    ReportKind,
    ReportStatus,
    ReviewDecision,
    ReviewStatus,
    SummaryKind,
    ValidationOutcome,
    ValidationRuleKind,
)
from app.models.extraction import (
    DocumentClassification,
    DocumentEntity,
    DocumentKeyValue,
    DocumentSummary,
    DocumentTable,
    DocumentTranslation,
)
from app.models.operations import (
    DocumentAudit,
    DocumentProcessingJob,
    DocumentReview,
    DocumentValidationResult,
)
from app.services.analytics import AnalyticsService, ReportService, render
from app.services.bundle import Repositories, build_repositories
from app.services.ingestion import IngestionService, checksum_of, is_supported
from app.services.pipeline import STAGE_ORDER, PipelineService
from app.services.review import ReviewService
from app.services.storage import DocumentStorage
from app.workers.processing_sweep import ProcessingSweepWorker
from app.workers.retention_sweep import RetentionSweepWorker
from app.workers.review_expiry_sweep import ReviewExpirySweepWorker
from app.workers.statistics_rollup import StatisticsRollupWorker
from tests.conftest import (
    CHANGE_REQUEST,
    DEFAULT_STAGES,
    LOG_FILE,
    RecordingPublisher,
    hours_ago,
    hours_ahead,
    utcnow,
)

pytestmark = pytest.mark.asyncio


# ---- repositories --------------------------------------------------------------------


async def _document(
    repos: Repositories,
    organization_id: uuid.UUID,
    *,
    title: str = "A document",
    status: DocumentStatus = DocumentStatus.UPLOADED,
    checksum: str | None = None,
    confidence: float | None = None,
    review: bool = False,
    fmt: DocumentFormat = DocumentFormat.TXT,
    expires_at: datetime | None = None,
) -> Document:
    return await repos.documents.create(
        Document(
            organization_id=organization_id,
            title=title,
            document_format=fmt,
            status=status,
            checksum=checksum,
            overall_confidence=confidence,
            requires_review=review,
            expires_at=expires_at,
        )
    )


async def test_a_document_is_scoped_to_its_organization(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    assert await repos.documents.require_in_org(organization_id, document.id)
    with pytest.raises(NotFoundError):
        await repos.documents.require_in_org(uuid.uuid4(), document.id)


async def test_the_same_checksum_in_two_tenants_is_not_a_duplicate(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    """Telling one tenant its document exists would leak that another has it."""
    other = uuid.uuid4()
    await _document(repos, organization_id, title="Ours", checksum="sha256:x")
    await _document(repos, other, title="Theirs", checksum="sha256:x")
    ours = await repos.documents.find_by_checksum(organization_id, "sha256:x")
    theirs = await repos.documents.find_by_checksum(other, "sha256:x")
    assert ours is not None and theirs is not None
    assert ours.id != theirs.id


async def test_the_review_queue_puts_unscored_documents_first(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    """NULL confidence means nothing scored it, which is worse than a low score."""
    await _document(repos, organization_id, title="Scored", confidence=0.42, review=True)
    await _document(repos, organization_id, title="Unscored", confidence=None, review=True)
    queue = await repos.documents.list_awaiting_review(organization_id)
    assert next(document.title for document in queue) == "Unscored"


async def test_counts_group_by_status_and_format(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    await _document(repos, organization_id, status=DocumentStatus.APPROVED)
    await _document(repos, organization_id, fmt=DocumentFormat.PDF)
    assert await repos.documents.count_by_status(organization_id)
    assert await repos.documents.count_by_format(organization_id)


async def test_search_matches_title_and_filters_by_format(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    await _document(repos, organization_id, title="Change request CHG-004821")
    await _document(repos, organization_id, title="Unrelated", fmt=DocumentFormat.PDF)
    found = await repos.documents.search_in_org(organization_id, "CHG")
    assert [document.title for document in found] == ["Change request CHG-004821"]
    pdfs = await repos.documents.search_in_org(organization_id, "", formats=[DocumentFormat.PDF])
    assert [document.title for document in pdfs] == ["Unrelated"]


async def test_mark_status_updates_without_loading_the_row(
    repos: Repositories, organization_id: uuid.UUID, db_session: AsyncSession
) -> None:
    document = await _document(repos, organization_id)
    await repos.documents.mark_status(document.id, DocumentStatus.PARSING, error="none")
    await db_session.refresh(document)
    assert document.status == DocumentStatus.PARSING


async def test_expired_documents_exclude_ones_already_archived(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    """Without that, every tick re-archives and writes a fresh audit row."""
    await _document(repos, organization_id, title="Due", expires_at=hours_ago(2))
    await _document(
        repos,
        organization_id,
        title="Already archived",
        status=DocumentStatus.ARCHIVED,
        expires_at=hours_ago(2),
    )
    titles = {document.title for document in await repos.documents.list_expired(utcnow())}
    assert "Due" in titles
    assert "Already archived" not in titles


async def test_version_numbering_and_current_promotion(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    first = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=await repos.versions.next_version_number(document.id),
            content="v1",
            checksum="sha256:v1",
            is_current=True,
        )
    )
    second = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=await repos.versions.next_version_number(document.id),
            content="v2",
            checksum="sha256:v2",
            is_current=True,
        )
    )
    assert (first.version_number, second.version_number) == (1, 2)
    await repos.versions.demote_others(document.id, second.id)
    current = await repos.versions.require_current(document.id)
    assert current.id == second.id


async def test_a_document_with_no_version_raises_rather_than_returning_none(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    with pytest.raises(NotFoundError, match="no current version"):
        await repos.versions.require_current(document.id)


async def test_layout_regions_are_reached_through_their_page(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    """A region belongs to a page; duplicating the version onto it would drift."""
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    page = await repos.pages.create(
        DocumentPage(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            page_number=1,
            content="A title",
        )
    )
    await repos.layouts.create(
        DocumentLayout(
            organization_id=organization_id,
            document_id=document.id,
            document_page_id=page.id,
            region_kind=LayoutRegionKind.TITLE,
            reading_order=0,
            content="A title",
        )
    )
    assert len(await repos.layouts.list_for_page(page.id)) == 1
    assert len(await repos.layouts.list_for_version(version.id)) == 1
    assert await repos.pages.get_page(version.id, 1) is not None
    assert await repos.pages.delete_for_version(version.id) == 1


async def test_entities_are_found_by_their_normalised_value(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    for value in ("+44 20 7946 0018", "+44-20-7946-0018"):
        await repos.entities.create(
            DocumentEntity(
                organization_id=organization_id,
                document_id=document.id,
                document_version_id=version.id,
                entity_kind=EntityKind.PHONE,
                value=value,
                normalized_value="+442079460018",
                confidence=0.9,
                extraction_method=ExtractionMethod.PATTERN,
            )
        )
    assert len(await repos.entities.find_by_value(organization_id, "+442079460018")) == 2
    assert await repos.entities.count_by_kind(version.id) == {"phone": 2}
    assert await repos.entities.redact_kinds(version.id, [EntityKind.PHONE]) == 2
    assert await repos.entities.redact_kinds(version.id, []) == 0


async def test_nested_tables_are_excluded_from_the_top_level_listing(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    parent = await repos.tables.create(
        DocumentTable(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            sequence=0,
            confidence=0.9,
            extraction_method=ExtractionMethod.LAYOUT,
        )
    )
    await repos.tables.create(
        DocumentTable(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            sequence=1,
            parent_table_id=parent.id,
            confidence=0.7,
            extraction_method=ExtractionMethod.LAYOUT,
        )
    )
    assert len(await repos.tables.list_for_version(version.id)) == 1
    assert len(await repos.tables.list_children(parent.id)) == 1


async def test_correction_rate_is_none_when_nothing_was_reviewed(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    """0.0 would read as a perfect extractor."""
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    assert await repos.key_values.correction_rate(version.id) is None

    for key, value, confirmed, corrected in [
        ("risk level", "high", True, None),
        ("approved by", "R Mehta", True, "R. Mehta"),
        ("cab reference", None, False, None),
    ]:
        await repos.key_values.create(
            DocumentKeyValue(
                organization_id=organization_id,
                document_id=document.id,
                document_version_id=version.id,
                key=key,
                normalized_key=key,
                value=value,
                confidence=0.3 if value is None else 0.9,
                field_kind=FormFieldKind.TEXT,
                extraction_method=ExtractionMethod.PATTERN,
                is_confirmed=confirmed,
                corrected_value=corrected,
            )
        )
    assert await repos.key_values.correction_rate(version.id) == 0.5
    low = await repos.key_values.list_low_confidence(version.id, 0.7)
    assert [field.key for field in low] == ["cab reference"]
    assert await repos.key_values.find_by_key(version.id, "risk level") is not None


async def test_only_one_classification_stays_primary(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    keep = await repos.classifications.create(
        DocumentClassification(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            category=DocumentCategory.FORM,
            confidence=0.9,
            method=ClassificationMethod.STRUCTURE,
            is_primary=True,
        )
    )
    await repos.classifications.create(
        DocumentClassification(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            category=DocumentCategory.RUNBOOK,
            confidence=0.5,
            method=ClassificationMethod.KEYWORD,
            is_primary=True,
        )
    )
    await repos.classifications.demote_others(version.id, keep.id)
    primary = await repos.classifications.primary_for_version(version.id)
    assert primary is not None and primary.id == keep.id
    assert await repos.classifications.count_by_category(organization_id) == {"form": 1}
    assert (
        len(await repos.classifications.list_by_category(organization_id, DocumentCategory.FORM))
        == 1
    )


async def test_summaries_and_translations_are_found_by_kind_and_language(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    await repos.summaries.create(
        DocumentSummary(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            summary_kind=SummaryKind.EXECUTIVE,
            content="A summary.",
            confidence=0.8,
        )
    )
    await repos.translations.create(
        DocumentTranslation(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            source_language="en",
            target_language="fr",
            content="Un resume.",
            confidence=0.85,
        )
    )
    assert await repos.summaries.find_of_kind(version.id, SummaryKind.EXECUTIVE) is not None
    assert await repos.summaries.find_of_kind(version.id, SummaryKind.TECHNICAL) is None
    assert await repos.translations.find_in_language(version.id, "fr") is not None
    assert await repos.translations.find_in_language(version.id, "de") is None
    assert len(await repos.summaries.list_for_version(version.id)) == 1
    assert len(await repos.translations.list_for_version(version.id)) == 1


async def test_the_review_queue_sorts_undated_reviews_last(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    """An ascending sort's default NULLS FIRST would make them most urgent."""
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    for reason, due in [
        ("overdue", hours_ago(2)),
        ("no deadline", None),
        ("tomorrow", hours_ahead(24)),
    ]:
        await repos.reviews.create(
            DocumentReview(
                organization_id=organization_id,
                document_id=document.id,
                document_version_id=version.id,
                status=ReviewStatus.PENDING,
                reason=reason,
                priority=50,
                due_at=due,
            )
        )
    order = [review.reason for review in await repos.reviews.list_queue(organization_id)]
    assert order == ["overdue", "tomorrow", "no deadline"]
    assert [r.reason for r in await repos.reviews.list_overdue(utcnow())] == ["overdue"]
    assert await repos.reviews.count_by_status(organization_id) == {"pending": 3}
    with pytest.raises(NotFoundError):
        await repos.reviews.require_in_org(uuid.uuid4(), uuid.uuid4())


async def test_validation_findings_are_replaced_not_appended(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    """A stale FAILED row beside a new PASSED one never validates."""
    document = await _document(repos, organization_id)
    version = await repos.versions.create(
        DocumentVersion(
            organization_id=organization_id,
            document_id=document.id,
            version_number=1,
            content="text",
            checksum="sha256:v",
            is_current=True,
        )
    )
    await repos.validations.create(
        DocumentValidationResult(
            organization_id=organization_id,
            document_id=document.id,
            document_version_id=version.id,
            rule_kind=ValidationRuleKind.SCHEMA,
            rule_name="risk-allowed",
            outcome=ValidationOutcome.FAILED,
            message="bad",
            is_blocking=True,
        )
    )
    assert await repos.validations.has_blocking(version.id) is True
    assert await repos.validations.delete_for_version(version.id) == 1
    assert await repos.validations.has_blocking(version.id) is False


async def test_jobs_claim_only_due_work_and_only_retryable_failures(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    for status, priority, when, attempts in [
        (JobStatus.QUEUED, 10, hours_ago(1), 0),
        (JobStatus.QUEUED, 100, hours_ahead(1), 0),
        (JobStatus.FAILED, 50, hours_ago(1), 1),
        (JobStatus.FAILED, 50, hours_ago(1), 3),
    ]:
        await repos.jobs.create(
            DocumentProcessingJob(
                organization_id=organization_id,
                document_id=document.id,
                status=status,
                priority=priority,
                scheduled_at=when,
                attempts=attempts,
                max_attempts=3,
                stages=["parsing"],
            )
        )
    # Both queries are global by design -- the worker sweeps every tenant --
    # so the assertions scope to this test's own document rather than to a
    # count of every row in the database.
    claimed = await repos.jobs.claim_due(utcnow(), limit=50)
    mine = [job for job in claimed if job.document_id == document.id]
    assert [job.priority for job in mine] == [10], "only the due job should be claimed"
    retryable = [
        job
        for job in await repos.jobs.list_retryable(utcnow(), limit=50)
        if job.document_id == document.id
    ]
    assert [job.attempts for job in retryable] == [1], "an exhausted job must not retry"
    assert await repos.jobs.count_by_status()
    assert len(await repos.jobs.list_for_document(document.id)) == 4


async def test_the_audit_trail_filters_by_action_actor_and_time(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    document = await _document(repos, organization_id)
    for action, actor, when in [
        ("uploaded", "user-1", utcnow()),
        ("reviewed", "user-2", hours_ago(3)),
    ]:
        await repos.audits.create(
            DocumentAudit(
                organization_id=organization_id,
                action=action,
                entity_type="document",
                entity_id=document.id,
                occurred_at=when,
                actor_id=actor,
            )
        )
    assert len(await repos.audits.list_for_entity(document.id)) == 2
    assert len(await repos.audits.list_for_org(organization_id, action="uploaded")) == 1
    assert len(await repos.audits.list_for_org(organization_id, actor_id="user-2")) == 1
    assert len(await repos.audits.list_for_org(organization_id, since=hours_ago(1))) == 1


async def test_reports_list_by_kind_and_status(
    repos: Repositories, organization_id: uuid.UUID
) -> None:
    from app.models.operations import DocumentReport

    await repos.reports.create(
        DocumentReport(
            organization_id=organization_id,
            kind=ReportKind.ACCURACY,
            report_format=ReportFormat.JSON,
            title="Accuracy",
            status=ReportStatus.PENDING,
        )
    )
    assert len(await repos.reports.list_for_org(organization_id, kind=ReportKind.ACCURACY)) == 1
    assert len(await repos.reports.list_for_org(organization_id, kind=ReportKind.REVIEW)) == 0
    assert len(await repos.reports.list_pending()) >= 1


# ---- ingestion -----------------------------------------------------------------------


async def test_ingestion_stores_the_bytes_before_queueing_the_job(
    ingestion: IngestionService,
    storage: DocumentStorage,
    organization_id: uuid.UUID,
    publisher: RecordingPublisher,
) -> None:
    """A worker must never claim a job whose bytes are not yet readable."""
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR 4821",
        filename="cr.txt",
        content_type="text/plain",
        uploaded_by="user-1",
        tags=["cab", "cab", " "],
    )
    assert result.job is not None
    assert result.document.storage_key
    assert result.document.tags == ["cab"]
    assert (
        await storage.get(bucket=result.document.storage_bucket, key=result.document.storage_key)
        == CHANGE_REQUEST
    )
    payloads = publisher.payloads("DocumentUploaded")
    assert payloads[0]["format"] == "txt"


async def test_a_duplicate_is_recorded_and_not_reprocessed(
    ingestion: IngestionService, organization_id: uuid.UUID
) -> None:
    first = await ingestion.ingest(
        organization_id=organization_id, data=CHANGE_REQUEST, title="First", filename="a.txt"
    )
    second = await ingestion.ingest(
        organization_id=organization_id, data=CHANGE_REQUEST, title="Second", filename="b.txt"
    )
    assert second.is_duplicate is True
    assert second.will_process is False
    assert second.duplicate_of is not None
    assert second.duplicate_of.id == first.document.id


@pytest.mark.parametrize(
    ("data", "filename", "match"),
    [
        (b"", "x.txt", "empty"),
        (b"\x00\x01\x02\x03\x04\x05\x06\x07", "mystery.bin", "could not be identified"),
    ],
)
async def test_ingestion_rejects_at_the_door(
    ingestion: IngestionService,
    organization_id: uuid.UUID,
    data: bytes,
    filename: str,
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match):
        await ingestion.ingest(
            organization_id=organization_id, data=data, title="t", filename=filename
        )


async def test_an_oversized_upload_is_rejected(
    repos: Repositories, publisher: RecordingPublisher, organization_id: uuid.UUID
) -> None:
    tiny = IngestionService(
        documents=repos.documents,
        jobs=repos.jobs,
        audits=repos.audits,
        publish=publisher,
        max_bytes=10,
    )
    with pytest.raises(ValidationError, match="above the"):
        await tiny.ingest(
            organization_id=organization_id, data=CHANGE_REQUEST, title="t", filename="x.txt"
        )


async def test_requeue_raises_priority_and_records_an_audit(
    ingestion: IngestionService, repos: Repositories, organization_id: uuid.UUID
) -> None:
    result = await ingestion.ingest(
        organization_id=organization_id, data=CHANGE_REQUEST, title="CR", filename="cr.txt"
    )
    job = await ingestion.requeue(
        organization_id=organization_id,
        document_id=result.document.id,
        stages=(ProcessingStage.PARSING,),
        requested_by="user-1",
    )
    assert job.priority == 50
    actions = [audit.action for audit in await repos.audits.list_for_org(organization_id)]
    assert "requeued" in actions


async def test_checksum_and_support_helpers() -> None:
    assert checksum_of(b"abc").startswith("sha256:")
    assert is_supported(DocumentFormat.TXT) is True
    assert is_supported(DocumentFormat.UNKNOWN) is False


# ---- the pipeline --------------------------------------------------------------------


async def test_the_whole_pipeline_runs_and_stores_everything_it_found(
    ingestion: IngestionService,
    pipeline: PipelineService,
    repos: Repositories,
    organization_id: uuid.UUID,
    publisher: RecordingPublisher,
) -> None:
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR 4821",
        filename="cr.txt",
        content_type="text/plain",
        stages=DEFAULT_STAGES,
    )
    assert result.job is not None
    run = await pipeline.run(result.job, CHANGE_REQUEST)

    assert run.job.status == JobStatus.COMPLETED
    assert run.succeeded is True
    assert run.version is not None
    version = run.version

    assert len(await repos.pages.list_for_version(version.id)) >= 1
    assert await repos.layouts.list_for_version(version.id)
    assert await repos.entities.count_by_kind(version.id)
    tables = await repos.tables.list_for_version(version.id)
    assert tables[0].headers == ["System", "Risk", "Approver"]
    assert len(await repos.key_values.list_for_version(version.id)) >= 8

    labels = await repos.classifications.list_for_version(version.id)
    assert any(label.is_primary for label in labels)
    # ``==``, never ``is``: a loaded row's enum column is a plain ``str`` at
    # runtime, so identity against the enum member is always False.
    assert labels[0].category == DocumentCategory.FORM, "the template should have matched"
    assert labels[0].routed_to == "cab-queue"

    findings = await repos.validations.list_for_version(version.id)
    assert any(finding.is_blocking for finding in findings), "the blank signature should block"
    assert run.requires_review is True

    names = publisher.names()
    for expected in ("ClassificationCompleted", "ExtractionCompleted", "ValidationCompleted"):
        assert expected in names


async def test_no_document_content_reaches_the_event_bus(
    ingestion: IngestionService,
    pipeline: PipelineService,
    organization_id: uuid.UUID,
    publisher: RecordingPublisher,
) -> None:
    """A span or a payload is the easiest place to publish a corpus."""
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR",
        filename="cr.txt",
        stages=DEFAULT_STAGES,
    )
    assert result.job is not None
    await pipeline.run(result.job, CHANGE_REQUEST)
    for event in publisher.events:
        rendered = repr(event.payload)
        assert "7946 0018" not in rendered
        assert "r.mehta@example.com" not in rendered
        assert "CHG-004821" not in rendered


async def test_parsing_is_prepended_when_a_later_stage_is_asked_for_alone(
    ingestion: IngestionService, pipeline: PipelineService, organization_id: uuid.UUID
) -> None:
    """Extracting without parsing would extract from nothing and pass."""
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR",
        filename="cr.txt",
        stages=(ProcessingStage.ENTITY_EXTRACTION,),
    )
    assert result.job is not None
    run = await pipeline.run(result.job, CHANGE_REQUEST)
    stages = [outcome.stage for outcome in run.outcomes]
    assert stages[0] is ProcessingStage.PARSING
    assert ProcessingStage.ENTITY_EXTRACTION in stages


async def test_classification_runs_after_form_extraction() -> None:
    """Template matching needs the field labels form extraction produces."""
    order = list(STAGE_ORDER)
    assert order.index(ProcessingStage.FORM_EXTRACTION) < order.index(
        ProcessingStage.CLASSIFICATION
    )


async def test_a_parse_failure_stops_the_run_and_fails_the_document(
    ingestion: IngestionService,
    pipeline: PipelineService,
    repos: Repositories,
    organization_id: uuid.UUID,
    publisher: RecordingPublisher,
) -> None:
    broken = b"%PDF-1.7\nnot actually a pdf"
    result = await ingestion.ingest(
        organization_id=organization_id, data=broken, title="Broken", filename="broken.pdf"
    )
    assert result.job is not None
    run = await pipeline.run(result.job, broken)
    assert run.job.status == JobStatus.FAILED
    assert len(run.outcomes) == 1
    document = await repos.documents.require_in_org(organization_id, result.document.id)
    assert document.status == DocumentStatus.FAILED
    assert "ProcessingFailed" in publisher.names()


async def test_ocr_is_skipped_when_the_document_already_has_text(
    ingestion: IngestionService, pipeline: PipelineService, organization_id: uuid.UUID
) -> None:
    """Running OCR over a born-digital document costs seconds per page and
    reads worse than the text layer it replaces."""
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR",
        filename="cr.txt",
        stages=(ProcessingStage.PARSING, ProcessingStage.OCR),
    )
    assert result.job is not None
    run = await pipeline.run(result.job, CHANGE_REQUEST)
    ocr = next(o for o in run.outcomes if o.stage is ProcessingStage.OCR)
    assert ocr.succeeded is True
    assert ocr.detail["skipped"] is True


async def test_a_document_needing_ocr_with_no_engine_is_sent_to_review(
    ingestion: IngestionService, pipeline: PipelineService, organization_id: uuid.UUID
) -> None:
    """A stub returning empty text would make this look successfully read."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buffer, format="PNG")
    payload = buffer.getvalue()

    result = await ingestion.ingest(
        organization_id=organization_id,
        data=payload,
        title="Scan",
        filename="scan.png",
        stages=(ProcessingStage.PARSING, ProcessingStage.OCR),
    )
    assert result.job is not None
    run = await pipeline.run(result.job, payload)
    assert run.requires_review is True
    assert run.review_reason is not None
    assert "OCR" in run.review_reason


async def test_overall_confidence_is_none_when_no_stage_measured_anything(
    ingestion: IngestionService,
    pipeline: PipelineService,
    repos: Repositories,
    organization_id: uuid.UUID,
) -> None:
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=LOG_FILE,
        title="Log",
        filename="app.log",
        stages=(ProcessingStage.PARSING,),
    )
    assert result.job is not None
    await pipeline.run(result.job, LOG_FILE)
    document = await repos.documents.require_in_org(organization_id, result.document.id)
    assert document.overall_confidence is None


async def test_a_partial_run_is_recorded_as_partial(
    ingestion: IngestionService,
    repos: Repositories,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    """Neither a success nor a failure -- a re-run decision needs the difference."""
    from app.services.pipeline import PipelineConfig

    class Exploding(PipelineService):
        async def _tables_stage(self, job, parsed, version):  # type: ignore[no-untyped-def]
            raise RuntimeError("table extraction blew up")

    service = Exploding(repositories=repos, publish=publisher, config=PipelineConfig())
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR",
        filename="cr.txt",
        stages=(ProcessingStage.PARSING, ProcessingStage.TABLE_EXTRACTION),
    )
    assert result.job is not None
    run = await service.run(result.job, CHANGE_REQUEST)
    assert run.job.status == JobStatus.PARTIAL
    assert ProcessingStage.TABLE_EXTRACTION in run.failed_stages
    assert run.requires_review is True


# ---- review --------------------------------------------------------------------------


async def _reviewable(
    ingestion: IngestionService, pipeline: PipelineService, organization_id: uuid.UUID
) -> Document:
    result = await ingestion.ingest(
        organization_id=organization_id,
        data=CHANGE_REQUEST,
        title="CR 4821",
        filename="cr.txt",
        stages=DEFAULT_STAGES,
    )
    assert result.job is not None
    await pipeline.run(result.job, CHANGE_REQUEST)
    return result.document


async def test_a_review_records_corrections_beside_the_originals(
    ingestion: IngestionService,
    pipeline: PipelineService,
    review: ReviewService,
    repos: Repositories,
    organization_id: uuid.UUID,
    publisher: RecordingPublisher,
) -> None:
    """Overwriting the original destroys the only signal that measures the
    extractor."""
    document = await _reviewable(ingestion, pipeline, organization_id)
    opened = await review.open(
        organization_id=organization_id,
        document_id=document.id,
        reason="blank required signature",
        assigned_to="reviewer-1",
    )
    assert opened.status == ReviewStatus.ASSIGNED
    assert opened.due_at is not None

    await review.start(
        organization_id=organization_id, review_id=opened.id, reviewer_id="reviewer-1"
    )
    outcome = await review.complete(
        organization_id=organization_id,
        review_id=opened.id,
        reviewer_id="reviewer-1",
        decision=ReviewDecision.CORRECTED,
        corrections={"approved by": "A. Novak", "no such field": "ignored"},
        comment="Signed off.",
        annotations=[{"page": 1, "note": "signature was blank"}],
    )
    assert outcome.corrections_applied == 1
    assert outcome.document_status is DocumentStatus.APPROVED
    assert outcome.review.duration_ms is not None

    version = await repos.versions.require_current(document.id)
    corrected = [
        field
        for field in await repos.key_values.list_for_version(version.id)
        if field.corrected_value
    ]
    assert len(corrected) == 1
    assert corrected[0].value in (None, "")
    assert corrected[0].corrected_value == "A. Novak"
    assert corrected[0].corrected_by == "reviewer-1"
    assert publisher.payloads("ReviewCompleted")[0]["decision"] == "corrected"


async def test_a_review_needs_a_reason(
    ingestion: IngestionService,
    pipeline: PipelineService,
    review: ReviewService,
    organization_id: uuid.UUID,
) -> None:
    document = await _reviewable(ingestion, pipeline, organization_id)
    with pytest.raises(ValidationError, match="needs a reason"):
        await review.open(organization_id=organization_id, document_id=document.id, reason="   ")


async def test_a_corrected_decision_with_no_corrections_is_refused(
    ingestion: IngestionService,
    pipeline: PipelineService,
    review: ReviewService,
    organization_id: uuid.UUID,
) -> None:
    """It would inflate the correction rate with edits that never happened."""
    document = await _reviewable(ingestion, pipeline, organization_id)
    opened = await review.open(
        organization_id=organization_id, document_id=document.id, reason="low confidence"
    )
    with pytest.raises(ValidationError, match="at least one correction"):
        await review.complete(
            organization_id=organization_id,
            review_id=opened.id,
            reviewer_id="reviewer-1",
            decision=ReviewDecision.CORRECTED,
        )


async def test_a_completed_review_cannot_be_changed(
    ingestion: IngestionService,
    pipeline: PipelineService,
    review: ReviewService,
    organization_id: uuid.UUID,
) -> None:
    """Mutating it would rewrite the audit trail."""
    document = await _reviewable(ingestion, pipeline, organization_id)
    opened = await review.open(
        organization_id=organization_id, document_id=document.id, reason="low confidence"
    )
    await review.complete(
        organization_id=organization_id,
        review_id=opened.id,
        reviewer_id="reviewer-1",
        decision=ReviewDecision.APPROVED,
    )
    with pytest.raises(ValidationError, match="cannot be changed"):
        await review.assign(
            organization_id=organization_id, review_id=opened.id, reviewer_id="reviewer-2"
        )


async def test_reprocess_returns_the_document_to_the_start(
    ingestion: IngestionService,
    pipeline: PipelineService,
    review: ReviewService,
    repos: Repositories,
    organization_id: uuid.UUID,
) -> None:
    document = await _reviewable(ingestion, pipeline, organization_id)
    opened = await review.open(
        organization_id=organization_id, document_id=document.id, reason="extraction is wrong"
    )
    outcome = await review.complete(
        organization_id=organization_id,
        review_id=opened.id,
        reviewer_id="reviewer-1",
        decision=ReviewDecision.REPROCESS,
    )
    assert outcome.requeued is True
    assert outcome.document_status is DocumentStatus.UPLOADED
    refreshed = await repos.documents.require_in_org(organization_id, document.id)
    assert refreshed.requires_review is True


async def test_a_rejected_document_is_rejected(
    ingestion: IngestionService,
    pipeline: PipelineService,
    review: ReviewService,
    organization_id: uuid.UUID,
) -> None:
    document = await _reviewable(ingestion, pipeline, organization_id)
    opened = await review.open(
        organization_id=organization_id, document_id=document.id, reason="wrong document"
    )
    outcome = await review.complete(
        organization_id=organization_id,
        review_id=opened.id,
        reviewer_id="reviewer-1",
        decision=ReviewDecision.REJECTED,
    )
    assert outcome.document_status is DocumentStatus.REJECTED


async def test_escalation_and_the_overdue_sweep(
    ingestion: IngestionService,
    pipeline: PipelineService,
    review: ReviewService,
    repos: Repositories,
    organization_id: uuid.UUID,
    db_session: AsyncSession,
) -> None:
    """Escalated, not expired: a review nobody did is a document nobody checked."""
    document = await _reviewable(ingestion, pipeline, organization_id)
    opened = await review.open(
        organization_id=organization_id, document_id=document.id, reason="needs a lead"
    )
    escalated = await review.escalate(
        organization_id=organization_id,
        review_id=opened.id,
        escalated_to="lead-1",
        escalation_reason="unsure about the risk rating",
    )
    assert escalated.status == ReviewStatus.ESCALATED
    assert escalated.escalated_to == "lead-1"

    late = await review.open(
        organization_id=organization_id, document_id=document.id, reason="will go overdue"
    )
    late.due_at = hours_ago(2)
    await db_session.flush()
    swept = await review.expire_overdue()
    assert swept >= 1
    assert late.status == ReviewStatus.ESCALATED
    assert late.escalation_reason is not None


# ---- analytics and reports -----------------------------------------------------------


async def test_rollup_is_idempotent_for_one_window(
    analytics: AnalyticsService, repos: Repositories, organization_id: uuid.UUID
) -> None:
    """Two rows for one window double-count every document in it."""
    await _document(repos, organization_id, status=DocumentStatus.APPROVED)
    window = utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    first = await analytics.roll_up(organization_id=organization_id, window_start=window)
    again = await analytics.roll_up(organization_id=organization_id, window_start=window)
    assert first.id == again.id
    assert len(await repos.statistics.list_recent(organization_id)) == 1


async def test_a_window_nobody_reviewed_has_no_correction_rate(
    analytics: AnalyticsService, repos: Repositories, organization_id: uuid.UUID
) -> None:
    await _document(repos, organization_id)
    window = utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    row = await analytics.roll_up(organization_id=organization_id, window_start=window)
    assert row.correction_rate is None


async def test_rollup_covers_every_organization_with_documents(
    analytics: AnalyticsService, repos: Repositories, organization_id: uuid.UUID
) -> None:
    await _document(repos, organization_id)
    rows = await analytics.roll_up_all()
    assert any(row.organization_id == organization_id for row in rows)


@pytest.mark.parametrize("kind", list(ReportKind))
async def test_every_report_kind_generates(
    reports: ReportService,
    analytics: AnalyticsService,
    repos: Repositories,
    organization_id: uuid.UUID,
    kind: ReportKind,
) -> None:
    await _document(repos, organization_id, status=DocumentStatus.APPROVED)
    window = utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    await analytics.roll_up(organization_id=organization_id, window_start=window)
    report = await reports.request(organization_id=organization_id, kind=kind)
    await reports.generate(report)
    assert report.status == ReportStatus.COMPLETED
    assert report.content["kind"] == str(kind)


@pytest.mark.parametrize("fmt", list(ReportFormat))
async def test_every_report_format_renders(
    reports: ReportService, organization_id: uuid.UUID, fmt: ReportFormat
) -> None:
    report = await reports.request(
        organization_id=organization_id, kind=ReportKind.ACCURACY, report_format=fmt
    )
    await reports.generate(report)
    assert render(report)


async def test_report_html_escapes_its_values(
    reports: ReportService, organization_id: uuid.UUID
) -> None:
    """Report content includes titles that came from user-chosen filenames."""
    report = await reports.request(
        organization_id=organization_id,
        kind=ReportKind.ACCURACY,
        report_format=ReportFormat.HTML,
        title="<script>alert(1)</script>",
    )
    await reports.generate(report)
    rendered = render(report)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


async def test_a_report_that_cannot_be_built_records_the_reason(
    reports: ReportService, organization_id: uuid.UUID
) -> None:
    report = await reports.request(organization_id=organization_id, kind=ReportKind.PROCESSING)
    report.kind = "not-a-kind"  # type: ignore[assignment]
    await reports.generate(report)
    assert report.status == ReportStatus.FAILED
    assert report.error


# ---- workers -------------------------------------------------------------------------


async def test_the_processing_sweep_runs_a_queued_job(
    db_session_factory: async_sessionmaker[AsyncSession],
    storage: DocumentStorage,
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    """Exercised against the real session factory: claiming manages its own
    transactions, so the HTTP client's overridden session cannot test it."""
    async with db_session_factory() as session:
        repos = build_repositories(session)
        ingestion = IngestionService(
            documents=repos.documents,
            jobs=repos.jobs,
            audits=repos.audits,
            publish=publisher,
            max_bytes=1024 * 1024,
            storage=storage,
        )
        result = await ingestion.ingest(
            organization_id=organization_id,
            data=CHANGE_REQUEST,
            title="CR",
            filename="cr.txt",
            stages=DEFAULT_STAGES,
        )
        await session.commit()
        document_id = result.document.id

    worker = ProcessingSweepWorker(
        db_session_factory, publish_event=publisher, storage=storage, batch_size=50
    )
    assert await worker.tick() >= 1

    async with db_session_factory() as session:
        repos = build_repositories(session)
        document = await repos.documents.require_in_org(organization_id, document_id)
        assert document.status != DocumentStatus.UPLOADED
        version = await repos.versions.require_current(document_id)
        assert await repos.key_values.list_for_version(version.id)


async def test_the_processing_sweep_records_a_failure_rather_than_raising(
    db_session_factory: async_sessionmaker[AsyncSession],
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    """No storage configured, so the worker cannot read any bytes."""
    async with db_session_factory() as session:
        repos = build_repositories(session)
        document = await _document(repos, organization_id)
        job = await repos.jobs.create(
            DocumentProcessingJob(
                organization_id=organization_id,
                document_id=document.id,
                status=JobStatus.QUEUED,
                scheduled_at=hours_ago(1),
                stages=["parsing"],
            )
        )
        await session.commit()
        job_id = job.id

    worker = ProcessingSweepWorker(
        db_session_factory, publish_event=publisher, storage=None, batch_size=50
    )
    # Nothing succeeds without a store, and the failure is recorded on the
    # job rather than raised out of the sweep.
    assert await worker.tick() == 0

    async with db_session_factory() as session:
        repos = build_repositories(session)
        failed = await repos.jobs.get_by_id(job_id)
        assert failed is not None
        assert failed.status == JobStatus.FAILED
        assert failed.error


async def test_an_empty_queue_is_a_no_op(
    db_session_factory: async_sessionmaker[AsyncSession], publisher: RecordingPublisher
) -> None:
    worker = ProcessingSweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() == 0


async def test_the_review_expiry_sweep_escalates(
    db_session_factory: async_sessionmaker[AsyncSession],
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    async with db_session_factory() as session:
        repos = build_repositories(session)
        document = await _document(repos, organization_id)
        version = await repos.versions.create(
            DocumentVersion(
                organization_id=organization_id,
                document_id=document.id,
                version_number=1,
                content="text",
                checksum="sha256:v",
                is_current=True,
            )
        )
        await repos.reviews.create(
            DocumentReview(
                organization_id=organization_id,
                document_id=document.id,
                document_version_id=version.id,
                status=ReviewStatus.PENDING,
                reason="overdue",
                due_at=hours_ago(2),
            )
        )
        await session.commit()

    worker = ReviewExpirySweepWorker(db_session_factory, publish_event=publisher)
    assert await worker.tick() >= 1


async def test_the_statistics_rollup_worker_writes_a_window(
    db_session_factory: async_sessionmaker[AsyncSession], organization_id: uuid.UUID
) -> None:
    async with db_session_factory() as session:
        repos = build_repositories(session)
        await _document(repos, organization_id)
        await session.commit()

    assert await StatisticsRollupWorker(db_session_factory).tick() >= 1


async def test_the_retention_sweep_archives_and_requeues(
    db_session_factory: async_sessionmaker[AsyncSession],
    publisher: RecordingPublisher,
    organization_id: uuid.UUID,
) -> None:
    """Archived rather than deleted, and stalled documents requeued rather
    than failed: an interrupted run is not a document defect."""
    async with db_session_factory() as session:
        repos = build_repositories(session)
        await _document(repos, organization_id, title="Expired", expires_at=hours_ago(2))
        stalled = await _document(
            repos, organization_id, title="Stalled", status=DocumentStatus.PARSING
        )
        await session.commit()
        stalled_id = stalled.id

    worker = RetentionSweepWorker(db_session_factory, publish_event=publisher, stall_minutes=0)
    archived, recovered = await worker.tick()
    assert archived >= 1
    assert recovered >= 1
    assert "DocumentArchived" in publisher.names()

    async with db_session_factory() as session:
        repos = build_repositories(session)
        document = await repos.documents.require_in_org(organization_id, stalled_id)
        assert document.status == DocumentStatus.UPLOADED
        assert await repos.jobs.list_for_document(stalled_id)


async def test_every_worker_run_job_entry_point_is_callable(
    db_session_factory: async_sessionmaker[AsyncSession], publisher: RecordingPublisher
) -> None:
    """``run_job`` is what the scheduler actually calls."""
    for worker in (
        ProcessingSweepWorker(db_session_factory, publish_event=publisher),
        ReviewExpirySweepWorker(db_session_factory, publish_event=publisher),
        StatisticsRollupWorker(db_session_factory),
        RetentionSweepWorker(db_session_factory, publish_event=publisher),
    ):
        await worker.run_job(object())


# ---- storage ------------------------------------------------------------------------


async def test_storage_keys_are_scoped_by_organization(
    storage: DocumentStorage, organization_id: uuid.UUID
) -> None:
    document_id = uuid.uuid4()
    key = storage.key_for(organization_id, document_id, 1)
    assert key.startswith(f"{organization_id!s}/")
    assert str(document_id) in key


async def test_storage_round_trips_and_deletes(
    storage: DocumentStorage, organization_id: uuid.UUID
) -> None:
    document_id = uuid.uuid4()
    stored = await storage.put(
        organization_id=organization_id,
        document_id=document_id,
        data=CHANGE_REQUEST,
        content_type="text/plain",
    )
    assert stored.byte_size == len(CHANGE_REQUEST)
    assert await storage.get(bucket=stored.bucket, key=stored.key) == CHANGE_REQUEST
    assert await storage.delete(bucket=stored.bucket, key=stored.key) is True


async def test_reading_a_document_with_no_stored_location_says_so(
    storage: DocumentStorage,
) -> None:
    from shared_core.exceptions.dependency import DependencyError

    with pytest.raises(DependencyError, match="no stored object location"):
        await storage.get(bucket=None, key=None)


async def test_deleting_nothing_is_not_an_error(storage: DocumentStorage) -> None:
    assert await storage.delete(bucket=None, key=None) is False
    assert await storage.delete(bucket=storage.bucket, key="never/existed") is True
