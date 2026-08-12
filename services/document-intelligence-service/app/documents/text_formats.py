"""Parsers for the text-based formats.

TXT, Markdown, HTML, RTF, CSV, JSON, XML and YAML. All of them decode to
a string first, so the decoding decision is made in one place.

**Structured formats are flattened to readable lines, not dumped.** A
JSON document rendered as ``json.dumps`` is text an entity extractor can
scan but a human cannot read, and every downstream summary of it is a
summary of punctuation. Nested keys become dotted paths and values sit
beside them.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import yaml
from bs4 import BeautifulSoup

from app.documents.parser import (
    ParsedDocument,
    ParsedPage,
    limit_text,
    paginate,
    register,
)
from app.models.enums import DocumentFormat

DEFAULT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
"""Tried in order. ``latin-1`` is last and always succeeds, which makes
it the deliberate fallback rather than a failure -- a document that
decodes to the wrong glyphs is more useful than one that does not decode
at all, provided the choice is recorded.

**UTF-16 is not in this list, and is only tried on a byte-order mark.**
UTF-16 decodes almost any even-length byte string without raising, so
attempting it ahead of ``cp1252`` turns an ordinary Western European
document into plausible-looking CJK mojibake -- silently, with no error
anywhere. A BOM is the only reliable evidence that a payload really is
UTF-16."""

_UTF16_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)

CHARACTERS_PER_PAGE = 3_000
"""How much text counts as a page for formats that have no pages of their
own. Roughly a printed page, so a citation to "page 3" of a text file
means something a reader can find."""

MAX_CSV_FIELD_SIZE = 1_000_000
MAX_NESTING_DEPTH = 32
"""Deeper than this and a structured document is either generated or
hostile; recursing to its bottom is how a parser blows the stack."""

_RTF_CONTROL = re.compile(r"\\(?:[a-zA-Z]+-?\d*|[^a-zA-Z])")
_RTF_HEX = re.compile(r"\\'([0-9a-fA-F]{2})")
_RTF_GROUPS_TO_DROP = re.compile(
    r"\{\\(?:\*\\)?(?:fonttbl|colortbl|stylesheet|info|generator|pict|"
    r"listtable|rsidtbl|themedata)\b[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
)
"""Whole RTF groups whose contents are not text.

``{\\*\\generator ...}`` carries the leading ``\\*``; ``{\\fonttbl ...}``
does not, so the ``\\*`` has to be optional and the keyword's own
backslash counted once. Counting it twice matches neither form, and the
font table then survives stripping and turns up in the document as
"Arial;"."""


def decode(data: bytes) -> tuple[str, str]:
    """*data* as text, with the encoding that worked."""
    for bom, encoding in _UTF16_BOMS:
        if data.startswith(bom):
            try:
                return data.decode(encoding), encoding
            except UnicodeDecodeError:  # pragma: no cover -- a BOM implies it decodes
                break
    for encoding in DEFAULT_ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    # Unreachable in practice: latin-1 maps every byte. Kept so a change
    # to DEFAULT_ENCODINGS cannot silently produce an unbound variable.
    return data.decode("utf-8", errors="replace"), "utf-8/replace"


def _base(data: bytes, fmt: DocumentFormat) -> tuple[ParsedDocument, str]:
    """A document of *fmt* and its decoded text."""
    document = ParsedDocument(format=fmt)
    text, encoding = decode(data)
    document.metadata["encoding"] = encoding
    if encoding in {"latin-1", "utf-8/replace"}:
        document.add_warning(
            f"The payload did not decode as UTF-8 and was read as {encoding}; "
            "non-ASCII characters may be wrong."
        )
    return document, limit_text(text, document)


def parse_txt(data: bytes) -> ParsedDocument:
    """A plain text file."""
    document, text = _base(data, DocumentFormat.TXT)
    document.pages = paginate(text, per_page=CHARACTERS_PER_PAGE)
    return document


def parse_markdown(data: bytes) -> ParsedDocument:
    """A Markdown file.

    The markup is left in place. Headings and bullets are exactly the
    structure the layout analyser and the summarizer look for, and
    stripping them to "clean" the text throws that away.
    """
    document, text = _base(data, DocumentFormat.MARKDOWN)
    document.pages = paginate(text, per_page=CHARACTERS_PER_PAGE)
    document.metadata["heading_count"] = str(len(re.findall(r"^#{1,6}\s", text, re.MULTILINE)))
    return document


def parse_html(data: bytes) -> ParsedDocument:
    """An HTML document, reduced to its readable text."""
    document, raw = _base(data, DocumentFormat.HTML)
    soup = BeautifulSoup(raw, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string if soup.title and soup.title.string else None
    if title:
        document.metadata["title"] = title.strip()
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property")
        content = meta.get("content")
        if name and content:
            document.metadata[f"meta:{name}"] = str(content)[:512]

    text = soup.get_text(separator="\n")
    # Collapse the runs of blank lines that get_text leaves behind
    # wherever nested block tags closed, without joining separate
    # paragraphs into one.
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(line.strip() for line in text.splitlines()))
    document.pages = paginate(text.strip(), per_page=CHARACTERS_PER_PAGE)
    if soup.find_all("table"):
        document.metadata["table_count"] = str(len(soup.find_all("table")))
    return document


def parse_rtf(data: bytes) -> ParsedDocument:
    """An RTF document, reduced to its text.

    RTF is stripped rather than parsed. A full reader would need a font
    and style model to render what is mostly formatting, and the text is
    what everything downstream wants; the loss is recorded rather than
    passed off as a complete read.
    """
    document, raw = _base(data, DocumentFormat.RTF)
    text = _RTF_GROUPS_TO_DROP.sub("", raw)
    text = _RTF_HEX.sub(
        lambda match: bytes([int(match.group(1), 16)]).decode("cp1252", "replace"), text
    )
    text = text.replace("\\par", "\n").replace("\\line", "\n").replace("\\tab", "\t")
    text = _RTF_CONTROL.sub("", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    document.add_warning(
        "RTF formatting, fonts and embedded images were discarded; only text was kept."
    )
    document.pages = paginate(text.strip(), per_page=CHARACTERS_PER_PAGE)
    return document


def parse_csv(data: bytes) -> ParsedDocument:
    """A delimited file, rendered back as aligned rows.

    The delimiter is sniffed rather than assumed, because the spec's
    ``.tsv`` and ``.csv`` reach this parser through the same format and
    reading a tab-delimited file as comma-delimited yields one enormous
    column.
    """
    document, text = _base(data, DocumentFormat.CSV)
    delimiter = _sniff_delimiter(text)
    document.metadata["delimiter"] = repr(delimiter)

    previous = csv.field_size_limit(MAX_CSV_FIELD_SIZE)
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error as error:
        document.add_warning(f"The delimited file was malformed and read as plain text: {error}")
        document.pages = paginate(text, per_page=CHARACTERS_PER_PAGE)
        return document
    finally:
        csv.field_size_limit(previous)

    document.metadata["row_count"] = str(len(rows))
    document.metadata["column_count"] = str(max((len(row) for row in rows), default=0))
    rendered = "\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(row))
    document.pages = paginate(rendered, per_page=CHARACTERS_PER_PAGE)
    return document


def _sniff_delimiter(text: str) -> str:
    """The delimiter *text* uses."""
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        # Sniffer fails on a single-column file, where every delimiter is
        # equally absent and comma is the harmless answer.
        return ","


def parse_json(data: bytes) -> ParsedDocument:
    """A JSON document, flattened to readable ``path: value`` lines."""
    document, text = _base(data, DocumentFormat.JSON)
    try:
        payload = json.loads(text)
    except ValueError as error:
        document.add_warning(f"The payload is not valid JSON and was read as text: {error}")
        document.pages = paginate(text, per_page=CHARACTERS_PER_PAGE)
        return document
    document.pages = paginate("\n".join(flatten(payload, document)), per_page=CHARACTERS_PER_PAGE)
    return document


def parse_yaml(data: bytes) -> ParsedDocument:
    """A YAML document, flattened the same way JSON is.

    Loaded with ``safe_load``: YAML's full loader constructs arbitrary
    Python objects, and this parser reads files that arrived from
    outside.
    """
    document, text = _base(data, DocumentFormat.YAML)
    try:
        documents = [item for item in yaml.safe_load_all(text) if item is not None]
    except yaml.YAMLError as error:
        document.add_warning(f"The payload is not valid YAML and was read as text: {error}")
        document.pages = paginate(text, per_page=CHARACTERS_PER_PAGE)
        return document

    if len(documents) > 1:
        document.metadata["yaml_documents"] = str(len(documents))
    lines: list[str] = []
    for index, payload in enumerate(documents, start=1):
        if len(documents) > 1:
            lines.append(f"--- document {index}")
        lines.extend(flatten(payload, document))
    document.pages = paginate("\n".join(lines), per_page=CHARACTERS_PER_PAGE)
    return document


def parse_xml(data: bytes) -> ParsedDocument:
    """An XML document, rendered as its element paths and text.

    Parsed with BeautifulSoup's XML mode rather than a raw expat parser,
    so entity expansion cannot be used to blow up the worker.
    """
    document, text = _base(data, DocumentFormat.XML)
    soup = BeautifulSoup(text, "xml")
    if soup.find() is None:
        document.add_warning("No XML elements were found; the payload was read as text.")
        document.pages = paginate(text, per_page=CHARACTERS_PER_PAGE)
        return document

    root = soup.find()
    if root is not None:
        document.metadata["root_element"] = root.name
    lines = [f"{path}: {value}" for path, value in _walk_xml(soup)]
    document.pages = paginate("\n".join(lines), per_page=CHARACTERS_PER_PAGE)
    return document


def _walk_xml(soup: BeautifulSoup) -> Iterator[tuple[str, str]]:
    """Every element with its own text, as ``path: value``."""
    for element in soup.find_all(True):
        own = "".join(child for child in element.children if isinstance(child, str)).strip()
        if not own:
            continue
        path = ".".join(
            parent.name for parent in reversed(list(element.parents)) if parent.name != "[document]"
        )
        yield (f"{path}.{element.name}" if path else element.name), own


def flatten(payload: Any, document: ParsedDocument, prefix: str = "", depth: int = 0) -> list[str]:
    """A nested structure as ``dotted.path: value`` lines.

    Depth is capped: a structure nested past :data:`MAX_NESTING_DEPTH` is
    generated or hostile, and recursing into it takes the worker down
    with a ``RecursionError`` that says nothing useful.
    """
    if depth > MAX_NESTING_DEPTH:
        document.add_warning(f"Nesting deeper than {MAX_NESTING_DEPTH} levels was not flattened.")
        return [f"{prefix}: ..."]

    if isinstance(payload, Mapping):
        lines: list[str] = []
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(flatten(value, document, path, depth + 1))
        return lines
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        lines = []
        for index, value in enumerate(payload):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            lines.extend(flatten(value, document, path, depth + 1))
        return lines
    rendered = "" if payload is None else str(payload)
    return [f"{prefix}: {rendered}" if prefix else rendered]


def _register_all() -> None:
    """Wire every text parser into the registry."""
    register(DocumentFormat.TXT, parse_txt)
    register(DocumentFormat.MARKDOWN, parse_markdown)
    register(DocumentFormat.HTML, parse_html)
    register(DocumentFormat.RTF, parse_rtf)
    register(DocumentFormat.CSV, parse_csv)
    register(DocumentFormat.JSON, parse_json)
    register(DocumentFormat.YAML, parse_yaml)
    register(DocumentFormat.XML, parse_xml)


_register_all()


__all__ = [
    "CHARACTERS_PER_PAGE",
    "DEFAULT_ENCODINGS",
    "MAX_NESTING_DEPTH",
    "ParsedPage",
    "decode",
    "flatten",
    "parse_csv",
    "parse_html",
    "parse_json",
    "parse_markdown",
    "parse_rtf",
    "parse_txt",
    "parse_xml",
    "parse_yaml",
]
