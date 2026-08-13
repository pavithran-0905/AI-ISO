"""Tests for app.search.query -- bounded ranges, stable pagination."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.models.enums import SignalKind
from app.search.query import (
    Cursor,
    QueryLimits,
    QueryRefusal,
    SearchFilter,
    SearchRequest,
    SearchRow,
    TimeRange,
    paginate,
    validate_query,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _limits(**overrides: object) -> QueryLimits:
    defaults: dict[str, object] = {
        "max_range": timedelta(days=90),
        "max_filters": 10,
        "max_page_size": 100,
        "default_page_size": 20,
    }
    defaults.update(overrides)
    return QueryLimits(**defaults)  # type: ignore[arg-type]


def _range(*, start: datetime = NOW - timedelta(hours=1), end: datetime = NOW) -> TimeRange:
    return TimeRange(start=start, end=end)


def _request(**overrides: object) -> SearchRequest:
    defaults: dict[str, object] = {"signal_kind": SignalKind.LOG, "time_range": _range()}
    defaults.update(overrides)
    return SearchRequest(**defaults)  # type: ignore[arg-type]


class TestTimeRange:
    def test_naive_start_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            TimeRange(start=datetime(2026, 1, 1), end=NOW)

    def test_span(self) -> None:
        rng = TimeRange(start=NOW - timedelta(hours=2), end=NOW)
        assert rng.span == timedelta(hours=2)


class TestCursor:
    def test_encode_decode_round_trip(self) -> None:
        record_id = uuid4()
        cursor = Cursor(occurred_at=NOW, record_id=record_id)
        decoded = Cursor.decode(cursor.encode())
        assert decoded == cursor

    def test_decode_malformed_returns_none(self) -> None:
        assert Cursor.decode("not-a-valid-cursor") is None

    def test_decode_invalid_uuid_returns_none(self) -> None:
        assert Cursor.decode(f"{NOW.isoformat()}|not-a-uuid") is None


class TestValidateQuery:
    def test_naive_now_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            validate_query(_request(), _limits(), now=datetime(2026, 1, 1))

    def test_inverted_range_refused(self) -> None:
        request = _request(time_range=TimeRange(start=NOW, end=NOW - timedelta(hours=1)))
        result = validate_query(request, _limits(), now=NOW)
        assert result.refusal == QueryRefusal.RANGE_INVERTED
        assert not result.is_valid

    def test_range_in_future_refused(self) -> None:
        request = _request(
            time_range=TimeRange(start=NOW + timedelta(hours=1), end=NOW + timedelta(hours=2))
        )
        result = validate_query(request, _limits(), now=NOW)
        assert result.refusal == QueryRefusal.RANGE_IN_FUTURE

    def test_range_too_wide_refused(self) -> None:
        request = _request(time_range=TimeRange(start=NOW - timedelta(days=100), end=NOW))
        result = validate_query(request, _limits(max_range=timedelta(days=90)), now=NOW)
        assert result.refusal == QueryRefusal.RANGE_TOO_WIDE

    def test_too_many_filters_refused(self) -> None:
        filters = tuple(SearchFilter(field=f"f{i}", value="v") for i in range(20))
        request = _request(filters=filters)
        result = validate_query(request, _limits(max_filters=5), now=NOW)
        assert result.refusal == QueryRefusal.TOO_MANY_FILTERS

    def test_empty_text_query_refused(self) -> None:
        request = _request(text="   ")
        result = validate_query(request, _limits(), now=NOW)
        assert result.refusal == QueryRefusal.EMPTY_TEXT_QUERY

    def test_page_size_too_large_refused(self) -> None:
        request = _request(page_size=1000)
        result = validate_query(request, _limits(max_page_size=100), now=NOW)
        assert result.refusal == QueryRefusal.PAGE_SIZE_TOO_LARGE

    def test_unknown_cursor_refused(self) -> None:
        request = _request(cursor="garbage")
        result = validate_query(request, _limits(), now=NOW)
        assert result.refusal == QueryRefusal.UNKNOWN_CURSOR

    def test_valid_query_with_defaults(self) -> None:
        result = validate_query(_request(), _limits(default_page_size=20), now=NOW)
        assert result.is_valid
        assert result.query is not None
        assert result.query.page_size == 20

    def test_filters_canonicalized_and_deduped(self) -> None:
        filters = (
            SearchFilter(field="b", value="2"),
            SearchFilter(field="a", value="1"),
            SearchFilter(field="a", value="1"),  # duplicate
        )
        result = validate_query(_request(filters=filters), _limits(), now=NOW)
        assert result.query is not None
        assert result.query.filters == (
            SearchFilter(field="a", value="1"),
            SearchFilter(field="b", value="2"),
        )

    def test_text_is_stripped(self) -> None:
        result = validate_query(_request(text="  error  "), _limits(), now=NOW)
        assert result.query is not None
        assert result.query.text == "error"

    def test_valid_cursor_decoded(self) -> None:
        cursor = Cursor(occurred_at=NOW, record_id=uuid4())
        result = validate_query(_request(cursor=cursor.encode()), _limits(), now=NOW)
        assert result.query is not None
        assert result.query.after == cursor

    def test_cache_key_stable_regardless_of_filter_order(self) -> None:
        filters_a = (SearchFilter(field="a", value="1"), SearchFilter(field="b", value="2"))
        filters_b = (SearchFilter(field="b", value="2"), SearchFilter(field="a", value="1"))
        query_a = validate_query(_request(filters=filters_a), _limits(), now=NOW).query
        query_b = validate_query(_request(filters=filters_b), _limits(), now=NOW).query
        assert query_a is not None and query_b is not None
        assert query_a.cache_key == query_b.cache_key


class TestPaginate:
    def _query(self, page_size: int = 2) -> object:
        result = validate_query(_request(page_size=page_size), _limits(), now=NOW)
        assert result.query is not None
        return result.query

    def test_fewer_rows_than_page_size_no_next_cursor(self) -> None:
        rows = [SearchRow(record_id=uuid4(), occurred_at=NOW)]
        page = paginate(rows, self._query(page_size=5))
        assert len(page.rows) == 1
        assert page.next_cursor is None
        assert not page.has_more

    def test_exact_page_size_no_overfetch_no_next_cursor(self) -> None:
        rows = [SearchRow(record_id=uuid4(), occurred_at=NOW) for _ in range(2)]
        page = paginate(rows, self._query(page_size=2))
        assert len(page.rows) == 2
        assert page.next_cursor is None

    def test_overfetched_row_produces_next_cursor(self) -> None:
        rows = [
            SearchRow(record_id=uuid4(), occurred_at=NOW - timedelta(seconds=i)) for i in range(3)
        ]
        page = paginate(rows, self._query(page_size=2))
        assert len(page.rows) == 2
        assert page.has_more
        assert page.next_cursor is not None

    def test_rows_ordered_by_occurred_at_then_id(self) -> None:
        r1 = SearchRow(record_id=UUID(int=1), occurred_at=NOW - timedelta(seconds=1))
        r2 = SearchRow(record_id=UUID(int=2), occurred_at=NOW)
        page = paginate([r2, r1], self._query(page_size=5))
        assert page.rows[0].record_id == r1.record_id
