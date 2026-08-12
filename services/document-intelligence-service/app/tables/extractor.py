"""Table extraction (docs/063 "TABLE EXTRACTION").

Three ways a table reaches this module and one shape leaves it: a
pipe-delimited grid from markdown, a whitespace-aligned block from a
plain-text or PDF text layer, and positioned words from OCR whose columns
are found by clustering x-coordinates.

**A ragged table is still a table.** Real documents contain rows with a
missing trailing cell and rows with one extra, and refusing to extract
those loses the whole table to punish two rows. Short rows are padded,
long ones are recorded as an overflow warning, and the ragged fact is
reported rather than hidden.

**Merged cells are recorded, not silently flattened.** CSV has no way to
express one, so an export is a lossy rendering of the table rather than
the table -- and a consumer that does not know that will read the
repeated value as a real repetition.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from app.models.enums import ExtractionMethod, TableExportFormat

MIN_TABLE_ROWS = 2
"""One row is a line that happens to contain separators."""

MIN_TABLE_COLUMNS = 2
"""One column is a list."""

MAX_CELL_LENGTH = 4_096

_MERGED_RUN_LENGTH = 2
"""Consecutive blanks that read as a merged cell rather than an empty one."""

_PIPE_ROW = re.compile(r"^\s*\|(?P<body>.*)\|\s*$")
_PIPE_DIVIDER = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")
_ALIGNED_ROW = re.compile(r"\S+(?: {2,}\S+)+")
_NUMERIC = re.compile(r"^[\s$£€¥]*-?[\d,]+(?:\.\d+)?%?\s*$")


@dataclass(slots=True)
class ExtractedTable:
    """One table, with everything an export or a reviewer needs."""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    confidence: float = 0.0
    method: ExtractionMethod = ExtractionMethod.LAYOUT
    cell_confidences: list[list[float]] = field(default_factory=list)
    caption: str | None = None
    sequence: int = 0
    page_number: int | None = None
    first_page_number: int | None = None
    last_page_number: int | None = None
    has_header_row: bool = False
    has_footer_row: bool = False
    has_merged_cells: bool = False
    spans_pages: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.headers) if self.headers else (len(self.rows[0]) if self.rows else 0)

    @property
    def is_empty(self) -> bool:
        return not self.rows and not self.headers

    def column(self, name_or_index: str | int) -> list[str]:
        """One column's values.

        Raises:
            KeyError: If a named column does not exist. Returning an empty
                list would make a typo'd column name indistinguishable
                from a column that is genuinely blank.
        """
        if isinstance(name_or_index, int):
            index = name_or_index
        else:
            wanted = name_or_index.strip().lower()
            lookup = {
                header.strip().lower(): position for position, header in enumerate(self.headers)
            }
            if wanted not in lookup:
                raise KeyError(
                    f"This table has no column {name_or_index!r}; it has " f"{self.headers!r}."
                )
            index = lookup[wanted]
        return [row[index] if index < len(row) else "" for row in self.rows]

    def to_records(self) -> list[dict[str, str]]:
        """Rows as dictionaries keyed by header.

        Only meaningful with a header row; without one the keys would be
        the first row of data, which silently deletes it.
        """
        if not self.has_header_row:
            return []
        return [
            {
                header: (row[index] if index < len(row) else "")
                for index, header in enumerate(self.headers)
            }
            for row in self.rows
        ]


@dataclass(frozen=True, slots=True)
class TableConfig:
    """How table extraction behaves."""

    minimum_confidence: float = 0.5
    detect_headers: bool = True
    merge_page_spans: bool = True
    """Join a table continued on the next page onto the first. A
    multi-page table split into two is two tables neither of which is the
    thing the document contains."""
    min_rows: int = MIN_TABLE_ROWS
    min_columns: int = MIN_TABLE_COLUMNS


def extract_tables(text: str, config: TableConfig | None = None) -> list[ExtractedTable]:
    """Every table in *text*, in document order.

    Pipe-delimited grids are found first because they are unambiguous;
    whitespace-aligned blocks are looked for only in what is left, since
    a markdown table's own rows would otherwise be read twice.
    """
    settings = config or TableConfig()
    if not text.strip():
        return []

    found: list[ExtractedTable] = []
    remaining_lines: list[str] = []
    block: list[str] = []

    for line in text.splitlines():
        if _PIPE_ROW.match(line):
            block.append(line)
            continue
        if block:
            table = _from_pipes(block, settings)
            if table is not None:
                found.append(table)
            else:
                remaining_lines.extend(block)
            block = []
        remaining_lines.append(line)
    if block:
        table = _from_pipes(block, settings)
        if table is not None:
            found.append(table)
        else:
            remaining_lines.extend(block)

    found.extend(_from_aligned("\n".join(remaining_lines), settings))
    kept = [table for table in found if table.confidence >= settings.minimum_confidence]
    for position, table in enumerate(kept):
        table.sequence = position
    return kept


# ---- pipe-delimited -------------------------------------------------------------


def _from_pipes(lines: Sequence[str], config: TableConfig) -> ExtractedTable | None:
    """A markdown-style table, or ``None`` if the block is not one."""
    cells = [_split_pipes(line) for line in lines if not _PIPE_DIVIDER.match(line)]
    has_divider = any(_PIPE_DIVIDER.match(line) for line in lines)
    cells = [row for row in cells if any(cell.strip() for cell in row)]
    if len(cells) < config.min_rows or not cells:
        return None
    if max(len(row) for row in cells) < config.min_columns:
        return None

    headers: list[str] = []
    body = cells
    # A divider row is the format's own statement that the line above is
    # a header. Without one, the first row is only a header if it looks
    # like labels rather than data -- guessing wrong deletes a row.
    if config.detect_headers and (has_divider or _looks_like_header(cells[0], cells[1:])):
        headers = [cell.strip() for cell in cells[0]]
        body = cells[1:]

    table = _build(headers, body, method=ExtractionMethod.LAYOUT, base_confidence=0.9)
    table.has_header_row = bool(headers)
    if has_divider:
        table.confidence = round(min(table.confidence + 0.05, 0.98), 4)
    return table


def _split_pipes(line: str) -> list[str]:
    """One pipe row's cells, outer pipes discarded."""
    match = _PIPE_ROW.match(line)
    body = match.group("body") if match else line
    return [cell.strip() for cell in body.split("|")]


# ---- whitespace-aligned ------------------------------------------------------------


def _from_aligned(text: str, config: TableConfig) -> list[ExtractedTable]:
    """Tables laid out with runs of spaces rather than separators.

    What a PDF text layer produces, and what nothing else in this module
    would otherwise catch.
    """
    tables: list[ExtractedTable] = []
    block: list[str] = []
    for line in text.splitlines():
        if _ALIGNED_ROW.search(line) and line.strip():
            block.append(line)
            continue
        table = _aligned_block(block, config)
        if table is not None:
            tables.append(table)
        block = []
    table = _aligned_block(block, config)
    if table is not None:
        tables.append(table)
    return tables


def _aligned_block(lines: Sequence[str], config: TableConfig) -> ExtractedTable | None:
    """One run of aligned lines as a table, or ``None``.

    The test is that columns actually *line up*: prose containing a stray
    double space produces fields at whatever offset the sentence happened
    to reach, while a table's fields start at the same offsets on every
    row. Counting fields per line is not enough -- two prose lines with
    one stray gap each have two fields apiece and would pass.
    """
    if len(lines) < config.min_rows:
        return None
    fields = [_aligned_fields(line) for line in lines]
    if max(len(row) for row in fields) < config.min_columns:
        return None
    if len(_shared_offsets(fields)) < config.min_columns:
        return None

    cells = [[text for _, text in row] for row in fields]
    headers: list[str] = []
    body = cells
    if config.detect_headers and _looks_like_header(cells[0], cells[1:]):
        headers = [cell.strip() for cell in cells[0]]
        body = cells[1:]

    table = _build(headers, body, method=ExtractionMethod.LAYOUT, base_confidence=0.7)
    table.has_header_row = bool(headers)
    return table


_ALIGNED_FIELD = re.compile(r"\S+(?: \S+)*")
"""One field: words joined by single spaces, ended by the column gap."""

_OFFSET_TOLERANCE = 1
"""A column that starts one character out is the same column; proportional
fonts rendered to text drift by about that much."""

_SHARED_OFFSET_RATIO = 0.6
"""How many rows a column must appear on to count as a column."""


def _aligned_fields(line: str) -> list[tuple[int, str]]:
    """Each field on *line* with the offset it starts at."""
    return [(match.start(), match.group()) for match in _ALIGNED_FIELD.finditer(line)]


def _shared_offsets(rows: Sequence[Sequence[tuple[int, str]]]) -> list[int]:
    """Offsets at which most rows start a field."""
    if not rows:
        return []
    counts: dict[int, int] = {}
    for row in rows:
        seen: set[int] = set()
        for offset, _ in row:
            anchor = next(
                (known for known in counts if abs(known - offset) <= _OFFSET_TOLERANCE),
                offset,
            )
            if anchor not in seen:
                counts[anchor] = counts.get(anchor, 0) + 1
                seen.add(anchor)
    needed = max(2, round(len(rows) * _SHARED_OFFSET_RATIO))
    return sorted(offset for offset, count in counts.items() if count >= needed)


# ---- positioned words ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TableWord:
    """One positioned word, as OCR produces them."""

    text: str
    left: float
    top: float
    width: float
    height: float
    confidence: float = 1.0


def extract_from_words(
    words: Sequence[TableWord],
    *,
    config: TableConfig | None = None,
    page_number: int | None = None,
    column_tolerance: float = 12.0,
    row_tolerance: float = 6.0,
) -> ExtractedTable | None:
    """A table from positioned words, columns found by clustering.

    Words are grouped into rows on vertical position and into columns on
    the left edge of each word. Clustering on the *left* edge rather than
    the centre, because a table's columns are left-aligned far more often
    than they are centred, and a centre-clustered wide cell drifts into
    its neighbour's column.
    """
    settings = config or TableConfig()
    usable = [word for word in words if word.text.strip()]
    if not usable:
        return None

    rows = _cluster(usable, key=lambda word: word.top, tolerance=row_tolerance)
    if len(rows) < settings.min_rows:
        return None

    boundaries = _column_boundaries(usable, tolerance=column_tolerance)
    if len(boundaries) < settings.min_columns:
        return None

    grid: list[list[str]] = []
    confidences: list[list[float]] = []
    for row in rows:
        cells = [""] * len(boundaries)
        scores = [0.0] * len(boundaries)
        counts = [0] * len(boundaries)
        for word in sorted(row, key=lambda item: item.left):
            index = _nearest_column(word.left, boundaries)
            cells[index] = f"{cells[index]} {word.text}".strip()
            scores[index] += word.confidence
            counts[index] += 1
        grid.append(cells)
        confidences.append(
            [scores[i] / counts[i] if counts[i] else 0.0 for i in range(len(boundaries))]
        )

    headers: list[str] = []
    body = grid
    body_confidences = confidences
    if settings.detect_headers and _looks_like_header(grid[0], grid[1:]):
        headers = grid[0]
        body = grid[1:]
        body_confidences = confidences[1:]

    table = _build(headers, body, method=ExtractionMethod.LAYOUT, base_confidence=0.65)
    table.has_header_row = bool(headers)
    table.cell_confidences = body_confidences
    table.page_number = page_number
    if body_confidences:
        scored = [value for row in body_confidences for value in row if value > 0]
        if scored:
            table.confidence = round(min(table.confidence, sum(scored) / len(scored)), 4)
    return table


def _cluster(
    words: Sequence[TableWord],
    *,
    key: Callable[[TableWord], float],
    tolerance: float,
) -> list[list[TableWord]]:
    """Group words whose *key* falls within *tolerance* of each other."""
    ordered = sorted(words, key=key)
    groups: list[list[TableWord]] = [[ordered[0]]]
    for word in ordered[1:]:
        if abs(key(word) - key(groups[-1][0])) > tolerance:
            groups.append([])
        groups[-1].append(word)
    return groups


def _column_boundaries(words: Sequence[TableWord], *, tolerance: float) -> list[float]:
    """The left edge of each column, in order."""
    lefts = sorted(word.left for word in words)
    boundaries: list[float] = [lefts[0]]
    for left in lefts[1:]:
        if left - boundaries[-1] > tolerance:
            boundaries.append(left)
    return boundaries


def _nearest_column(left: float, boundaries: Sequence[float]) -> int:
    """Which column a word at *left* belongs to."""
    return min(range(len(boundaries)), key=lambda index: abs(boundaries[index] - left))


# ---- shared construction ---------------------------------------------------------------


_HEADER_CONTRAST_RATIO = 0.3
"""How numeric the rows below must be before a non-numeric first row
counts as a header rather than as data."""


def _looks_like_header(first: Sequence[str], rest: Sequence[Sequence[str]]) -> bool:
    """Whether the first row is labels rather than data.

    Two signals, both about contrast with the rows below: a header is
    rarely numeric where its column's data is, and a header cell is
    rarely empty. Getting this wrong deletes a row of real data, so it
    requires actual contrast rather than the mere absence of numbers --
    a table of names under a header of names would otherwise never be
    recognised, and neither would one with no header at all.
    """
    if not first or not rest:
        return False
    if any(not cell.strip() for cell in first):
        return False
    if any(_NUMERIC.match(cell) for cell in first if cell.strip()):
        return False
    numeric_below = sum(1 for row in rest for cell in row if cell.strip() and _NUMERIC.match(cell))
    populated_below = sum(1 for row in rest for cell in row if cell.strip())
    return bool(populated_below) and numeric_below / populated_below >= _HEADER_CONTRAST_RATIO


def _build(
    headers: Sequence[str],
    body: Sequence[Sequence[str]],
    *,
    method: ExtractionMethod,
    base_confidence: float,
) -> ExtractedTable:
    """Normalise a grid into a table, padding and recording raggedness."""
    width = max(len(headers), *(len(row) for row in body), 0)
    padded: list[list[str]] = []
    ragged = 0
    overflowed = 0
    merged = False

    for row in body:
        cells = [cell.strip()[:MAX_CELL_LENGTH] for cell in row]
        if len(cells) < width:
            ragged += 1
            cells = [*cells, *[""] * (width - len(cells))]
        elif len(cells) > width:  # pragma: no cover -- width is the maximum
            overflowed += 1
            cells = cells[:width]
        if _has_merged_run(cells):
            merged = True
        padded.append(cells)

    table = ExtractedTable(
        headers=[header.strip()[:MAX_CELL_LENGTH] for header in headers][:width],
        rows=padded,
        method=method,
        has_merged_cells=merged,
        confidence=round(base_confidence, 4),
    )
    if table.headers and len(table.headers) < width:
        table.headers.extend([""] * (width - len(table.headers)))
    if ragged:
        table.warnings.append(
            f"{ragged} row(s) had fewer cells than the widest row and were padded; "
            "the table is ragged in the source."
        )
        table.confidence = round(max(table.confidence - 0.1, 0.1), 4)
    if overflowed:  # pragma: no cover -- width is the maximum
        table.warnings.append(f"{overflowed} row(s) had extra cells that were dropped.")
    return table


def _has_merged_run(cells: Sequence[str]) -> bool:
    """Whether a row shows the trace a merged cell leaves.

    A merged cell renders as its value followed by blanks in the columns
    it spans. Two or more consecutive blanks after a populated cell is
    that trace -- and it is a trace rather than proof, which is why it
    sets a flag rather than restructuring the row.

    The run counts at the end of the row too. A cell merged across the
    remaining columns is the commonest merge there is, and stopping at
    the last populated cell would miss every one of them.
    """
    blanks = 0
    seen_value = False
    for cell in cells:
        if cell.strip():
            if seen_value and blanks >= _MERGED_RUN_LENGTH:
                return True
            seen_value = True
            blanks = 0
        elif seen_value:
            blanks += 1
    return seen_value and blanks >= _MERGED_RUN_LENGTH


# ---- export -----------------------------------------------------------------------------


def export(table: ExtractedTable, fmt: TableExportFormat) -> str:
    """Render a table in one of the spec's export formats.

    Raises:
        ValueError: For a format with no renderer. Every member of
            :class:`~app.models.enums.TableExportFormat` has one, so
            reaching this means a member was added without a renderer --
            which should fail loudly rather than return an empty string
            that reads as an empty table.
    """
    chosen = TableExportFormat(str(fmt))
    if chosen is TableExportFormat.CSV:
        return _to_csv(table)
    if chosen is TableExportFormat.JSON:
        return _to_json(table)
    if chosen is TableExportFormat.MARKDOWN:
        return _to_markdown(table)
    if chosen is TableExportFormat.XLSX:
        return _to_xlsx_rows(table)
    raise ValueError(f"No renderer exists for {chosen!s}.")  # pragma: no cover -- exhaustive


def _to_csv(table: ExtractedTable) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if table.headers:
        writer.writerow(table.headers)
    writer.writerows(table.rows)
    return buffer.getvalue()


def _to_json(table: ExtractedTable) -> str:
    """JSON, as records where there is a header and as a grid otherwise.

    Records are what a consumer wants and are only possible with a
    header; emitting them regardless would key every row by the first
    row of data.
    """
    payload: Mapping[str, object] = {
        "headers": table.headers,
        "rows": table.rows,
        "records": table.to_records(),
        "row_count": table.row_count,
        "column_count": table.column_count,
        "has_merged_cells": table.has_merged_cells,
        "spans_pages": table.spans_pages,
        "confidence": table.confidence,
        "warnings": table.warnings,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _to_markdown(table: ExtractedTable) -> str:
    width = table.column_count
    headers = table.headers or [""] * width
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in table.rows)
    return "\n".join(lines)


def _to_xlsx_rows(table: ExtractedTable) -> str:
    """The rows an XLSX writer would receive, as JSON.

    The spec asks for Excel export; producing the *workbook* is the API
    layer's job because it is bytes rather than text, and this returns
    the rows it writes. Keeping the binary encoding out of a pure module
    is what lets every path here be tested without opening a file.
    """
    rows = [table.headers, *table.rows] if table.headers else list(table.rows)
    return json.dumps({"sheet": "table", "rows": rows}, ensure_ascii=False)


def merge_continuation(first: ExtractedTable, second: ExtractedTable) -> ExtractedTable | None:
    """Join a table continued on the next page, or ``None`` if it is not one.

    A continuation has the same column count and either repeats the
    header or has none. Joining two unrelated tables that happen to share
    a width would silently fabricate rows, so the header has to agree.
    """
    if first.column_count != second.column_count or first.column_count == 0:
        return None
    if second.headers and first.headers and second.headers != first.headers:
        return None

    merged = ExtractedTable(
        headers=list(first.headers),
        rows=[*first.rows, *second.rows],
        confidence=round(min(first.confidence, second.confidence), 4),
        method=first.method,
        cell_confidences=[*first.cell_confidences, *second.cell_confidences],
        caption=first.caption,
        sequence=first.sequence,
        has_header_row=first.has_header_row,
        has_merged_cells=first.has_merged_cells or second.has_merged_cells,
        spans_pages=True,
        first_page_number=first.first_page_number or first.page_number,
        last_page_number=second.last_page_number or second.page_number,
        warnings=[*first.warnings, *second.warnings],
    )
    return merged


__all__ = [
    "MAX_CELL_LENGTH",
    "MIN_TABLE_COLUMNS",
    "MIN_TABLE_ROWS",
    "ExtractedTable",
    "TableConfig",
    "TableWord",
    "export",
    "extract_from_words",
    "extract_tables",
    "merge_continuation",
]
