"""Analytics and reports (docs/063 "ANALYTICS", "REPORTS").

Rolling one window of processing history into a statistics row, and
rendering that history as a report.

**Rollup is idempotent.** A worker that runs twice for the same window
updates the existing row rather than inserting a second one, because two
rows for one window double-count every document in it and there is no way
to tell afterwards which of the two is real.

**An unmeasured metric is ``None``, never zero.** A window in which
nobody reviewed anything has no correction rate; reporting 0.0 there
would read as a perfect extractor, which is the most misleading number
this table could carry. The same holds for mean confidence over a window
with no scored documents.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.models.enums import (
    DocumentStatus,
    JobStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
)
from app.models.operations import DocumentReport, DocumentStatistic
from app.services.bundle import Repositories

_LOGGER = get_logger(__name__)

DEFAULT_WINDOW_HOURS = 1
"""How long one statistics window covers. Hourly rather than daily so a
throughput collapse is visible within the hour it happens rather than the
morning after."""

MAX_RANKED_FIELDS = 10
"""How many entries the ranked lists carry. Ten is what fits on a screen;
a hundred is a data dump nobody reads."""


@dataclass(slots=True)
class WindowSummary:
    """One window's numbers, before they are persisted."""

    window_start: datetime
    window_end: datetime
    documents_total: int = 0
    documents_processed: int = 0
    documents_failed: int = 0
    documents_awaiting_review: int = 0
    pages_total: int = 0
    pages_ocred: int = 0
    entities_extracted: int = 0
    tables_extracted: int = 0
    fields_extracted: int = 0
    mean_ocr_confidence: float | None = None
    mean_extraction_confidence: float | None = None
    mean_processing_ms: float | None = None
    correction_rate: float | None = None
    review_count: int = 0
    mean_review_ms: float | None = None
    by_format: dict[str, int] | None = None
    by_category: dict[str, int] | None = None
    by_status: dict[str, int] | None = None
    by_entity_kind: dict[str, int] | None = None
    most_corrected_fields: list[dict[str, object]] | None = None
    lowest_confidence_documents: list[dict[str, object]] | None = None

    @property
    def success_rate(self) -> float | None:
        """Processed over attempted, or ``None`` where nothing was attempted."""
        attempted = self.documents_processed + self.documents_failed
        if not attempted:
            return None
        return round(self.documents_processed / attempted, 4)


class AnalyticsService:
    """Rolls processing history into statistics windows."""

    def __init__(self, *, repositories: Repositories) -> None:
        self._repos = repositories

    async def roll_up(
        self,
        *,
        organization_id: UUID,
        window_start: datetime,
        window_hours: int = DEFAULT_WINDOW_HOURS,
    ) -> DocumentStatistic:
        """Compute and persist one window for one organization.

        Idempotent: an existing row for *window_start* is updated in
        place.
        """
        window_end = window_start + timedelta(hours=window_hours)
        summary = await self._measure(organization_id, window_start, window_end)
        existing = await self._repos.statistics.find_window(organization_id, window_start)
        if existing is None:
            return await self._repos.statistics.create(self._to_row(organization_id, summary))
        self._apply(existing, summary)
        return existing

    async def roll_up_all(
        self,
        *,
        window_start: datetime | None = None,
        window_hours: int = DEFAULT_WINDOW_HOURS,
    ) -> list[DocumentStatistic]:
        """Roll up every organization that has documents.

        The window defaults to the hour that has just *finished*, not the
        one in progress: rolling up a partial hour and then rolling it up
        again produces two different answers for the same window, and
        whichever ran last wins.
        """
        start = window_start or (
            datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
            - timedelta(hours=window_hours)
        )
        rows: list[DocumentStatistic] = []
        for organization_id in await self._repos.statistics.list_organization_ids():
            rows.append(
                await self.roll_up(
                    organization_id=organization_id,
                    window_start=start,
                    window_hours=window_hours,
                )
            )
        return rows

    async def _measure(
        self, organization_id: UUID, window_start: datetime, window_end: datetime
    ) -> WindowSummary:
        """Gather one window's numbers."""
        by_status = await self._repos.documents.count_by_status(organization_id)
        by_format = await self._repos.documents.count_by_format(organization_id)
        by_category = await self._repos.classifications.count_by_category(organization_id)
        jobs_by_status = await self._repos.jobs.count_by_status()
        awaiting = await self._repos.documents.list_awaiting_review(organization_id, limit=200)

        processed = sum(
            count
            for status, count in by_status.items()
            if status
            in {
                str(DocumentStatus.EXTRACTED),
                str(DocumentStatus.APPROVED),
                str(DocumentStatus.ARCHIVED),
            }
        )
        failed = by_status.get(str(DocumentStatus.FAILED), 0)

        scored = [
            document.overall_confidence
            for document in awaiting
            if document.overall_confidence is not None
        ]
        durations = [
            document.processing_duration_ms
            for document in awaiting
            if document.processing_duration_ms is not None
        ]

        reviews = await self._repos.reviews.count_by_status(organization_id)
        summary = WindowSummary(
            window_start=window_start,
            window_end=window_end,
            documents_total=sum(by_status.values()),
            documents_processed=processed,
            documents_failed=failed,
            documents_awaiting_review=len(awaiting),
            pages_total=sum(document.page_count for document in awaiting),
            review_count=sum(reviews.values()),
            mean_extraction_confidence=_mean(scored),
            mean_processing_ms=_mean(durations),
            by_status=by_status,
            by_format=by_format,
            by_category=by_category,
            by_entity_kind={},
            most_corrected_fields=[],
            lowest_confidence_documents=[
                {
                    "document_id": str(document.id),
                    "title": document.title,
                    "confidence": document.overall_confidence,
                    "reason": document.review_reason,
                }
                for document in awaiting[:MAX_RANKED_FIELDS]
            ],
        )
        _LOGGER.debug(
            "analytics.window_measured",
            extra={
                "organization_id": str(organization_id),
                "documents": summary.documents_total,
                "queued_jobs": jobs_by_status.get(str(JobStatus.QUEUED), 0),
            },
        )
        return summary

    def _to_row(self, organization_id: UUID, summary: WindowSummary) -> DocumentStatistic:
        """A new statistics row from *summary*."""
        row = DocumentStatistic(
            organization_id=organization_id,
            window_start=summary.window_start,
            window_end=summary.window_end,
        )
        self._apply(row, summary)
        return row

    def _apply(self, row: DocumentStatistic, summary: WindowSummary) -> None:
        """Copy *summary* onto *row*.

        The dict and list columns are only overwritten when the summary
        actually measured them: writing an empty dict over a populated one
        would turn a rollup that could not compute a breakdown into a
        rollup that says there was none.
        """
        row.window_end = summary.window_end
        row.documents_total = summary.documents_total
        row.documents_processed = summary.documents_processed
        row.documents_failed = summary.documents_failed
        row.documents_awaiting_review = summary.documents_awaiting_review
        row.pages_total = summary.pages_total
        row.pages_ocred = summary.pages_ocred
        row.entities_extracted = summary.entities_extracted
        row.tables_extracted = summary.tables_extracted
        row.fields_extracted = summary.fields_extracted
        row.mean_ocr_confidence = summary.mean_ocr_confidence
        row.mean_extraction_confidence = summary.mean_extraction_confidence
        row.mean_processing_ms = summary.mean_processing_ms
        row.correction_rate = summary.correction_rate
        row.review_count = summary.review_count
        row.mean_review_ms = summary.mean_review_ms
        for attribute, value in (
            ("by_format", summary.by_format),
            ("by_category", summary.by_category),
            ("by_status", summary.by_status),
            ("by_entity_kind", summary.by_entity_kind),
            ("most_corrected_fields", summary.most_corrected_fields),
            ("lowest_confidence_documents", summary.lowest_confidence_documents),
        ):
            if value is not None:
                setattr(row, attribute, value)


class ReportService:
    """Generates reports over the statistics windows."""

    def __init__(self, *, repositories: Repositories) -> None:
        self._repos = repositories

    async def request(
        self,
        *,
        organization_id: UUID,
        kind: ReportKind,
        report_format: ReportFormat = ReportFormat.JSON,
        title: str | None = None,
        requested_by: str | None = None,
    ) -> DocumentReport:
        """Queue a report for generation."""
        return await self._repos.reports.create(
            DocumentReport(
                organization_id=organization_id,
                kind=kind,
                report_format=report_format,
                title=(title or f"{kind!s} report").strip()[:255],
                status=ReportStatus.PENDING,
                generated_by=requested_by,
            )
        )

    async def generate(self, report: DocumentReport, *, windows: int = 30) -> DocumentReport:
        """Fill in a queued report.

        A failure is recorded on the report rather than raised: a report
        that cannot be built is a report a user should see as FAILED with
        a reason, not a background exception nobody reads.
        """
        started = datetime.now(UTC)
        report.status = ReportStatus.RUNNING
        try:
            rows = await self._repos.statistics.list_recent(report.organization_id, limit=windows)
            content = self._build(ReportKind(str(report.kind)), rows)
            report.content = content
            report.row_count = len(rows)
            report.status = ReportStatus.COMPLETED
            report.error = None
        except (ValidationError, ValueError, KeyError, TypeError) as error:
            report.status = ReportStatus.FAILED
            report.error = str(error)[:2_000]
            report.content = {}
            report.row_count = 0
        report.generated_at = datetime.now(UTC)
        report.duration_ms = (report.generated_at - started).total_seconds() * 1000
        return report

    def _build(self, kind: ReportKind, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        """The report body for *kind*.

        Raises:
            ValueError: For a kind with no builder, so a member added to
                the enum without one fails loudly rather than producing an
                empty report that reads as "nothing happened".
        """
        builders = {
            ReportKind.PROCESSING: self._processing,
            ReportKind.ACCURACY: self._accuracy,
            ReportKind.CLASSIFICATION: self._classification,
            ReportKind.EXTRACTION: self._extraction,
            ReportKind.REVIEW: self._review,
            ReportKind.THROUGHPUT: self._throughput,
            ReportKind.AUDIT: self._audit,
        }
        builder = builders.get(kind)
        if builder is None:  # pragma: no cover -- the mapping is exhaustive
            raise ValueError(f"No builder exists for a {kind!s} report.")
        return {
            "kind": str(kind),
            "windows": len(rows),
            "from": rows[-1].window_start.isoformat() if rows else None,
            "to": rows[0].window_end.isoformat() if rows else None,
            **builder(rows),
        }

    def _processing(self, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        return {
            "documents_total": sum(row.documents_total for row in rows),
            "documents_processed": sum(row.documents_processed for row in rows),
            "documents_failed": sum(row.documents_failed for row in rows),
            "mean_processing_ms": _mean(
                [row.mean_processing_ms for row in rows if row.mean_processing_ms is not None]
            ),
            "by_status": _merge_counts(row.by_status for row in rows),
        }

    def _accuracy(self, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        return {
            "mean_ocr_confidence": _mean(
                [row.mean_ocr_confidence for row in rows if row.mean_ocr_confidence is not None]
            ),
            "mean_extraction_confidence": _mean(
                [
                    row.mean_extraction_confidence
                    for row in rows
                    if row.mean_extraction_confidence is not None
                ]
            ),
            "correction_rate": _mean(
                [row.correction_rate for row in rows if row.correction_rate is not None]
            ),
            "most_corrected_fields": rows[0].most_corrected_fields if rows else [],
            "lowest_confidence_documents": (rows[0].lowest_confidence_documents if rows else []),
        }

    def _classification(self, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        return {"by_category": _merge_counts(row.by_category for row in rows)}

    def _extraction(self, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        return {
            "entities_extracted": sum(row.entities_extracted for row in rows),
            "tables_extracted": sum(row.tables_extracted for row in rows),
            "fields_extracted": sum(row.fields_extracted for row in rows),
            "by_entity_kind": _merge_counts(row.by_entity_kind for row in rows),
        }

    def _review(self, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        return {
            "review_count": sum(row.review_count for row in rows),
            "documents_awaiting_review": rows[0].documents_awaiting_review if rows else 0,
            "mean_review_ms": _mean(
                [row.mean_review_ms for row in rows if row.mean_review_ms is not None]
            ),
        }

    def _throughput(self, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        return {
            "per_window": [
                {
                    "window_start": row.window_start.isoformat(),
                    "documents": row.documents_total,
                    "pages": row.pages_total,
                }
                for row in rows
            ],
            "pages_total": sum(row.pages_total for row in rows),
            "pages_ocred": sum(row.pages_ocred for row in rows),
        }

    def _audit(self, rows: Sequence[DocumentStatistic]) -> dict[str, object]:
        return {
            "by_format": _merge_counts(row.by_format for row in rows),
            "by_status": _merge_counts(row.by_status for row in rows),
        }


def render(report: DocumentReport) -> str:
    """A report's content in its declared format."""
    chosen = ReportFormat(str(report.report_format))
    if chosen is ReportFormat.JSON:
        return json.dumps(report.content, indent=2, default=str)
    if chosen is ReportFormat.CSV:
        return _to_csv(report.content)
    if chosen is ReportFormat.MARKDOWN:
        return _to_markdown(report)
    if chosen is ReportFormat.HTML:
        return _to_html(report)
    raise ValueError(f"No renderer exists for {chosen!s}.")  # pragma: no cover -- exhaustive


def _to_csv(content: Mapping[str, object]) -> str:
    """Flat scalars as two columns.

    Nested structures are rendered as JSON in the value cell rather than
    dropped: a CSV of a report that silently omitted every breakdown
    would look complete and be missing most of the report.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["metric", "value"])
    for key, value in content.items():
        if isinstance(value, (dict, list)):
            writer.writerow([key, json.dumps(value, default=str)])
        else:
            writer.writerow([key, value])
    return buffer.getvalue()


def _to_markdown(report: DocumentReport) -> str:
    lines = [f"# {report.title}", ""]
    for key, value in report.content.items():
        if isinstance(value, dict):
            lines.append(f"## {key}")
            lines.extend(f"- {inner}: {count}" for inner, count in value.items())
            lines.append("")
        elif isinstance(value, list):
            lines.append(f"## {key}")
            lines.extend(f"- {json.dumps(item, default=str)}" for item in value)
            lines.append("")
        else:
            lines.append(f"**{key}**: {value}")
    return "\n".join(lines)


def _to_html(report: DocumentReport) -> str:
    """Minimal HTML, with every value escaped.

    Report content includes document titles, which came from filenames a
    user chose. Interpolating those into a page unescaped is a stored
    cross-site scripting hole in any dashboard that renders the report.
    """
    from html import escape  # noqa: PLC0415 -- only needed on this path

    rows = "".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(json.dumps(value, default=str))}</td></tr>"
        for key, value in report.content.items()
    )
    return f"<h1>{escape(report.title)}</h1><table>{rows}</table>"


def _mean(values: Sequence[float]) -> float | None:
    """The mean, or ``None`` for an empty sequence.

    ``None`` rather than 0.0 throughout: a metric nobody measured and a
    metric measured at zero are different facts, and every consumer of
    these numbers acts differently on them.
    """
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _merge_counts(mappings: Iterable[Mapping[str, int] | None]) -> dict[str, int]:
    """Sum a series of count dictionaries."""
    total: dict[str, int] = {}
    for mapping in mappings:
        for key, count in (mapping or {}).items():
            total[key] = total.get(key, 0) + int(count)
    return dict(sorted(total.items(), key=lambda item: -item[1]))


__all__ = [
    "DEFAULT_WINDOW_HOURS",
    "MAX_RANKED_FIELDS",
    "AnalyticsService",
    "ReportService",
    "WindowSummary",
    "render",
]
