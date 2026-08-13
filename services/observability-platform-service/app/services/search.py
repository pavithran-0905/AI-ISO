"""Search service: validates a request with ``app.search.query`` and
executes it against the repository whose table matches the requested
signal kind.

**Log and event search share this module because both have a genuine
free-form search shape**: a bounded time range, a handful of equality
filters, optional text, cursor pagination. Metric and trace lookup do
not share that shape -- browsing a metric means picking a series and a
resolution, and trace lookup means fetching one whole trace by id -- so
neither is bent to fit here. Forcing every signal kind through one
interface is how a search API grows filters that only work for one of
them and silently no-op for the rest.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from app.models.enums import EventKind, LogLevel, SignalKind
from app.repositories.signals import LogEntryRepository, ObservabilityEventRepository
from app.search.query import (
    QueryLimits,
    QueryValidation,
    SearchFilter,
    SearchPage,
    SearchRequest,
    SearchRow,
    paginate,
    validate_query,
)


class SearchService:
    """Executes validated log and event searches with stable pagination."""

    def __init__(
        self,
        log_repo: LogEntryRepository,
        event_repo: ObservabilityEventRepository,
        *,
        limits: QueryLimits,
    ) -> None:
        self._log_repo = log_repo
        self._event_repo = event_repo
        self._limits = limits

    async def search(
        self, organization_id: UUID, request: SearchRequest, *, now: datetime
    ) -> QueryValidation | tuple[QueryValidation, list[SearchRow]]:
        """Validate *request*, then execute it.

        Returns just the failed :class:`QueryValidation` when the request
        was refused (no query to run), or the validation paired with a
        raw row list ready for :func:`app.search.query.paginate` -- kept
        as two returns rather than folding failure into an empty page, so
        a caller cannot mistake "the range was too wide" for "nothing
        matched".
        """
        validation = validate_query(request, self._limits, now=now)
        if not validation.is_valid or validation.query is None:
            return validation

        query = validation.query
        after: tuple[datetime, UUID] | None = None
        if query.after is not None:
            after = (query.after.occurred_at, query.after.record_id)

        filters = _filters_by_field(query.filters)
        search_rows: list[SearchRow]
        if query.signal_kind is SignalKind.LOG:
            log_rows = await self._log_repo.search_window(
                organization_id,
                start=query.time_range.start,
                end=query.time_range.end,
                service_name=filters.get("service"),
                level=LogLevel(filters["level"]) if "level" in filters else None,
                trace_id=filters.get("trace_id"),
                after=after,
                limit=query.page_size,
            )
            search_rows = [
                SearchRow(
                    record_id=row.id,
                    occurred_at=row.occurred_at,
                    payload={
                        "message": row.message,
                        "level": str(row.level),
                        "service_name": row.service_name,
                    },
                )
                for row in log_rows
            ]
        elif query.signal_kind is SignalKind.EVENT:
            event_rows = await self._event_repo.search_window(
                organization_id,
                start=query.time_range.start,
                end=query.time_range.end,
                kind=EventKind(filters["kind"]) if "kind" in filters else None,
                service_name=filters.get("service"),
                after=after,
                limit=query.page_size,
            )
            search_rows = [
                SearchRow(
                    record_id=row.id,
                    occurred_at=row.occurred_at,
                    payload={
                        "title": row.title,
                        "kind": str(row.event_kind),
                        "service_name": row.service_name,
                    },
                )
                for row in event_rows
            ]
        else:
            raise ValueError(
                f"{query.signal_kind!s} has no generic search shape; use the "
                "metric or trace repositories directly for that signal kind."
            )

        return validation, search_rows

    @staticmethod
    def paginate(validation: QueryValidation, rows: list[SearchRow]) -> SearchPage:
        """Slice the over-fetched rows into a page with a stable cursor.

        Raises:
            ValueError: If called on a failed validation. The caller
                already branched on ``is_valid`` to get here with rows at
                all, so this is a programming error, not a runtime case.
        """
        if validation.query is None:
            raise ValueError("Cannot paginate a failed query validation.")
        return paginate(rows, validation.query)


def _filters_by_field(filters: tuple[SearchFilter, ...]) -> Mapping[str, str]:
    return {item.field: item.value for item in filters}


__all__ = ["SearchService"]
