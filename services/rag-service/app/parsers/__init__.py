"""Document parsers.

**Importing this package is what registers the parsers.** Every parser
module calls :func:`~app.parsers.base.register` at import time, so a
consumer that imports only ``app.parsers.base`` gets an empty registry
and :func:`~app.parsers.base.get_parser` returns ``None`` for formats
that are fully implemented -- which surfaces as "no parser exists for
txt" at ingestion time rather than as an import error anywhere. Importing
the format modules here makes registration a property of using the
package at all.
"""

from __future__ import annotations

from app.parsers import binary_formats, text_formats
from app.parsers.base import (
    MAX_PARSE_BYTES,
    ParsedBlock,
    Parser,
    ParseResult,
    ParserFactory,
    blocks_to_text,
    decode,
    detect_kind,
    get_parser,
    oversized,
    register,
    supported_kinds,
)

__all__ = [
    "MAX_PARSE_BYTES",
    "ParseResult",
    "ParsedBlock",
    "Parser",
    "ParserFactory",
    "binary_formats",
    "blocks_to_text",
    "decode",
    "detect_kind",
    "get_parser",
    "oversized",
    "register",
    "supported_kinds",
    "text_formats",
]
