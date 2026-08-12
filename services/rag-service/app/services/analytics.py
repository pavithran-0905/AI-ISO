"""Analytics (docs/062 "ANALYTICS & REPORTING", "EVALUATION").

Three things that look similar and are not: **statistics** (what happened
in a window, rolled up on a timer), **reports** (a rendered answer to one
question, generated on request), and **evaluation** (how good retrieval
actually was, measured against human judgement).

**Nothing here fabricates a number it does not have.** A window with no
feedback reports ``search_accuracy`` as ``None``, not ``0.0``; a metric
with nothing to measure reports itself unmeasurable rather than zero. The
two are opposite conclusions -- one says retrieval is broken, the other
says nobody has looked -- and a dashboard that renders them the same way
sends people to fix a system that is fine, or leaves them content with
one that is not.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from shared_core.exceptions.validation import ValidationError
from shared_core.logging.logger import get_logger

from app.evaluation.metrics import MetricResult, evaluate_retrieval, f1
from app.events.rag_events import EvaluationCompletedEvent
from app.models.analytics import RagReport, RagStatistic
from app.models.enums import (
    DocumentStatus,
    IndexStatus,
    ReportFormat,
    ReportKind,
    ReportStatus,
    RetrievalOutcome,
)
from app.repositories.analytics import (
    IndexingJobRepository,
    KnowledgeSourceRepository,
    RagAuditRepository,
    RagReportRepository,
    RagStatisticRepository,
)
from app.repositories.document import DocumentChunkRepository, DocumentRepository
from app.repositories.embedding import EmbeddingVectorRepository
from app.repositories.retrieval import (
    RetrievalFeedbackRepository,
    RetrievalQueryRepository,
    RetrievalResultRepository,
)
from app.types import EventPublisher

logger = get_logger("app.services.analytics")

_SOURCE_SERVICE = "rag-service"

DEFAULT_WINDOW_HOURS = 24
BYTES_PER_DIMENSION = 4
"""pgvector stores a ``vector(n)`` as ``n`` 4-byte floats plus a small
header. Used to estimate index size without asking PostgreSQL for a table
size, which would report the whole table including every other tenant's
rows -- a per-tenant threshold computed from a shared total is not a
per-tenant threshold at all."""

EMBEDDING_HEADER_BYTES = 8


@dataclass(slots=True)
class EvaluationSummary:
    """What one evaluation run measured."""

    queries_evaluated: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    unmeasurable: list[str] = field(default_factory=list)
    """Metrics that had nothing to compute over. Named rather than
    silently omitted, because "we did not measure recall" and "recall was
    zero" are different reports."""

    @property
    def is_measurable(self) -> bool:
        return self.queries_evaluated > 0

    @property
    def precision(self) -> float | None:
        return self.metrics.get("precision")


class AnalyticsService:
    """Rolls up statistics, generates reports, and evaluates retrieval."""

    def __init__(
        self,
        documents: DocumentRepository,
        chunks: DocumentChunkRepository,
        vectors: EmbeddingVectorRepository,
        queries: RetrievalQueryRepository,
        results: RetrievalResultRepository,
        feedback: RetrievalFeedbackRepository,
        jobs: IndexingJobRepository,
        sources: KnowledgeSourceRepository,
        statistics: RagStatisticRepository,
        reports: RagReportRepository,
        audit: RagAuditRepository,
        *,
        publish_event: EventPublisher,
        embedding_dimensions: int = 1_536,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._vectors = vectors
        self._queries = queries
        self._results = results
        self._feedback = feedback
        self._jobs = jobs
        self._sources = sources
        self._statistics = statistics
        self._reports = reports
        self._audit = audit
        self._publish_event = publish_event
        self._dimensions = embedding_dimensions

    # -- statistics ---------------------------------------------------------

    async def compute_statistics(
        self,
        organization_id: UUID,
        *,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> RagStatistic:
        """Roll up one window for one organization.

        Raises:
            ValidationError: If the window ends before it starts. A
                negative window silently produces zeroes everywhere,
                which reads as a dead service rather than a bad argument.
        """
        end = window_end or datetime.now(UTC)
        start = window_start or (end - timedelta(hours=DEFAULT_WINDOW_HOURS))
        if end <= start:
            raise ValidationError(
                f"The statistics window must end after it starts; got {start!s} to "
                f"{end!s}. A reversed window matches no rows and reports zeroes, "
                "which is indistinguishable from a service that did nothing."
            )

        by_status = await self._documents.count_by_status(organization_id)
        window_queries = await self._queries.list_in_window(organization_id, since=start, until=end)
        empty = sum(1 for row in window_queries if row.outcome == RetrievalOutcome.EMPTY)
        denied = sum(1 for row in window_queries if row.outcome == RetrievalOutcome.DENIED)

        vectors = await self._vectors.count_for_org(organization_id)
        tokens, cost = await self._vectors.tokens_in_window(organization_id, since=start, until=end)
        accuracy = await self._search_accuracy(organization_id, since=start)

        statistic = RagStatistic(
            organization_id=organization_id,
            window_start=start,
            window_end=end,
            documents_total=sum(by_status.values()),
            documents_indexed=by_status.get(str(DocumentStatus.INDEXED), 0),
            documents_failed=by_status.get(str(DocumentStatus.FAILED), 0),
            chunks_total=await self._chunks.count_for_org(organization_id),
            vectors_total=vectors,
            index_size_bytes=self._index_size(vectors),
            retrieval_count=len(window_queries),
            retrievals_empty=empty,
            retrievals_denied=denied,
            average_latency_ms=await self._queries.average_latency(
                organization_id, since=start, until=end
            ),
            average_result_count=await self._results.average_result_count(
                organization_id, since=start, until=end
            ),
            tokens_embedded=tokens,
            embedding_cost_usd=cost,
            search_accuracy=accuracy,
            top_documents=await self._top_documents(organization_id, since=start),
            top_sources=await self._top_sources(organization_id),
            unanswered_queries=[
                {"query": text, "hits": hits}
                for text, hits in await self._queries.unanswered(organization_id, since=start)
            ],
            by_strategy=await self._queries.count_by_strategy(organization_id, since=start),
            by_source_kind=await self._by_source_kind(organization_id),
        )
        return await self._statistics.create(statistic)

    def _index_size(self, vectors: int) -> int:
        """Estimated bytes this organization's vectors occupy."""
        return vectors * (self._dimensions * BYTES_PER_DIMENSION + EMBEDDING_HEADER_BYTES)

    async def _job_cost(self, organization_id: UUID, *, since: datetime, until: datetime) -> float:
        """What the window's indexing *jobs* recorded spending.

        Distinct from the vector-derived cost, and both are reported
        because they answer different questions. A vector row holds what
        the vector currently in the index cost, so a forced re-embed
        overwrites the earlier figure; a job row is an append-only ledger
        and keeps it. One is "what the index cost to hold", the other is
        "what we spent" -- and reporting only the first would make a
        month of repeated full reindexes look free.
        """
        total = 0.0
        for job in await self._jobs.list_for_org(organization_id, limit=1_000):
            completed = job.completed_at
            if completed is not None and since <= _aware(completed, since) < until:
                total += job.cost_usd
        return round(total, 6)

    async def _search_accuracy(self, organization_id: UUID, *, since: datetime) -> float | None:
        """Mean precision over the window's judged queries, or ``None``.

        ``None`` when nobody judged anything. Precision over zero judged
        queries is not zero, it is unknown, and the difference decides
        whether anyone investigates.
        """
        summary = await self.evaluate(organization_id, since=since, record=False)
        return summary.precision if summary.is_measurable else None

    async def _top_documents(
        self, organization_id: UUID, *, since: datetime, limit: int = 10
    ) -> list[dict[str, object]]:
        """The most retrieved documents, resolved to titles."""
        hits = await self._results.top_documents(organization_id, since=since, limit=limit)
        if not hits:
            return []
        titles = {
            document.id: document.title
            for document in await self._documents.list_by_ids(
                organization_id, [document_id for document_id, _ in hits]
            )
        }
        return [
            {
                "document_id": str(document_id),
                "title": titles.get(document_id, "(deleted)"),
                "hits": count,
            }
            for document_id, count in hits
        ]

    async def _top_sources(
        self, organization_id: UUID, *, limit: int = 10
    ) -> list[dict[str, object]]:
        """Knowledge sources by how many documents they contributed."""
        rows = []
        for source in await self._sources.list_for_org(organization_id, limit=limit):
            rows.append(
                {
                    "source_id": str(source.id),
                    "name": source.name,
                    "documents": await self._sources.count_documents(source.id),
                }
            )
        rows.sort(key=lambda row: int(str(row["documents"])), reverse=True)
        return rows

    async def _by_source_kind(self, organization_id: UUID) -> dict[str, int]:
        """How many documents came from each format or system."""
        totals: dict[str, int] = {}
        for document in await self._documents.list_for_org(organization_id, limit=10_000):
            key = str(document.source_kind)
            totals[key] = totals.get(key, 0) + 1
        return totals

    # -- evaluation ------------------------------------------------------------

    async def evaluate(
        self,
        organization_id: UUID,
        *,
        since: datetime | None = None,
        k: int = 10,
        record: bool = True,
    ) -> EvaluationSummary:
        """Measure retrieval quality against human feedback.

        Averaged over judged queries only. A query nobody judged is
        excluded rather than scored zero: including it would drive every
        metric towards zero in proportion to how little feedback exists,
        so the service would look worse the less anyone reviewed it.

        Raises:
            ValidationError: If *k* is below one.
        """
        if k < 1:
            raise ValidationError(f"k must be at least 1, got {k!r}.")
        window_start = since or (datetime.now(UTC) - timedelta(days=30))

        judged = await self._feedback.list_judged_queries(organization_id, since=window_start)
        totals: dict[str, list[float]] = {}
        unmeasurable: set[str] = set()
        evaluated = 0

        for query_id in judged:
            relevant = await self._relevant_keys(query_id)
            if not relevant:
                # Judged, but every verdict was "irrelevant". Real
                # information -- and not something precision or recall can
                # be computed from, since there is no ground truth set to
                # compare against.
                continue
            retrieved = [
                str(row.document_chunk_id) for row in await self._results.list_for_query(query_id)
            ]
            if not retrieved:
                continue
            measured = evaluate_retrieval(
                retrieved, relevant, k=k, gains=await self._graded_keys(query_id)
            )
            evaluated += 1
            for name, result in measured.items():
                if result.is_measurable:
                    totals.setdefault(name, []).append(result.value)
                else:
                    unmeasurable.add(name)

        metrics = {
            name: round(sum(values) / len(values), 6) for name, values in totals.items() if values
        }
        if "precision" in metrics and "recall" in metrics:
            metrics["f1"] = round(f1(metrics["precision"], metrics["recall"]), 6)

        summary = EvaluationSummary(
            queries_evaluated=evaluated,
            metrics=metrics,
            unmeasurable=sorted(unmeasurable - set(metrics)),
        )
        if record:
            await self._publish_event(
                EvaluationCompletedEvent(
                    source_service=_SOURCE_SERVICE,
                    organization_id=organization_id,
                    payload={
                        "queries_evaluated": summary.queries_evaluated,
                        "metrics": dict(summary.metrics),
                        "unmeasurable": list(summary.unmeasurable),
                    },
                )
            )
        return summary

    async def evaluate_query(
        self, organization_id: UUID, query_id: UUID, *, k: int = 10
    ) -> dict[str, MetricResult]:
        """Every metric for one query, unaveraged.

        Raises:
            NotFoundError: If the query is not in this organization.
        """
        await self._queries.require_in_org(organization_id, query_id)
        retrieved = [
            str(row.document_chunk_id) for row in await self._results.list_for_query(query_id)
        ]
        return evaluate_retrieval(
            retrieved,
            await self._relevant_keys(query_id),
            k=k,
            gains=await self._graded_keys(query_id),
        )

    async def _relevant_keys(self, query_id: UUID) -> set[str]:
        """Judged-relevant chunk ids, **as strings**.

        The metric functions compare retrieved keys against relevant keys
        with set membership, and the repositories return ``UUID`` while a
        retrieved key is the string form. Mixing the two never raises --
        it silently produces an empty intersection, so every metric
        reports a confident ``0.0`` and the service looks comprehensively
        broken while working perfectly. Converting here, once, is the only
        place this can be got right.
        """
        return {str(chunk_id) for chunk_id in await self._feedback.relevant_chunk_ids(query_id)}

    async def _graded_keys(self, query_id: UUID) -> dict[str, float]:
        """Graded relevance keyed by string chunk id, for nDCG."""
        graded = await self._feedback.graded_relevance(query_id)
        return {str(chunk_id): gain for chunk_id, gain in graded.items()}

    # -- reports ------------------------------------------------------------------

    async def generate_report(
        self,
        organization_id: UUID,
        kind: ReportKind,
        *,
        report_format: ReportFormat = ReportFormat.JSON,
        since: datetime | None = None,
        title: str | None = None,
        generated_by: str | None = None,
    ) -> RagReport:
        """Build one report and store it.

        A failed report is stored as ``FAILED`` with its reason rather
        than raising: a report is a scheduled artefact as often as an
        interactive one, and a nightly job that vanishes on error leaves
        nothing behind to explain the gap.
        """
        started = time.perf_counter()
        window_start = since or (datetime.now(UTC) - timedelta(days=7))
        report = await self._reports.create(
            RagReport(
                organization_id=organization_id,
                kind=kind,
                report_format=report_format,
                title=title or _default_title(kind),
                status=ReportStatus.RUNNING,
                generated_by=generated_by,
            )
        )
        try:
            content, rows = await self._build_report(organization_id, kind, since=window_start)
        except (ValidationError, ValueError) as exc:
            report.status = ReportStatus.FAILED
            report.error = str(exc)[:2_000]
            report.duration_ms = (time.perf_counter() - started) * 1_000.0
            logger.warning(
                "Report generation failed.",
                extra={"extra_fields": {"kind": str(kind), "error": str(exc)}},
            )
            return await self._reports.update(report)

        report.content = content
        report.row_count = rows
        report.status = ReportStatus.COMPLETED
        report.generated_at = datetime.now(UTC)
        report.duration_ms = (time.perf_counter() - started) * 1_000.0
        return await self._reports.update(report)

    async def _build_report(
        self, organization_id: UUID, kind: ReportKind, *, since: datetime
    ) -> tuple[dict[str, object], int]:
        """The body of one report, and how many rows it holds.

        Raises:
            ValidationError: For a report kind with no builder. Every
                member of :class:`~app.models.enums.ReportKind` has one,
                so reaching this means a member was added without a
                builder -- which should fail loudly rather than return an
                empty report that looks like an empty corpus.
        """
        chosen = ReportKind(kind)
        if chosen == ReportKind.INDEX:
            counts = await self._documents.count_by_status(organization_id)
            jobs = await self._jobs.count_by_status(organization_id)
            vectors = await self._vectors.count_for_org(organization_id)
            body: dict[str, object] = {
                "documents_by_status": counts,
                "jobs_by_status": jobs,
                "chunks": await self._chunks.count_for_org(organization_id),
                "vectors": vectors,
                "index_size_bytes": self._index_size(vectors),
                "models_in_use": await self._vectors.models_in_use(organization_id),
            }
            return body, sum(counts.values())

        if chosen == ReportKind.RETRIEVAL:
            queries = await self._queries.list_for_org(organization_id, limit=500)
            return (
                {
                    "queries": len(queries),
                    "by_strategy": await self._queries.count_by_strategy(
                        organization_id, since=since
                    ),
                    "by_outcome": _count_by(str(row.outcome) for row in queries),
                    "average_latency_ms": await self._queries.average_latency(
                        organization_id, since=since, until=datetime.now(UTC)
                    ),
                    "unanswered": [
                        {"query": text, "hits": hits}
                        for text, hits in await self._queries.unanswered(
                            organization_id, since=since
                        )
                    ],
                },
                len(queries),
            )

        if chosen == ReportKind.KNOWLEDGE_SOURCE:
            rows = await self._top_sources(organization_id, limit=100)
            return {"sources": rows}, len(rows)

        if chosen == ReportKind.EMBEDDING:
            now = datetime.now(UTC)
            models = await self._vectors.models_in_use(organization_id)
            tokens, held_cost = await self._vectors.tokens_in_window(
                organization_id, since=since, until=now
            )
            return (
                {
                    "models": models,
                    "tokens_embedded": tokens,
                    "cost_usd_held": held_cost,
                    "cost_usd_spent": await self._job_cost(organization_id, since=since, until=now),
                },
                len(models),
            )

        if chosen in {ReportKind.ACCURACY, ReportKind.EVALUATION}:
            summary = await self.evaluate(organization_id, since=since, record=False)
            return (
                {
                    "queries_evaluated": summary.queries_evaluated,
                    "metrics": dict(summary.metrics),
                    "unmeasurable": list(summary.unmeasurable),
                    "measured": summary.is_measurable,
                },
                summary.queries_evaluated,
            )

        if chosen == ReportKind.AUDIT:
            rows = [
                {
                    "action": str(row.action),
                    "entity_type": row.entity_type,
                    "entity_id": str(row.entity_id) if row.entity_id else None,
                    "actor_id": row.actor_id,
                    "occurred_at": row.occurred_at.isoformat(),
                    "succeeded": row.succeeded,
                    "summary": row.summary,
                }
                for row in await self._audit.list_for_org(organization_id, limit=1_000)
            ]
            return (
                {
                    "entries": rows,
                    "by_action": await self._audit.count_by_action(organization_id, since=since),
                },
                len(rows),
            )

        raise ValidationError(  # pragma: no cover -- every member is handled above
            f"No report builder exists for {chosen!s}."
        )

    # -- housekeeping ---------------------------------------------------------------

    async def storage_used(self, organization_id: UUID) -> int:
        """Estimated bytes this organization's vectors occupy."""
        return self._index_size(await self._vectors.count_for_org(organization_id))

    async def stale_job_count(self, organization_id: UUID) -> int:
        """Queued and running jobs -- the backlog, for a health check."""
        counts = await self._jobs.count_by_status(organization_id)
        return counts.get(str(IndexStatus.QUEUED), 0) + counts.get(str(IndexStatus.RUNNING), 0)

    async def compute_all_statistics(self, *, limit: int = 200) -> list[RagStatistic]:
        """Roll up every organization that has documents.

        Iterates tenants explicitly rather than computing one global row:
        a shared total cannot answer any question a single tenant has,
        and a per-tenant threshold computed from it would fire for
        everyone at once.
        """
        rolled: list[RagStatistic] = []
        for organization_id in await self._documents.list_organization_ids(limit=limit):
            rolled.append(await self.compute_statistics(organization_id))
        return rolled


def _count_by(values: Iterable[str]) -> dict[str, int]:
    """Tally an iterable of strings."""
    totals: dict[str, int] = {}
    for value in values:
        totals[value] = totals.get(value, 0) + 1
    return totals


def _aware(moment: datetime, reference: datetime) -> datetime:
    """*moment* with a timezone, borrowing *reference*'s if it has none.

    PostgreSQL returns aware datetimes, but a row built in memory and not
    yet round-tripped may be naive, and comparing the two raises. Borrowing
    beats assuming UTC: the reference is the window being tested against,
    so the comparison stays internally consistent either way.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=reference.tzinfo)


def _default_title(kind: ReportKind) -> str:
    """A readable title for a report nobody named."""
    return f"{str(kind).replace('_', ' ').title()} report"


__all__ = [
    "BYTES_PER_DIMENSION",
    "DEFAULT_WINDOW_HOURS",
    "AnalyticsService",
    "EvaluationSummary",
]
