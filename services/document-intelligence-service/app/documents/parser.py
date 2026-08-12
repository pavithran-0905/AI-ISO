"""The parser contract and registry (docs/063 "DOCUMENT TYPES").

Every format produces the same shape: pages of text with the structure
that survived, plus a record of what did not.

**A parser reports what it lost.** A DOCX's headers, an XLSX's formulas,
a PDF's ligatures: each parser records in ``warnings`` what it could not
carry across, because a downstream extractor finding no signature field
needs to know whether the document lacked one or the parser dropped it.

**A PDF with no text layer is not an empty PDF.** Parsers set
``needs_ocr`` rather than returning empty text, so the pipeline routes a
scan to OCR instead of concluding the document says nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from app.models.enums import DocumentFormat

MAX_TEXT_BYTES = 50 * 1024 * 1024
"""A ceiling on extracted text. A zip bomb or a pathological PDF can
expand without limit, and a parser that will not stop takes the worker
with it."""


class DocumentParseError(RuntimeError):
    """Raised when a document cannot be parsed at all.

    Distinct from a parse that succeeded with warnings: this means no
    text was recoverable, which is a different thing to a document that
    genuinely holds none.
    """


class UnsupportedFormatError(DocumentParseError):
    """Raised when no parser is registered for a format."""


@dataclass(slots=True)
class ParsedPage:
    """One page of a parsed document."""

    number: int
    text: str = ""
    width: float | None = None
    height: float | None = None
    rotation: int = 0
    has_text_layer: bool = True
    image_count: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass(slots=True)
class ParsedDocument:
    """What a parser produces, whatever the source format was."""

    format: DocumentFormat
    pages: list[ParsedPage] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    needs_ocr: bool = False
    """The document carries no usable text layer. Not an error: it is
    the signal that routes a scan to OCR."""
    attachments: list[ParsedDocument] = field(default_factory=list)
    """Members of an archive, parsed in turn."""
    truncated: bool = False

    @property
    def text(self) -> str:
        """Every page's text, joined by the page separator."""
        return PAGE_SEPARATOR.join(page.text for page in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


PAGE_SEPARATOR = "\n\n"
"""What joins pages into one text. Two newlines, so a paragraph split
across a page break does not silently become one run-on sentence, and so
downstream sentence splitting sees a boundary."""


Parser = Callable[[bytes], ParsedDocument]

_REGISTRY: dict[DocumentFormat, Parser] = {}


def register(fmt: DocumentFormat, parser: Parser) -> None:
    """Register *parser* as the reader for *fmt*.

    Raises:
        ValueError: On a second registration for the same format. Two
            parsers for one format means whichever module imported last
            wins, and that is not a thing to discover from a wrong parse
            in production.
    """
    if fmt in _REGISTRY and _REGISTRY[fmt] is not parser:
        raise ValueError(
            f"A parser for {fmt!s} is already registered; refusing to replace "
            f"{_REGISTRY[fmt].__name__!r} with {parser.__name__!r}."
        )
    _REGISTRY[fmt] = parser


def parser_for(fmt: DocumentFormat) -> Parser:
    """The parser for *fmt*.

    Raises:
        UnsupportedFormatError: When none is registered.
    """
    try:
        return _REGISTRY[fmt]
    except KeyError:
        raise UnsupportedFormatError(
            f"No parser is registered for {fmt!s}; registered formats are "
            f"{sorted(str(key) for key in _REGISTRY)}."
        ) from None


def supported_formats() -> list[DocumentFormat]:
    """Every format that can currently be parsed."""
    return sorted(_REGISTRY, key=str)


def parse(
    data: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    fmt: DocumentFormat | None = None,
) -> ParsedDocument:
    """Parse *data*, detecting its format unless *fmt* says otherwise.

    Raises:
        DocumentParseError: When the format cannot be identified or no
            parser handles it.
    """
    from app.documents.detection import detect_format  # noqa: PLC0415 -- avoids a cycle

    if fmt is None:
        guess = detect_format(data, filename=filename, content_type=content_type)
        if not guess.is_known:
            raise DocumentParseError(
                f"The format of {filename or 'this payload'} could not be "
                f"identified: {guess.evidence}."
            )
        resolved = guess.format
        evidence: str | None = guess.evidence
    else:
        resolved = fmt
        evidence = None

    document = parser_for(resolved)(data)
    if evidence:
        document.metadata.setdefault("format_evidence", evidence)
    if filename:
        document.metadata.setdefault("filename", filename)
    return document


def paginate(text: str, *, per_page: int | None = None) -> list[ParsedPage]:
    """Text as pages, split on form feeds or on *per_page* characters.

    Form feeds first, because a document that carries them is stating its
    own page boundaries and any character count would contradict them.
    """
    if "\f" in text:
        return [
            ParsedPage(number=index, text=chunk.strip("\n"))
            for index, chunk in enumerate(text.split("\f"), start=1)
        ]
    if per_page is None or len(text) <= per_page:
        return [ParsedPage(number=1, text=text)]
    return [
        ParsedPage(number=index, text=text[start : start + per_page])
        for index, start in enumerate(range(0, len(text), per_page), start=1)
    ]


def merge(documents: Iterable[ParsedDocument], fmt: DocumentFormat) -> ParsedDocument:
    """One document from several, renumbering pages continuously.

    What multi-page assembly needs: page 1 of the second file becomes
    page 4 of the result, so a citation to "page 4" means one thing.
    """
    merged = ParsedDocument(format=fmt)
    for document in documents:
        for page in document.pages:
            merged.pages.append(
                ParsedPage(
                    number=len(merged.pages) + 1,
                    text=page.text,
                    width=page.width,
                    height=page.height,
                    rotation=page.rotation,
                    has_text_layer=page.has_text_layer,
                    image_count=page.image_count,
                )
            )
        merged.warnings.extend(
            warning for warning in document.warnings if warning not in merged.warnings
        )
        merged.needs_ocr = merged.needs_ocr or document.needs_ocr
        merged.truncated = merged.truncated or document.truncated
    return merged


def limit_text(text: str, document: ParsedDocument) -> str:
    """*text* cut to :data:`MAX_TEXT_BYTES`, flagging the document if cut."""
    encoded = text.encode("utf-8", errors="ignore")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    document.truncated = True
    document.add_warning(f"Extracted text exceeded {MAX_TEXT_BYTES} bytes and was truncated.")
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")


def _reset_registry_for_tests() -> None:
    """Empty the registry. Used only by tests that register a stub."""
    _REGISTRY.clear()


__all__ = [
    "MAX_TEXT_BYTES",
    "PAGE_SEPARATOR",
    "DocumentParseError",
    "ParsedDocument",
    "ParsedPage",
    "Parser",
    "UnsupportedFormatError",
    "limit_text",
    "merge",
    "paginate",
    "parse",
    "parser_for",
    "register",
    "supported_formats",
]
