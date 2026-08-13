"""Search query construction: bounded ranges, stable pagination, safe filters.

**Offset pagination is not used anywhere in this module.** Under
concurrent inserts, "skip 10000, take 100" skips or repeats rows
depending on whether inserts landed before or after the skipped window
since the last page was fetched -- and a log search during an active
incident is exactly the situation with the highest insert rate. Every
cursor here is ``(occurred_at, id)``, which is stable regardless of what
else is being written.

**A time range has a maximum span, always.** An unbounded "search all
logs" is a full-table scan wearing a search box, and it is the single
most common way an observability backend gets taken down by its own
users.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from app.models.enums import SignalKind


class QueryRefusal:
    """Why a query was not run. Typed, so a UI can react differently."""

    RANGE_TOO_WIDE = "range_too_wide"
    RANGE_INVERTED = "range_inverted"
    RANGE_IN_FUTURE = "range_in_future"
    TOO_MANY_FILTERS = "too_many_filters"
    EMPTY_TEXT_QUERY = "empty_text_query"
    PAGE_SIZE_TOO_LARGE = "page_size_too_large"
    UNKNOWN_CURSOR = "unknown_cursor"


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A half-open window, always ``[start, end)``."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        for moment in (self.start, self.end):
            if moment.tzinfo is None or moment.utcoffset() is None:
                raise ValueError(f"TimeRange requires timezone-aware bounds; got {moment!r}.")

    @property
    def span(self) -> timedelta:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class QueryLimits:
    """The gates a query must pass before it is allowed to run."""

    max_range: timedelta
    max_filters: int
    max_page_size: int
    default_page_size: int


@dataclass(frozen=True, slots=True)
class Cursor:
    """A stable pagination position.

    Opaque to the caller in practice (it is serialised at the API layer);
    here it is just the two fields that make ordering deterministic even
    when many rows share one timestamp.
    """

    occurred_at: datetime
    record_id: UUID

    def encode(self) -> str:
        return f"{self.occurred_at.isoformat()}|{self.record_id}"

    @classmethod
    def decode(cls, token: str) -> Cursor | None:
        try:
            stamp, raw_id = token.split("|", 1)
            return cls(occurred_at=datetime.fromisoformat(stamp), record_id=UUID(raw_id))
        except (ValueError, AttributeError):
            return None


@dataclass(frozen=True, slots=True)
class SearchFilter:
    """One equality or text constraint on the search."""

    field: str
    value: str


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """A search as the caller expressed it, before validation."""

    signal_kind: SignalKind
    time_range: TimeRange
    filters: tuple[SearchFilter, ...] = ()
    text: str | None = None
    page_size: int | None = None
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedQuery:
    """A query cleared to run, with filters in a canonical order.

    Sorting the filters is what makes two semantically identical queries
    -- built by different UI code paths, with filters attached in a
    different order -- produce the same cache key. Without it a search
    cache silently never hits.
    """

    signal_kind: SignalKind
    time_range: TimeRange
    filters: tuple[SearchFilter, ...]
    text: str | None
    page_size: int
    after: Cursor | None

    @property
    def cache_key(self) -> tuple[object, ...]:
        return (
            self.signal_kind,
            self.time_range.start,
            self.time_range.end,
            self.filters,
            self.text,
            self.page_size,
        )


@dataclass(frozen=True, slots=True)
class QueryValidation:
    """Either a runnable query or a typed reason it cannot run."""

    query: ValidatedQuery | None
    refusal: str | None
    detail: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.query is not None


def validate_query(  # noqa: PLR0911 - one exit per gate, by design
    request: SearchRequest, limits: QueryLimits, *, now: datetime
) -> QueryValidation:
    """Check a search request against every gate before it touches storage."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("validate_query requires a timezone-aware 'now'.")

    if request.time_range.end <= request.time_range.start:
        return QueryValidation(
            query=None,
            refusal=QueryRefusal.RANGE_INVERTED,
            detail=(
                f"end {request.time_range.end.isoformat()} is not after start "
                f"{request.time_range.start.isoformat()}."
            ),
        )
    if request.time_range.start > now:
        return QueryValidation(
            query=None,
            refusal=QueryRefusal.RANGE_IN_FUTURE,
            detail="The range starts in the future; there is nothing there yet.",
        )
    if request.time_range.span > limits.max_range:
        return QueryValidation(
            query=None,
            refusal=QueryRefusal.RANGE_TOO_WIDE,
            detail=(
                f"{request.time_range.span} exceeds the {limits.max_range} maximum. "
                "Narrow the range or use a report for long-window aggregates."
            ),
        )
    if len(request.filters) > limits.max_filters:
        return QueryValidation(
            query=None,
            refusal=QueryRefusal.TOO_MANY_FILTERS,
            detail=f"{len(request.filters)} filters exceeds the {limits.max_filters} limit.",
        )
    if request.text is not None and not request.text.strip():
        return QueryValidation(
            query=None,
            refusal=QueryRefusal.EMPTY_TEXT_QUERY,
            detail="An empty text filter matches everything and is not a search.",
        )

    page_size = request.page_size or limits.default_page_size
    if page_size > limits.max_page_size:
        return QueryValidation(
            query=None,
            refusal=QueryRefusal.PAGE_SIZE_TOO_LARGE,
            detail=f"{page_size} exceeds the {limits.max_page_size} maximum.",
        )

    after: Cursor | None = None
    if request.cursor is not None:
        after = Cursor.decode(request.cursor)
        if after is None:
            return QueryValidation(
                query=None,
                refusal=QueryRefusal.UNKNOWN_CURSOR,
                detail="The cursor could not be decoded; it may be stale or malformed.",
            )

    canonical_filters = tuple(sorted({(f.field, f.value) for f in request.filters}))
    return QueryValidation(
        query=ValidatedQuery(
            signal_kind=request.signal_kind,
            time_range=request.time_range,
            filters=tuple(SearchFilter(field=f, value=v) for f, v in canonical_filters),
            text=request.text.strip() if request.text else None,
            page_size=page_size,
            after=after,
        ),
        refusal=None,
    )


@dataclass(frozen=True, slots=True)
class SearchRow:
    """One matched record -- generic over signal kind."""

    record_id: UUID
    occurred_at: datetime
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchPage:
    """One page of results, with a cursor only when more data exists.

    ``next_cursor`` is ``None`` when the page did not fill -- a full page
    that happens to end exactly at the last row would otherwise emit a
    cursor that returns an empty next page forever, which looks to a
    client like the search is still loading.
    """

    rows: tuple[SearchRow, ...]
    next_cursor: str | None
    query: ValidatedQuery

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None


def paginate(rows: Sequence[SearchRow], query: ValidatedQuery) -> SearchPage:
    """Slice a fetched (over-fetched by one) row set into a page.

    Expects the caller to have fetched ``page_size + 1`` rows ordered by
    ``(occurred_at, record_id)`` starting after ``query.after`` -- the
    extra row is how the engine knows whether a next page exists without
    a separate count query.
    """
    ordered = sorted(rows, key=lambda row: (row.occurred_at, row.record_id))
    page = ordered[: query.page_size]
    has_more = len(ordered) > query.page_size

    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = Cursor(occurred_at=last.occurred_at, record_id=last.record_id).encode()

    return SearchPage(rows=tuple(page), next_cursor=next_cursor, query=query)


__all__ = [
    "Cursor",
    "QueryLimits",
    "QueryRefusal",
    "QueryValidation",
    "SearchFilter",
    "SearchPage",
    "SearchRequest",
    "SearchRow",
    "TimeRange",
    "ValidatedQuery",
    "paginate",
    "validate_query",
]
