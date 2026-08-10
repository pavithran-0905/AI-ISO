"""Parsers for the text-based formats (docs/062 "KNOWLEDGE SOURCES").

Plain text, Markdown, HTML, CSV, JSON, XML, and YAML. All seven share one
property that shapes the design: the bytes already *are* text, so the
work is not extraction but **structure recovery** -- finding the headings,
rows, and keys that a chunker can split on and a citation can point at.

The structured formats (CSV, JSON, XML, YAML) get particular care,
because the obvious implementation is wrong in the same way for all of
them: dumping the raw serialisation as text embeds punctuation and
indentation, and a query about the *content* then has to compete with
braces and commas for similarity. Each is instead flattened into prose
that says what the data means.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any
from xml.etree import ElementTree

import yaml
from bs4 import BeautifulSoup

from app.models.enums import SourceKind
from app.parsers.base import (
    ParsedBlock,
    ParseResult,
    blocks_to_text,
    decode,
    oversized,
    register,
)

MAX_CSV_ROWS = 50_000
MAX_STRUCTURE_DEPTH = 24
"""Recursion bound for JSON, XML, and YAML walks. Deeply nested data is
either generated or hostile; either way, flattening past this depth adds
no retrievable meaning and risks the interpreter's own stack."""

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_SKIPPED_HTML = ("script", "style", "noscript", "template", "svg")
"""Removed before extraction. Script and style contents are never prose,
and embedding a minified bundle produces a vector that matches nothing
while consuming the whole chunk budget."""


class TextParser:
    """Plain text. Decodes and preserves paragraph structure."""

    name = "text"

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        too_big = oversized(data)
        if too_big is not None:
            return too_big
        text, warnings = decode(data)
        blocks = [
            ParsedBlock(text=piece.strip())
            for piece in re.split(r"\n\s*\n+", text)
            if piece.strip()
        ]
        return ParseResult(
            text=text.strip(),
            blocks=blocks,
            parser=self.name,
            warnings=warnings,
        )


class MarkdownParser:
    """Markdown. Recovers the heading trail each block sits under."""

    name = "markdown"

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        too_big = oversized(data)
        if too_big is not None:
            return too_big
        text, warnings = decode(data)

        blocks: list[ParsedBlock] = []
        trail: list[str] = []
        buffer: list[str] = []
        in_fence = False
        metadata: dict[str, str] = {}

        def flush(*, code: bool = False) -> None:
            body = "\n".join(buffer).strip()
            if body:
                blocks.append(
                    ParsedBlock(
                        text=body,
                        section_path=tuple(trail),
                        heading=trail[-1] if trail else None,
                        is_code=code,
                        is_table=not code and _looks_like_table(body),
                    )
                )
            buffer.clear()

        for line in text.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                if in_fence:
                    buffer.append(line)
                    flush(code=True)
                    in_fence = False
                else:
                    flush()
                    buffer.append(line)
                    in_fence = True
                continue
            if in_fence:
                buffer.append(line)
                continue

            heading = _HEADING.match(line)
            if heading:
                flush()
                level = len(heading.group(1))
                title = heading.group(2).strip()
                del trail[level - 1 :]
                trail.append(title)
                if level == 1 and "title" not in metadata:
                    metadata["title"] = title
                continue
            buffer.append(line)
        flush(code=in_fence)

        return ParseResult(
            text=blocks_to_text(blocks),
            blocks=blocks,
            metadata=metadata,
            parser=self.name,
            warnings=warnings,
        )


def _looks_like_table(body: str) -> bool:
    lines = [line for line in body.splitlines() if line.strip()]
    return bool(lines) and all(line.strip().startswith("|") for line in lines)


class HtmlParser:
    """HTML. Strips markup and recovers heading structure.

    Uses ``lxml`` through BeautifulSoup, which recovers from the
    malformed markup real-world HTML is full of -- unclosed tags, stray
    entities -- rather than refusing it. A strict parser would reject a
    large fraction of any genuine web corpus.
    """

    name = "html"

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        too_big = oversized(data)
        if too_big is not None:
            return too_big
        text, warnings = decode(data)
        try:
            soup = BeautifulSoup(text, "lxml")
        except Exception as exc:  # pragma: no cover - lxml is extremely tolerant
            return ParseResult(error=f"HTML could not be parsed: {exc}", parser=self.name)

        for tag in soup(_SKIPPED_HTML):
            tag.decompose()

        metadata: dict[str, str] = {}
        if soup.title and soup.title.string:
            metadata["title"] = soup.title.string.strip()
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                metadata[str(name).lower()] = str(content)

        blocks: list[ParsedBlock] = []
        trail: list[str] = []
        for element in soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "table", "blockquote"]
        ):
            content = element.get_text(" ", strip=True)
            if not content:
                continue
            if element.name and element.name.startswith("h") and element.name[1:].isdigit():
                level = int(element.name[1:])
                del trail[level - 1 :]
                trail.append(content)
                continue
            blocks.append(
                ParsedBlock(
                    text=content,
                    section_path=tuple(trail),
                    heading=trail[-1] if trail else None,
                    is_table=element.name == "table",
                    is_code=element.name == "pre",
                )
            )

        if not blocks:
            # No structural elements at all -- take the whole body rather
            # than reporting an empty parse, which would look like a
            # scanned document needing OCR.
            body = soup.get_text(" ", strip=True)
            if body:
                blocks.append(ParsedBlock(text=body))

        return ParseResult(
            text=blocks_to_text(blocks),
            blocks=blocks,
            metadata=metadata,
            parser=self.name,
            warnings=warnings,
        )


class CsvParser:
    """CSV and TSV, flattened into one readable line per row.

    ``"name: web-01, role: frontend, region: eu-west"`` rather than
    ``"web-01,frontend,eu-west"``. The header is repeated on every row on
    purpose: a chunk containing three rows out of a thousand has no other
    way to say what its columns mean, and a bare tuple of values is
    unsearchable -- nobody queries for "eu-west" hoping to match a
    positional field.
    """

    name = "csv"

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        too_big = oversized(data)
        if too_big is not None:
            return too_big
        text, warnings = decode(data)
        if not text.strip():
            return ParseResult(parser=self.name, warnings=warnings)

        delimiter = "\t" if (filename or "").lower().endswith(".tsv") else _sniff(text)
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        try:
            rows = list(reader)
        except csv.Error as exc:
            return ParseResult(error=f"CSV could not be parsed: {exc}", parser=self.name)

        if not rows:
            return ParseResult(parser=self.name, warnings=warnings)

        header = [cell.strip() for cell in rows[0]]
        blocks: list[ParsedBlock] = []
        for index, row in enumerate(rows[1 : MAX_CSV_ROWS + 1], start=2):
            pairs = [
                f"{header[position] or f'column {position + 1}'}: {value.strip()}"
                for position, value in enumerate(row)
                if position < len(header) and value.strip()
            ]
            if pairs:
                blocks.append(ParsedBlock(text=", ".join(pairs), page_number=index, is_table=True))

        if len(rows) - 1 > MAX_CSV_ROWS:
            warnings.append(f"Only the first {MAX_CSV_ROWS} of {len(rows) - 1} rows were parsed.")

        return ParseResult(
            text=blocks_to_text(blocks, separator="\n"),
            blocks=blocks,
            metadata={"columns": ", ".join(header)} if header else {},
            page_count=len(blocks),
            parser=self.name,
            warnings=warnings,
        )


def _sniff(text: str) -> str:
    """Guess the delimiter, defaulting to a comma."""
    try:
        return csv.Sniffer().sniff(text[:4_096], delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def _flatten(value: Any, *, path: str = "", depth: int = 0) -> list[str]:
    """Turn nested data into ``path: value`` lines.

    The path is what makes the result searchable: a query for
    ``"database host"`` should match ``database.host: db-01``, which it
    cannot do if the key was discarded and only ``db-01`` was indexed.
    """
    if depth > MAX_STRUCTURE_DEPTH:
        return [f"{path}: <nesting deeper than {MAX_STRUCTURE_DEPTH} levels omitted>"]
    if isinstance(value, dict):
        lines: list[str] = []
        for key, nested in value.items():
            lines.extend(
                _flatten(nested, path=f"{path}.{key}" if path else str(key), depth=depth + 1)
            )
        return lines
    if isinstance(value, list):
        lines = []
        for index, nested in enumerate(value):
            lines.extend(_flatten(nested, path=f"{path}[{index}]", depth=depth + 1))
        return lines
    if value is None or value == "":
        return []
    return [f"{path}: {value}" if path else str(value)]


class JsonParser:
    """JSON, flattened to dotted-path lines."""

    name = "json"

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        too_big = oversized(data)
        if too_big is not None:
            return too_big
        text, warnings = decode(data)
        try:
            document = json.loads(text) if text.strip() else None
        except json.JSONDecodeError as exc:
            return ParseResult(
                error=f"JSON could not be parsed at line {exc.lineno}: {exc.msg}",
                parser=self.name,
            )
        if document is None:
            return ParseResult(parser=self.name, warnings=warnings)

        lines = _flatten(document)
        blocks = [ParsedBlock(text=line) for line in lines]
        return ParseResult(
            text="\n".join(lines),
            blocks=blocks,
            parser=self.name,
            warnings=warnings,
        )


class YamlParser:
    """YAML, flattened the same way JSON is.

    Uses ``safe_load``, never ``load``. YAML's full loader can construct
    arbitrary Python objects from a document, which for a service whose
    entire job is ingesting untrusted files would be remote code
    execution by upload.
    """

    name = "yaml"

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        too_big = oversized(data)
        if too_big is not None:
            return too_big
        text, warnings = decode(data)
        try:
            documents = [doc for doc in yaml.safe_load_all(text) if doc is not None]
        except yaml.YAMLError as exc:
            return ParseResult(error=f"YAML could not be parsed: {exc}", parser=self.name)
        if not documents:
            return ParseResult(parser=self.name, warnings=warnings)

        blocks: list[ParsedBlock] = []
        for index, document in enumerate(documents, start=1):
            for line in _flatten(document):
                blocks.append(
                    ParsedBlock(text=line, page_number=index if len(documents) > 1 else None)
                )
        return ParseResult(
            text=blocks_to_text(blocks, separator="\n"),
            blocks=blocks,
            page_count=len(documents) if len(documents) > 1 else None,
            parser=self.name,
            warnings=warnings,
        )


class XmlParser:
    """XML, flattened to element paths with attributes and text.

    Parsed with the stdlib ``ElementTree``, whose parser does not resolve
    external entities -- so an XXE payload in an uploaded document cannot
    reach the filesystem or the network. That is the reason this does not
    use ``lxml.etree`` here despite lxml already being a dependency.
    """

    name = "xml"

    def parse(self, data: bytes, *, filename: str | None = None) -> ParseResult:
        too_big = oversized(data)
        if too_big is not None:
            return too_big
        text, warnings = decode(data)
        if not text.strip():
            return ParseResult(parser=self.name, warnings=warnings)
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as exc:
            return ParseResult(error=f"XML could not be parsed: {exc}", parser=self.name)

        blocks: list[ParsedBlock] = []
        _walk_xml(root, path="", blocks=blocks, depth=0)
        return ParseResult(
            text=blocks_to_text(blocks, separator="\n"),
            blocks=blocks,
            metadata={"root": _tag_name(root.tag)},
            parser=self.name,
            warnings=warnings,
        )


def _tag_name(tag: str) -> str:
    """Strip an XML namespace, which is noise in retrieved text."""
    return tag.rsplit("}", 1)[-1]


def _walk_xml(
    element: ElementTree.Element, *, path: str, blocks: list[ParsedBlock], depth: int
) -> None:
    name = _tag_name(element.tag)
    here = f"{path}.{name}" if path else name
    if depth > MAX_STRUCTURE_DEPTH:
        blocks.append(ParsedBlock(text=f"{here}: <nesting too deep>"))
        return

    for key, value in element.attrib.items():
        if value.strip():
            blocks.append(ParsedBlock(text=f"{here}@{_tag_name(key)}: {value.strip()}"))
    if element.text and element.text.strip():
        blocks.append(ParsedBlock(text=f"{here}: {element.text.strip()}"))
    for child in element:
        _walk_xml(child, path=here, blocks=blocks, depth=depth + 1)


register(SourceKind.TXT, TextParser)
register(SourceKind.MARKDOWN, MarkdownParser)
register(SourceKind.HTML, HtmlParser)
register(SourceKind.CSV, CsvParser)
register(SourceKind.JSON, JsonParser)
register(SourceKind.YAML, YamlParser)
register(SourceKind.XML, XmlParser)


__all__ = [
    "MAX_CSV_ROWS",
    "MAX_STRUCTURE_DEPTH",
    "CsvParser",
    "HtmlParser",
    "JsonParser",
    "MarkdownParser",
    "TextParser",
    "XmlParser",
    "YamlParser",
]
