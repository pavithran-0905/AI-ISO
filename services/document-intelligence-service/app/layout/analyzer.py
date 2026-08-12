"""Layout analysis (docs/063 "LAYOUT ANALYSIS").

Turns a page into ordered regions: what is a header, what is a table,
which column a paragraph sits in, and what order a human reads them in.

**Two inputs, one output shape.** A page can arrive as positioned words
from OCR or as plain text from a parser, and those are genuinely
different problems -- one has geometry and the other has punctuation and
line breaks. Both produce the same
:class:`LayoutRegion` list, because everything downstream cares about
reading order and region kind, not about which door the page came in
through.

**Reading order is the output that matters.** A two-column scan read
left-to-right across the page interleaves half-sentences from two
unrelated columns, and every extraction downstream then operates on
text nobody wrote. Column detection exists to prevent exactly that.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models.enums import LayoutRegionKind

DEFAULT_HEADER_BAND = 0.08
DEFAULT_FOOTER_BAND = 0.08
"""Fraction of page height treated as header and footer.

Bands rather than repeated-text matching: a header is defined by where it
sits on the page. Matching on text that repeats across pages misses it on
the first page and catches a running quotation on every other."""

DEFAULT_COLUMN_GAP_RATIO = 0.05
"""A horizontal gap this wide, as a fraction of page width, separates
columns. Narrower and every inter-word space becomes a column
boundary."""

MAX_BAND = 0.5
"""No band may exceed half the page. Beyond that the furniture is larger
than the content it frames, which is not a page layout."""

MAX_TITLE_BLOCK_LENGTH = 120

MAX_TITLE_LINE_LENGTH = 80
"""A first line longer than this is an opening sentence, not a title."""
"""A first block longer than this is an opening paragraph, not a title."""

MAX_FOOTER_BLOCK_LENGTH = 100
"""A last block longer than this is the document's conclusion, and
classifying it as furniture drops it from every summary."""

MIN_TABLE_ROWS = 2
"""One pipe-delimited line is a sentence containing pipes. Two in a row
is a table."""

SETEXT_BLOCK_LINES = 2
"""A setext heading is exactly its text and its underline."""

MIN_BLOCKS_FOR_FOOTER = 3
"""A page of two blocks has no footer -- it has two paragraphs, and
calling the second one furniture removes half the page from every
summary."""

MIN_COLUMN_WORDS = 8
"""Below this, a cluster of words is a stray caption or a page number
rather than a column. Two columns of four words each is a sentence that
happened to wrap."""

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_SETEXT = re.compile(r"^(=+|-+)\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+•]\s+|\d+[.)]\s+)")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?(?:\d+|[ivxlcdm]+)(?:\s*/\s*\d+)?\s*$", re.IGNORECASE)
_CAPTION = re.compile(
    r"^\s*(?:figure|fig\.?|table|exhibit|chart)\s+[\dA-Z][\w.-]*\s*[:.\-—]", re.IGNORECASE
)
_SIGNATURE = re.compile(
    r"^\s*(?:signature|signed(?:\s+by)?|authorised\s+by|authorized\s+by)\s*[:_.\-]", re.IGNORECASE
)
_ALL_CAPS_TITLE = re.compile(r"^[A-Z0-9][A-Z0-9 \t.,'&()/-]{3,}$")


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Where a region sits on the page, in page coordinates."""

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def centre_x(self) -> float:
        return self.left + self.width / 2

    def union(self, other: BoundingBox) -> BoundingBox:
        """The smallest box containing both."""
        left = min(self.left, other.left)
        top = min(self.top, other.top)
        return BoundingBox(
            left=left,
            top=top,
            width=max(self.right, other.right) - left,
            height=max(self.bottom, other.bottom) - top,
        )


@dataclass(slots=True)
class LayoutRegion:
    """One detected region, with its place in the reading order."""

    kind: LayoutRegionKind
    content: str
    reading_order: int = 0
    column_index: int = 0
    confidence: float = 0.0
    box: BoundingBox | None = None
    """``None`` for a region derived from a text layer.

    Left absent rather than filled with zeroes: a highlight drawn at
    ``(0, 0, 0, 0)`` covers the top-left corner of the page, which is a
    worse answer than no highlight."""
    heading_level: int | None = None
    section_path: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def is_boilerplate(self) -> bool:
        """Whether this region is page furniture rather than content.

        What a summariser and an entity extractor should skip: a footer
        repeated on ninety pages contributes ninety copies of the same
        company name to any entity count that includes it.
        """
        return self.kind in _BOILERPLATE


_BOILERPLATE = frozenset(
    {LayoutRegionKind.HEADER, LayoutRegionKind.FOOTER, LayoutRegionKind.PAGE_NUMBER}
)


@dataclass(slots=True)
class PageLayout:
    """Every region on one page, in reading order."""

    page_number: int
    regions: list[LayoutRegion] = field(default_factory=list)
    column_count: int = 1
    width: float | None = None
    height: float | None = None

    @property
    def body_text(self) -> str:
        """The page's content, boilerplate removed, in reading order."""
        return "\n\n".join(
            region.content for region in self.regions if not region.is_boilerplate
        ).strip()

    @property
    def has_tables(self) -> bool:
        return any(region.kind is LayoutRegionKind.TABLE for region in self.regions)

    @property
    def has_signatures(self) -> bool:
        return any(region.kind is LayoutRegionKind.SIGNATURE for region in self.regions)

    def of_kind(self, kind: LayoutRegionKind) -> list[LayoutRegion]:
        return [region for region in self.regions if region.kind is kind]


@dataclass(frozen=True, slots=True)
class LayoutConfig:
    """The thresholds layout analysis runs under.

    Raises on construction rather than at analysis time: a header band of
    0.6 would classify most of the page as a header, and discovering that
    halfway through a thousand-page document is worse than discovering it
    when the config is built.
    """

    header_band: float = DEFAULT_HEADER_BAND
    footer_band: float = DEFAULT_FOOTER_BAND
    column_gap_ratio: float = DEFAULT_COLUMN_GAP_RATIO
    min_column_words: int = MIN_COLUMN_WORDS
    detect_columns: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("header_band", self.header_band),
            ("footer_band", self.footer_band),
            ("column_gap_ratio", self.column_gap_ratio),
        ):
            if not 0.0 <= value <= MAX_BAND:
                raise ValueError(
                    f"{name} must be within [0, {MAX_BAND}], got {value!r}; a band larger "
                    "than half the page would classify its own content as furniture."
                )
        if self.header_band + self.footer_band >= 1.0:  # pragma: no cover -- bounded above
            raise ValueError("The header and footer bands cannot cover the whole page.")


@dataclass(frozen=True, slots=True)
class PositionedWord:
    """One word with its place on the page.

    The shape OCR produces, restated here so layout analysis does not
    depend on the OCR module -- a page whose words came from a PDF's own
    text layer positions is analysed by exactly the same code.
    """

    text: str
    left: float
    top: float
    width: float
    height: float
    line_number: int = 0
    block_number: int = 0
    confidence: float = 1.0

    @property
    def box(self) -> BoundingBox:
        return BoundingBox(self.left, self.top, self.width, self.height)


def analyze_text(
    text: str, *, page_number: int = 1, config: LayoutConfig | None = None
) -> PageLayout:
    """Analyse a page that arrived as text.

    No geometry, so header and footer detection falls back to position in
    the block sequence and to shape -- a page number is a line that is
    only a number, wherever it sits. Regions carry no bounding box,
    because there is genuinely nothing to report and a zeroed box is a
    lie a highlighting UI will draw.
    """
    settings = config or LayoutConfig()
    blocks = _split_blocks(text)
    if not blocks:
        return PageLayout(page_number=page_number)

    regions: list[LayoutRegion] = []
    trail: list[str] = []
    for index, block in enumerate(blocks):
        kind, level, confidence = _classify_block(block, index=index, total=len(blocks))
        if kind is LayoutRegionKind.HEADING and level is not None:
            del trail[level - 1 :]
            trail.append(_heading_text(block))
        regions.append(
            LayoutRegion(
                kind=kind,
                content=block.strip(),
                reading_order=len(regions),
                confidence=confidence,
                heading_level=level,
                section_path=tuple(trail),
            )
        )
    _ = settings
    return PageLayout(page_number=page_number, regions=regions, column_count=1)


def analyze_words(
    words: Sequence[PositionedWord],
    *,
    page_number: int = 1,
    page_width: float | None = None,
    page_height: float | None = None,
    config: LayoutConfig | None = None,
) -> PageLayout:
    """Analyse a page that arrived as positioned words.

    Columns are detected first and everything else happens within them,
    because reading order across columns is the one thing geometry can
    settle and text cannot.
    """
    settings = config or LayoutConfig()
    usable = [word for word in words if word.text.strip()]
    if not usable:
        return PageLayout(
            page_number=page_number, width=page_width, height=page_height, column_count=1
        )

    width = page_width or max(word.box.right for word in usable)
    height = page_height or max(word.box.bottom for word in usable)

    columns = (
        _detect_columns(usable, page_width=width, config=settings)
        if settings.detect_columns
        else [usable]
    )

    regions: list[LayoutRegion] = []
    for column_index, column_words in enumerate(columns):
        for line in _group_lines(column_words):
            box = _bounding_box(line)
            content = " ".join(word.text for word in line)
            kind, level, confidence = _classify_positioned(
                content, box=box, page_height=height, config=settings
            )
            regions.append(
                LayoutRegion(
                    kind=kind,
                    content=content,
                    column_index=column_index,
                    confidence=confidence,
                    box=box,
                    heading_level=level,
                )
            )

    ordered = _reading_order(regions)
    for position, region in enumerate(ordered):
        region.reading_order = position
    return PageLayout(
        page_number=page_number,
        regions=ordered,
        column_count=len(columns),
        width=width,
        height=height,
    )


# ---- text-layer analysis --------------------------------------------------------


def _split_blocks(text: str) -> list[str]:
    """Split page text into blocks on blank lines.

    A setext underline is folded into the line above rather than becoming
    its own block: ``====`` on its own is not a region, it is markup for
    the heading before it.
    """
    raw = [block for block in re.split(r"\n\s*\n+", text) if block.strip()]
    merged: list[str] = []
    for block in raw:
        lines = block.split("\n")
        if merged and len(lines) == 1 and _SETEXT.match(lines[0]):
            merged[-1] = f"{merged[-1]}\n{lines[0]}"
            continue
        merged.append(block)
    return merged


_BLOCK_SHAPE_RULES: tuple[tuple[re.Pattern[str], str, LayoutRegionKind, float], ...] = (
    (_PAGE_NUMBER, "block", LayoutRegionKind.PAGE_NUMBER, 0.9),
    (_CAPTION, "first_line", LayoutRegionKind.CAPTION, 0.85),
    (_SIGNATURE, "first_line", LayoutRegionKind.SIGNATURE, 0.8),
)
"""Shape rules tried in order, before any positional guess.

Ordered rather than branched so the precedence is visible: a page number
is a page number even in the first block, and a caption is a caption even
in the last."""

MIN_COLUMNS = 2
"""Fewer clusters than this is one column, however the gaps fell."""


def _classify_block(
    block: str, *, index: int, total: int
) -> tuple[LayoutRegionKind, int | None, float]:
    """What one text block is, with how sure the shape makes us."""
    stripped = block.strip()
    first_line = stripped.split("\n", 1)[0].strip()

    for pattern, target, kind, confidence in _BLOCK_SHAPE_RULES:
        if pattern.match(stripped if target == "block" else first_line):
            return kind, None, confidence

    heading = _HEADING.match(first_line)
    if heading:
        return LayoutRegionKind.HEADING, len(heading.group(1)), 0.95
    lines = stripped.split("\n")
    if len(lines) == SETEXT_BLOCK_LINES and _SETEXT.match(lines[1]):
        return (
            LayoutRegionKind.HEADING,
            1 if lines[1].startswith("=") else IMPLIED_HEADING_LEVEL,
            0.9,
        )

    if all(_TABLE_ROW.match(line) for line in lines) and len(lines) >= MIN_TABLE_ROWS:
        return LayoutRegionKind.TABLE, None, 0.9
    if all(_LIST_ITEM.match(line) for line in lines if line.strip()):
        return LayoutRegionKind.LIST, None, 0.85
    return _classify_by_position(stripped, first_line, index=index, total=total)


def _classify_by_position(
    stripped: str, first_line: str, *, index: int, total: int
) -> tuple[LayoutRegionKind, int | None, float]:
    """The fallback when shape said nothing.

    Position is weak evidence without geometry, so it is only consulted
    once shape has said nothing: a first block that is short and
    title-shaped is a title, and a last block that is short is a footer.
    Both at low confidence, because a one-line opening sentence looks
    identical to a title and only the writer knows which it was.
    """
    if index == 0 and len(stripped) < MAX_TITLE_BLOCK_LENGTH:
        # An ALL-CAPS first line is unambiguous; a *single short line* at
        # the very start is a title too. Requiring capitals meant the TITLE
        # region essentially never fired, because real documents are titled
        # in title case -- and a document with no title region cannot be
        # laid out or cited by section.
        if _ALL_CAPS_TITLE.match(first_line):
            return LayoutRegionKind.TITLE, 1, 0.7
        if "\n" not in stripped and len(first_line) <= MAX_TITLE_LINE_LENGTH:
            return LayoutRegionKind.TITLE, 1, 0.6
    if (
        index == total - 1
        and total >= MIN_BLOCKS_FOR_FOOTER
        and len(stripped) < MAX_FOOTER_BLOCK_LENGTH
    ):
        return LayoutRegionKind.FOOTER, None, 0.55
    return LayoutRegionKind.PARAGRAPH, None, 0.8


def _heading_text(block: str) -> str:
    """A heading's own words, without its markup."""
    first_line = block.strip().split("\n", 1)[0].strip()
    match = _HEADING.match(first_line)
    return match.group(2).strip() if match else first_line


# ---- geometry-based analysis -------------------------------------------------------


def _detect_columns(
    words: Sequence[PositionedWord], *, page_width: float, config: LayoutConfig
) -> list[list[PositionedWord]]:
    """Split words into columns on vertical whitespace.

    Finds gaps in the horizontal projection wide enough to be a column
    separator. A cluster too small to be a column is folded back into its
    neighbour rather than becoming a column of its own -- a page number
    and a marginal note are not columns, and treating them as such
    reorders the whole page around them.
    """
    if len(words) < config.min_column_words * 2:
        return [list(words)]

    minimum_gap = page_width * config.column_gap_ratio
    ordered = sorted(words, key=lambda word: word.left)
    clusters: list[list[PositionedWord]] = [[ordered[0]]]
    frontier = ordered[0].box.right
    for word in ordered[1:]:
        if word.left - frontier > minimum_gap:
            clusters.append([])
        clusters[-1].append(word)
        frontier = max(frontier, word.box.right)

    if len(clusters) < MIN_COLUMNS:
        return [list(words)]

    merged: list[list[PositionedWord]] = []
    for cluster in clusters:
        if len(cluster) < config.min_column_words and merged:
            merged[-1].extend(cluster)
        elif len(cluster) < config.min_column_words and not merged:
            merged.append(list(cluster))
        else:
            merged.append(list(cluster))
    return merged if len(merged) > 1 else [list(words)]


def _group_lines(words: Sequence[PositionedWord]) -> list[list[PositionedWord]]:
    """Group words into lines, then order each line left to right.

    Grouped on the engine's own line numbering where it gave one, because
    it saw the pixels; falling back to vertical position otherwise.
    """
    lines: dict[tuple[int, int], list[PositionedWord]] = {}
    for word in words:
        key = (word.block_number, word.line_number)
        lines.setdefault(key, []).append(word)
    ordered_lines = sorted(
        lines.values(), key=lambda line: (min(word.top for word in line), min(w.left for w in line))
    )
    return [sorted(line, key=lambda word: word.left) for line in ordered_lines]


def _bounding_box(words: Sequence[PositionedWord]) -> BoundingBox:
    """The box containing every word."""
    box = words[0].box
    for word in words[1:]:
        box = box.union(word.box)
    return box


_LINE_SHAPE_RULES: tuple[tuple[re.Pattern[str], LayoutRegionKind, float], ...] = (
    (_PAGE_NUMBER, LayoutRegionKind.PAGE_NUMBER, 0.8),
    (_CAPTION, LayoutRegionKind.CAPTION, 0.85),
    (_SIGNATURE, LayoutRegionKind.SIGNATURE, 0.8),
    (_TABLE_ROW, LayoutRegionKind.TABLE, 0.75),
    (_LIST_ITEM, LayoutRegionKind.LIST, 0.8),
)

MAX_TITLE_LENGTH = 80
"""An all-caps run longer than this is emphasis or a warning notice, not
a heading."""

IMPLIED_HEADING_LEVEL = 2
"""An all-caps line is a heading of unknown depth. Level 2 rather than 1:
guessing it is the document title would displace the real one."""


def _classify_positioned(
    content: str, *, box: BoundingBox, page_height: float, config: LayoutConfig
) -> tuple[LayoutRegionKind, int | None, float]:
    """What one positioned line is.

    Geometry decides header and footer, because that is what those words
    mean: a header is at the top of the page. Shape decides the rest.
    """
    if page_height > 0:
        if box.bottom <= page_height * config.header_band:
            return LayoutRegionKind.HEADER, None, 0.85
        if box.top >= page_height * (1.0 - config.footer_band):
            kind = (
                LayoutRegionKind.PAGE_NUMBER
                if _PAGE_NUMBER.match(content)
                else LayoutRegionKind.FOOTER
            )
            return kind, None, 0.85

    for pattern, kind, confidence in _LINE_SHAPE_RULES:
        if pattern.match(content):
            return kind, None, confidence

    heading = _HEADING.match(content)
    if heading:
        return LayoutRegionKind.HEADING, len(heading.group(1)), 0.9
    if _ALL_CAPS_TITLE.match(content) and len(content) < MAX_TITLE_LENGTH:
        return LayoutRegionKind.HEADING, IMPLIED_HEADING_LEVEL, 0.65
    return LayoutRegionKind.PARAGRAPH, None, 0.8


def _reading_order(regions: Sequence[LayoutRegion]) -> list[LayoutRegion]:
    """Order regions the way a person reads them.

    Column first, then top to bottom, then left to right. Reading across
    columns instead is what turns a two-column page into interleaved
    half-sentences, and every extraction downstream then works on text
    nobody wrote.
    """
    return sorted(
        regions,
        key=lambda region: (
            region.column_index,
            region.box.top if region.box else 0.0,
            region.box.left if region.box else 0.0,
        ),
    )


def merge_pages(layouts: Sequence[PageLayout]) -> str:
    """Every page's body text, in page order, boilerplate removed.

    What a summariser or classifier should be given: the same footer
    repeated on ninety pages is ninety copies of one sentence, and it
    dominates any term frequency computed over the whole document.
    """
    return "\n\n".join(layout.body_text for layout in layouts if layout.body_text).strip()


__all__ = [
    "DEFAULT_COLUMN_GAP_RATIO",
    "DEFAULT_FOOTER_BAND",
    "DEFAULT_HEADER_BAND",
    "MIN_COLUMN_WORDS",
    "BoundingBox",
    "LayoutConfig",
    "LayoutRegion",
    "PageLayout",
    "PositionedWord",
    "analyze_text",
    "analyze_words",
    "merge_pages",
]
