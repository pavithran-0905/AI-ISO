"""Format detection (docs/063 "DOCUMENT TYPES").

Three sources of evidence, weakest last: the file's own leading bytes,
its declared content type, and its extension.

**The bytes outrank the name.** A ``.txt`` holding a PDF signature is a
PDF that was renamed, and trusting the extension there produces a parse
failure that blames the wrong thing. The extension is a hint of last
resort -- it is the one piece of evidence any uploader can set to
anything.

**Detection can fail.** :data:`~app.models.enums.DocumentFormat.UNKNOWN`
is a real answer, and returning it beats guessing ``TXT`` and handing a
caller mojibake that looks like a successfully parsed document.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.models.enums import DocumentFormat

MAX_SNIFF_BYTES = 8_192
"""How much of the file the text heuristics look at. Enough to recognise
a JSON or XML preamble; small enough that detection costs nothing on a
hundred-megabyte scan."""

_SIGNATURES: tuple[tuple[bytes, DocumentFormat], ...] = (
    (b"%PDF-", DocumentFormat.PDF),
    (b"{\\rtf", DocumentFormat.RTF),
    (b"\x89PNG\r\n\x1a\n", DocumentFormat.IMAGE),
    (b"\xff\xd8\xff", DocumentFormat.IMAGE),
    (b"GIF87a", DocumentFormat.IMAGE),
    (b"GIF89a", DocumentFormat.IMAGE),
    (b"BM", DocumentFormat.IMAGE),
    (b"II*\x00", DocumentFormat.TIFF),
    (b"MM\x00*", DocumentFormat.TIFF),
)
"""Magic numbers, checked at offset zero."""

_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
"""DOCX, XLSX and ZIP share these: the Office formats *are* zip files.
Which one it is comes from what the archive contains, not from the
signature."""

_EXTENSIONS: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".txt": DocumentFormat.TXT,
    ".text": DocumentFormat.TXT,
    ".log": DocumentFormat.TXT,
    ".md": DocumentFormat.MARKDOWN,
    ".markdown": DocumentFormat.MARKDOWN,
    ".html": DocumentFormat.HTML,
    ".htm": DocumentFormat.HTML,
    ".rtf": DocumentFormat.RTF,
    ".csv": DocumentFormat.CSV,
    ".tsv": DocumentFormat.CSV,
    ".xlsx": DocumentFormat.XLSX,
    ".xlsm": DocumentFormat.XLSX,
    ".json": DocumentFormat.JSON,
    ".xml": DocumentFormat.XML,
    ".yaml": DocumentFormat.YAML,
    ".yml": DocumentFormat.YAML,
    ".png": DocumentFormat.IMAGE,
    ".jpg": DocumentFormat.IMAGE,
    ".jpeg": DocumentFormat.IMAGE,
    ".gif": DocumentFormat.IMAGE,
    ".bmp": DocumentFormat.IMAGE,
    ".webp": DocumentFormat.IMAGE,
    ".tif": DocumentFormat.TIFF,
    ".tiff": DocumentFormat.TIFF,
    ".zip": DocumentFormat.ZIP,
}

_CONTENT_TYPES: dict[str, DocumentFormat] = {
    "application/pdf": DocumentFormat.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        DocumentFormat.DOCX
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": DocumentFormat.XLSX,
    "text/plain": DocumentFormat.TXT,
    "text/markdown": DocumentFormat.MARKDOWN,
    "text/html": DocumentFormat.HTML,
    "application/rtf": DocumentFormat.RTF,
    "text/rtf": DocumentFormat.RTF,
    "text/csv": DocumentFormat.CSV,
    "application/json": DocumentFormat.JSON,
    "application/xml": DocumentFormat.XML,
    "text/xml": DocumentFormat.XML,
    "application/yaml": DocumentFormat.YAML,
    "text/yaml": DocumentFormat.YAML,
    "image/png": DocumentFormat.IMAGE,
    "image/jpeg": DocumentFormat.IMAGE,
    "image/gif": DocumentFormat.IMAGE,
    "image/bmp": DocumentFormat.IMAGE,
    "image/webp": DocumentFormat.IMAGE,
    "image/tiff": DocumentFormat.TIFF,
    "application/zip": DocumentFormat.ZIP,
}

_OFFICE_MARKERS: tuple[tuple[bytes, DocumentFormat], ...] = (
    (b"word/document.xml", DocumentFormat.DOCX),
    (b"xl/workbook.xml", DocumentFormat.XLSX),
)
"""Path entries an Office archive's central directory always contains."""


@dataclass(frozen=True, slots=True)
class FormatGuess:
    """A detected format and what led to it."""

    format: DocumentFormat
    confidence: float
    evidence: str

    def __str__(self) -> str:
        return str(self.format)

    @property
    def is_known(self) -> bool:
        return self.format is not DocumentFormat.UNKNOWN


def detect_format(
    data: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> FormatGuess:
    """What *data* is, from its bytes, its content type and its name."""
    if not data:
        return FormatGuess(DocumentFormat.UNKNOWN, 0.0, "the payload is empty")

    signature = _by_signature(data)
    if signature is not None:
        return signature

    declared = _by_content_type(content_type)
    textual = _by_content(data)

    # The content type is what the uploader said; the content is what is
    # actually there. Where they disagree about a text format, believe
    # the content -- browsers send "text/plain" for anything they do not
    # recognise, and a JSON payload so labelled is still JSON.
    prefer_content = declared is None or declared.format is DocumentFormat.TXT
    ordered = (
        textual if prefer_content else None,
        declared,
        textual,
        _by_extension(filename),
        _fallback(data),
    )
    return next(guess for guess in ordered if guess is not None)


def _fallback(data: bytes) -> FormatGuess:
    """What to conclude when no evidence identified the payload."""
    if _looks_like_text(data):
        return FormatGuess(DocumentFormat.TXT, 0.4, "decodes as text but names no format")
    return FormatGuess(
        DocumentFormat.UNKNOWN,
        0.0,
        "no signature, content type or extension identified this payload",
    )


def _by_signature(data: bytes) -> FormatGuess | None:
    """A format proved by the leading bytes, or ``None``."""
    for magic, fmt in _SIGNATURES:
        if data.startswith(magic):
            return FormatGuess(fmt, 0.99, f"leading bytes {magic!r}")
    if data.startswith(_ZIP_SIGNATURES):
        return _zip_flavour(data)
    return None


def _zip_flavour(data: bytes) -> FormatGuess:
    """Which of the zip-based formats this archive is.

    DOCX and XLSX are zip files, so the signature alone cannot separate
    them from a plain archive; the entry names in the archive can.
    """
    window = data[:MAX_SNIFF_BYTES]
    for marker, fmt in _OFFICE_MARKERS:
        if marker in window:
            return FormatGuess(fmt, 0.97, f"zip archive containing {marker.decode()}")
    return FormatGuess(DocumentFormat.ZIP, 0.8, "zip signature with no Office marker in the header")


def _by_content_type(content_type: str | None) -> FormatGuess | None:
    """A format from a declared MIME type, or ``None``."""
    if not content_type:
        return None
    base = content_type.split(";")[0].strip().lower()
    fmt = _CONTENT_TYPES.get(base)
    if fmt is None:
        return None
    return FormatGuess(fmt, 0.85, f"declared content type {base!r}")


def _by_extension(filename: str | None) -> FormatGuess | None:
    """A format from the filename, or ``None``.

    The weakest evidence there is, which is why it carries the lowest
    confidence and is consulted last.
    """
    if not filename:
        return None
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    fmt = _EXTENSIONS.get(suffix)
    if fmt is None:
        return None
    return FormatGuess(fmt, 0.6, f"filename extension {suffix!r}")


def _by_content(data: bytes) -> FormatGuess | None:
    """A text format recognised from what the payload actually says."""
    text = _decode(data[:MAX_SNIFF_BYTES])
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None

    if stripped.startswith("<?xml") or (
        stripped.startswith("<") and not _looks_like_html(stripped)
    ):
        return FormatGuess(DocumentFormat.XML, 0.9, "an XML declaration or root element")
    if _looks_like_html(stripped):
        return FormatGuess(DocumentFormat.HTML, 0.9, "an HTML doctype or root element")
    if stripped[0] in "{[" and _parses_as_json(stripped):
        return FormatGuess(DocumentFormat.JSON, 0.92, "the payload parses as JSON")
    return None


def _looks_like_html(text: str) -> bool:
    head = text[:512].lower()
    return head.startswith("<!doctype html") or "<html" in head


def _parses_as_json(text: str) -> bool:
    """Whether *text* is JSON.

    Truncated payloads are the normal case here -- only the first few
    kilobytes were read -- so a parse failure is not evidence against
    JSON when the text was cut off mid-document.
    """
    try:
        json.loads(text)
    except ValueError:
        return len(text) >= MAX_SNIFF_BYTES
    return True


def _decode(data: bytes) -> str | None:
    """*data* as text, or ``None`` if it is not text."""
    for encoding in ("utf-8", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _looks_like_text(data: bytes) -> bool:
    """Whether *data* is plausibly human-readable text.

    A NUL byte settles it: text files do not contain them, and every
    binary format this service handles does.
    """
    window = data[:MAX_SNIFF_BYTES]
    if b"\x00" in window:
        return False
    return _decode(window) is not None


__all__ = ["MAX_SNIFF_BYTES", "FormatGuess", "detect_format"]
