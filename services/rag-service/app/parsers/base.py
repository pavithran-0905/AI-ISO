"""Parser contract and registry (docs/062 "DOCUMENT PARSING").

**A genuine gap.** No PDF, DOCX, HTML, or OCR handling existed anywhere
in this monorepo before this service -- confirmed against every
``pyproject.toml``.

**Every parser returns text plus provenance, never text alone.** A page
number, a section trail, a table's own boundaries: these are what turn a
retrieved chunk into a citation somebody can follow. Extracting the
characters and discarding where they came from would make every downstream
citation a gesture at a document rather than a reference into it, and that
loss is unrecoverable -- the position information does not exist anywhere
else once the bytes are parsed.

**Parsers never raise on malformed input.** A corrupt PDF in a thousand-
document import must not end the import. Failure is returned as a
:class:`ParseResult` carrying the error, so the document lands in
``FAILED`` with a reason attached and the other 999 still index.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.models.enums import SourceKind

MAX_PARSE_BYTES = 52_428_800
"""50 MiB. Parsing happens in memory, so this is the real bound on what
one document can cost the process."""


@dataclass(frozen=True, slots=True)
class ParsedBlock:
    """One extracted run of text, with where it came from.

    A parser emits blocks rather than one string so the chunker can see
    structure it would otherwise have to guess at -- which page a
    paragraph was on, which heading it sat under, whether it was a table.
    """

    text: str
    page_number: int | None = None
    section_path: tuple[str, ...] = ()
    heading: str | None = None
    is_table: bool = False
    is_code: bool = False


@dataclass(slots=True)
class ParseResult:
    """Everything one parse produced, including its failures."""

    text: str = ""
    blocks: list[ParsedBlock] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    page_count: int | None = None
    parser: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Whether anything usable came out.

        Text with warnings still counts. A PDF where three pages of forty
        failed to extract is worth indexing -- refusing it would discard
        thirty-seven good pages to punish three bad ones.
        """
        return self.error is None and bool(self.text.strip())

    @property
    def is_empty(self) -> bool:
        """Parsed cleanly and found no text.

        Distinct from a failure, and the distinction is actionable: a
        scanned PDF with no text layer parses perfectly and yields
        nothing, which means it needs OCR rather than a different parser.
        """
        return self.error is None and not self.text.strip()


class Parser(Protocol):
    """What every parser implements."""

    name: str

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        """Extract text and provenance from *data*."""
        ...


ParserFactory = Callable[[], Parser]

_REGISTRY: dict[SourceKind, ParserFactory] = {}


def register(kind: SourceKind, factory: ParserFactory) -> None:
    """Register the parser for one source kind."""
    _REGISTRY[kind] = factory


def get_parser(kind: SourceKind) -> Parser | None:
    """The parser for *kind*, or ``None`` if that kind has no parser.

    ``None`` rather than an exception: the systems in
    :class:`~app.models.enums.SourceKind` -- Confluence, S3, a git
    repository -- are *connectors* that fetch bytes, and those bytes are
    then parsed by whichever format parser matches. Asking for a parser
    for ``CONFLUENCE`` is a category question, not an error.
    """
    factory = _REGISTRY.get(kind)
    return factory() if factory else None


def supported_kinds() -> tuple[SourceKind, ...]:
    """Every source kind with a real parser behind it."""
    return tuple(sorted(_REGISTRY, key=str))


_EXTENSIONS: dict[str, SourceKind] = {
    ".pdf": SourceKind.PDF,
    ".docx": SourceKind.DOCX,
    ".txt": SourceKind.TXT,
    ".text": SourceKind.TXT,
    ".log": SourceKind.TXT,
    ".md": SourceKind.MARKDOWN,
    ".markdown": SourceKind.MARKDOWN,
    ".html": SourceKind.HTML,
    ".htm": SourceKind.HTML,
    ".csv": SourceKind.CSV,
    ".tsv": SourceKind.CSV,
    ".json": SourceKind.JSON,
    ".xml": SourceKind.XML,
    ".yaml": SourceKind.YAML,
    ".yml": SourceKind.YAML,
}


def detect_kind(filename: str | None, *, content_type: str | None = None) -> SourceKind | None:
    """Guess a source kind from a filename or MIME type.

    Extension first, because it is what a user actually controls and what
    they expect to matter. A browser upload's ``content_type`` is
    frequently ``application/octet-stream`` for anything the browser did
    not recognise, so trusting it first would misroute perfectly
    well-named files.
    """
    if filename:
        lowered = filename.lower()
        for extension, kind in _EXTENSIONS.items():
            if lowered.endswith(extension):
                return kind
    if content_type:
        normalized = content_type.split(";")[0].strip().lower()
        return _MIME_TYPES.get(normalized)
    return None


_MIME_TYPES: dict[str, SourceKind] = {
    "application/pdf": SourceKind.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": SourceKind.DOCX,
    "text/plain": SourceKind.TXT,
    "text/markdown": SourceKind.MARKDOWN,
    "text/html": SourceKind.HTML,
    "application/xhtml+xml": SourceKind.HTML,
    "text/csv": SourceKind.CSV,
    "application/json": SourceKind.JSON,
    "application/xml": SourceKind.XML,
    "text/xml": SourceKind.XML,
    "application/yaml": SourceKind.YAML,
    "text/yaml": SourceKind.YAML,
}


def decode(data: bytes) -> tuple[str, list[str]]:
    """Decode *data* to text, reporting what it took.

    **``utf-8-sig`` is tried before ``utf-8``, and the order is
    load-bearing.** Plain ``utf-8`` decodes BOM-prefixed content
    *successfully*, leaving the BOM in the text as a zero-width
    ``\\ufeff``. It would then survive into every chunk, every embedding,
    and every exact-match query against the first term of the document --
    invisibly, because it renders as nothing. Trying ``utf-8`` first
    means ``utf-8-sig`` is never reached and the BOM is never stripped.
    ``utf-8-sig`` handles both cases: it strips a BOM if present and is
    otherwise identical.

    Latin-1 is the final fallback and cannot fail, since every byte
    sequence is valid Latin-1. That is deliberate: mojibake is
    recoverable by re-ingesting with a stated encoding, whereas refusing
    the document loses it entirely, and a warning records that the text
    may be wrong.
    """
    warnings: list[str] = []
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding), warnings
        except UnicodeDecodeError:
            continue
    warnings.append(
        "Content was not valid UTF-8; decoded as Latin-1. Non-ASCII characters "
        "may be wrong. Re-ingest with an explicit encoding to correct it."
    )
    return data.decode("latin-1"), warnings


def blocks_to_text(blocks: Sequence[ParsedBlock], *, separator: str = "\n\n") -> str:
    """Join blocks into one document, dropping the empty ones."""
    return separator.join(block.text for block in blocks if block.text.strip())


def oversized(data: bytes, *, limit: int = MAX_PARSE_BYTES) -> ParseResult | None:
    """A failed :class:`ParseResult` if *data* exceeds *limit*.

    Checked before any parser touches the bytes: a decompression bomb or
    a mistakenly uploaded disk image should be refused on its size, not
    after a parser has tried to hold it in memory.
    """
    if len(data) <= limit:
        return None
    return ParseResult(
        error=(
            f"Document is {len(data)} bytes, over the {limit}-byte parse limit. "
            "Parsing runs in memory, so this bound is what stops one upload "
            "exhausting the process."
        )
    )


__all__ = [
    "MAX_PARSE_BYTES",
    "ParseResult",
    "ParsedBlock",
    "Parser",
    "ParserFactory",
    "blocks_to_text",
    "decode",
    "detect_kind",
    "get_parser",
    "oversized",
    "register",
    "supported_kinds",
]
