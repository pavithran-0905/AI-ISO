"""Document parsing: format detection and one parser per format.

The two format modules are imported here for their side effect. Each
calls :func:`~app.documents.parser.register` at import time, so a package
that does not import them exposes a registry that is empty -- every
parse then fails with "no parser registered" for a format the service
demonstrably supports.
"""

from app.documents import binary_formats, text_formats
from app.documents.detection import FormatGuess, detect_format
from app.documents.parser import (
    DocumentParseError,
    ParsedDocument,
    ParsedPage,
    UnsupportedFormatError,
    merge,
    paginate,
    parse,
    parser_for,
    register,
    supported_formats,
)

__all__ = [
    "DocumentParseError",
    "FormatGuess",
    "ParsedDocument",
    "ParsedPage",
    "UnsupportedFormatError",
    "binary_formats",
    "detect_format",
    "merge",
    "paginate",
    "parse",
    "parser_for",
    "register",
    "supported_formats",
    "text_formats",
]
