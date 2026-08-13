"""Repositories for the raw signal tables.

**Cursor-based listing, not offset, for every high-volume table.**
Metrics, log entries, spans, and events are written continuously and
searched most heavily during an incident -- exactly when concurrent
insert volume is highest and offset pagination silently skips or repeats
rows. Every listing method here takes an ``after`` cursor of
``(occurred_at, id)`` instead, matching :mod:`app.search.query`.

``require_in_org`` is named apart from :class:`BaseRepository`'s own
unscoped ``require_by_id`` deliberately, per the convention every AI-IOS
service follows: the two differ only in tenant scoping, and a name
collision would make an unscoped lookup look like a scoped one at the
call site.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from shared_core.database.base import BaseModel
from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import ColumnElement, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventKind, LogLevel, SpanStatus
from app.models.signals import (
    LogEntry,
    Metric,
    MetricSeries,
    ObservabilityEvent,
    Profile,
    TraceSession,
    TraceSpan,
)

MAX_PAGE_SIZE = 500
"""Mirrors :data:`app.search.query.QueryLimits.max_page_size`. A caller
asking for everything gets a bounded page, never a query that holds the
connection open materialising a signal table."""


class MetricSeriesRepository(BaseRepository[MetricSeries]):
    """CRUD plus identity lookup for :class:`MetricSeries`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, MetricSeries, tenant_scope=tenant_scope)

    async def find_by_identity(
        self, organization_id: UUID, name: str, label_fingerprint: str
    ) -> MetricSeries | None:
        """The series for this name and label set, if it already exists.

        Keyed on the fingerprint, never the label JSON: two label sets
        differing only in key order hash identically and are the same
        series, while a lookup against the JSON column would treat them as
        two, silently splitting one series' samples in half.
        """
        stmt = self._base_select().where(
            MetricSeries.organization_id == organization_id,
            MetricSeries.name == name,
            MetricSeries.label_fingerprint == label_fingerprint,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def require_in_org(self, organization_id: UUID, series_id: UUID) -> MetricSeries:
        """Return *series_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such series exists in that organization.
        """
        stmt = self._base_select().where(
            MetricSeries.id == series_id, MetricSeries.organization_id == organization_id
        )
        found: MetricSeries | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"Metric series {series_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def list_stale(
        self, organization_id: UUID, *, older_than: datetime, limit: int = 100
    ) -> Sequence[MetricSeries]:
        """Series nothing has written to since *older_than*.

        A stale series is usually a removed instrumentation point; it
        should stop appearing in pickers rather than being silently
        deleted, so this lists rather than purges.
        """
        stmt = (
            self._base_select()
            .where(
                MetricSeries.organization_id == organization_id,
                MetricSeries.last_seen_at < older_than,
            )
            .order_by(MetricSeries.last_seen_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


def _cursor_clause(
    model: type[BaseModel], after: tuple[datetime, UUID] | None, time_column: str
) -> ColumnElement[bool] | None:
    """A ``WHERE`` clause for cursor-stable pagination on ``(time, id)``.

    ``after`` is exclusive on both fields together, not on either alone:
    filtering only on the timestamp drops or repeats every other row that
    shares that exact instant, which is common at sub-millisecond
    granularity under load.
    """
    if after is None:
        return None
    moment, record_id = after
    column = getattr(model, time_column)
    return or_(
        column > moment,
        and_(column == moment, model.id > record_id),
    )


class MetricRepository(BaseRepository[Metric]):
    """Append-mostly repository for :class:`Metric` samples."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Metric, tenant_scope=tenant_scope)

    async def list_for_series(
        self,
        series_id: UUID,
        *,
        start: datetime,
        end: datetime,
        after: tuple[datetime, UUID] | None = None,
        limit: int = 200,
    ) -> Sequence[Metric]:
        """Samples for one series in ``[start, end)``, oldest first.

        Fetches ``limit + 1`` rows so the caller can tell whether a next
        page exists without a separate count query, matching
        :func:`app.search.query.paginate`'s contract.
        """
        stmt = self._base_select().where(
            Metric.metric_series_id == series_id,
            Metric.occurred_at >= start,
            Metric.occurred_at < end,
        )
        cursor = _cursor_clause(Metric, after, "occurred_at")
        if cursor is not None:
            stmt = stmt.where(cursor)
        stmt = stmt.order_by(Metric.occurred_at, Metric.id).limit(min(limit, MAX_PAGE_SIZE) + 1)
        return (await self._session.execute(stmt)).scalars().all()


class LogEntryRepository(BaseRepository[LogEntry]):
    """Search-oriented repository for :class:`LogEntry`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, LogEntry, tenant_scope=tenant_scope)

    async def search_window(
        self,
        organization_id: UUID,
        *,
        start: datetime,
        end: datetime,
        service_name: str | None = None,
        level: LogLevel | None = None,
        trace_id: str | None = None,
        after: tuple[datetime, UUID] | None = None,
        limit: int = 100,
    ) -> Sequence[LogEntry]:
        """Log lines in a bounded window, filtered and cursor-paginated."""
        stmt = self._base_select().where(
            LogEntry.organization_id == organization_id,
            LogEntry.occurred_at >= start,
            LogEntry.occurred_at < end,
        )
        if service_name is not None:
            stmt = stmt.where(LogEntry.service_name == service_name)
        if level is not None:
            stmt = stmt.where(LogEntry.level == level)
        if trace_id is not None:
            stmt = stmt.where(LogEntry.trace_id == trace_id)
        cursor = _cursor_clause(LogEntry, after, "occurred_at")
        if cursor is not None:
            stmt = stmt.where(cursor)
        stmt = stmt.order_by(LogEntry.occurred_at, LogEntry.id).limit(min(limit, MAX_PAGE_SIZE) + 1)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_parse_failures(
        self, organization_id: UUID, *, since: datetime, limit: int = 100
    ) -> Sequence[LogEntry]:
        """Lines that could not be parsed, for pipeline health.

        Never dropped at ingest, so this is the queue that surfaces a new
        log format nobody has taught the parser yet.
        """
        stmt = (
            self._base_select()
            .where(
                LogEntry.organization_id == organization_id,
                LogEntry.parse_failed.is_(True),
                LogEntry.occurred_at >= since,
            )
            .order_by(LogEntry.occurred_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class TraceSessionRepository(BaseRepository[TraceSession]):
    """CRUD plus lookup for :class:`TraceSession`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TraceSession, tenant_scope=tenant_scope)

    async def find_by_trace_id(self, organization_id: UUID, trace_id: str) -> TraceSession | None:
        stmt = self._base_select().where(
            TraceSession.organization_id == organization_id,
            TraceSession.trace_id == trace_id,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_incomplete(
        self, organization_id: UUID, *, older_than: datetime, limit: int = 100
    ) -> Sequence[TraceSession]:
        """Traces whose root span never arrived, past a grace period.

        A duration computed from an incomplete trace is a lower bound
        presented as a measurement; this is the queue for closing them out
        once no more spans are plausibly still coming.
        """
        stmt = (
            self._base_select()
            .where(
                TraceSession.organization_id == organization_id,
                TraceSession.is_complete.is_(False),
                TraceSession.started_at < older_than,
            )
            .order_by(TraceSession.started_at)
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


class TraceSpanRepository(BaseRepository[TraceSpan]):
    """Repository for :class:`TraceSpan`, keyed by trace rather than id."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, TraceSpan, tenant_scope=tenant_scope)

    async def list_for_trace(self, organization_id: UUID, trace_id: str) -> Sequence[TraceSpan]:
        """Every span of one trace, in start order.

        Unbounded by page size deliberately: a trace is a bounded unit
        capped at ingest by ``max_spans_per_trace``, and splitting it
        across pages would let the critical-path and topology engines see
        a partial tree and draw a wrong conclusion from it.
        """
        stmt = (
            self._base_select()
            .where(
                TraceSpan.organization_id == organization_id,
                TraceSpan.trace_id == trace_id,
            )
            .order_by(TraceSpan.started_at, TraceSpan.span_id)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_errors_for_service(
        self,
        organization_id: UUID,
        service_name: str,
        *,
        start: datetime,
        end: datetime,
        after: tuple[datetime, UUID] | None = None,
        limit: int = 100,
    ) -> Sequence[TraceSpan]:
        stmt = self._base_select().where(
            TraceSpan.organization_id == organization_id,
            TraceSpan.service_name == service_name,
            TraceSpan.status == SpanStatus.ERROR,
            TraceSpan.started_at >= start,
            TraceSpan.started_at < end,
        )
        cursor = _cursor_clause(TraceSpan, after, "started_at")
        if cursor is not None:
            stmt = stmt.where(cursor)
        stmt = stmt.order_by(TraceSpan.started_at, TraceSpan.id).limit(
            min(limit, MAX_PAGE_SIZE) + 1
        )
        return (await self._session.execute(stmt)).scalars().all()


class ObservabilityEventRepository(BaseRepository[ObservabilityEvent]):
    """Repository for :class:`ObservabilityEvent`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, ObservabilityEvent, tenant_scope=tenant_scope)

    async def search_window(
        self,
        organization_id: UUID,
        *,
        start: datetime,
        end: datetime,
        kind: EventKind | None = None,
        service_name: str | None = None,
        after: tuple[datetime, UUID] | None = None,
        limit: int = 100,
    ) -> Sequence[ObservabilityEvent]:
        stmt = self._base_select().where(
            ObservabilityEvent.organization_id == organization_id,
            ObservabilityEvent.occurred_at >= start,
            ObservabilityEvent.occurred_at < end,
        )
        if kind is not None:
            stmt = stmt.where(ObservabilityEvent.event_kind == kind)
        if service_name is not None:
            stmt = stmt.where(ObservabilityEvent.service_name == service_name)
        cursor = _cursor_clause(ObservabilityEvent, after, "occurred_at")
        if cursor is not None:
            stmt = stmt.where(cursor)
        stmt = stmt.order_by(ObservabilityEvent.occurred_at, ObservabilityEvent.id).limit(
            min(limit, MAX_PAGE_SIZE) + 1
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def active_at(
        self, organization_id: UUID, moment: datetime
    ) -> Sequence[ObservabilityEvent]:
        """Events with duration that were still in effect at *moment*.

        An instantaneous event has ``ended_at is None`` and never matches
        here past its instant -- see the model docstring for why that
        column is left null rather than repeating ``occurred_at``.
        """
        stmt = self._base_select().where(
            ObservabilityEvent.organization_id == organization_id,
            ObservabilityEvent.occurred_at <= moment,
            ObservabilityEvent.ended_at.is_not(None),
            ObservabilityEvent.ended_at >= moment,
        )
        return (await self._session.execute(stmt)).scalars().all()


class ProfileRepository(BaseRepository[Profile]):
    """Repository for :class:`Profile`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Profile, tenant_scope=tenant_scope)

    async def list_for_service(
        self,
        organization_id: UUID,
        service_name: str,
        *,
        start: datetime,
        end: datetime,
        limit: int = 50,
    ) -> Sequence[Profile]:
        stmt = (
            self._base_select()
            .where(
                Profile.organization_id == organization_id,
                Profile.service_name == service_name,
                Profile.captured_at >= start,
                Profile.captured_at < end,
            )
            .order_by(Profile.captured_at.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        return (await self._session.execute(stmt)).scalars().all()


__all__ = [
    "MAX_PAGE_SIZE",
    "LogEntryRepository",
    "MetricRepository",
    "MetricSeriesRepository",
    "ObservabilityEventRepository",
    "ProfileRepository",
    "TraceSessionRepository",
    "TraceSpanRepository",
]
