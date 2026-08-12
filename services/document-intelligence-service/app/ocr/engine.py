"""The OCR engine contract and its Tesseract implementation.

**Cloud OCR is out of scope by the spec's own DO NOT IMPLEMENT list**, so
there is no hosted fallback and none is pretended. What ships is a local
engine, and a local engine has a property a hosted one does not: it can
be *missing*. Tesseract is a system binary, not a wheel, so an image
arriving at a deployment without it is not a parse failure -- it is a
deployment that cannot read that document, which is a different message
to a different person.

**Availability is answered at startup, not discovered on the first
scanned page.** :func:`probe` runs once and reports what the deployment
can actually do. A service that only finds out when a user uploads a scan
reports it as an error against their document rather than against its own
configuration.

**Confidence is per word, and the page score is derived from it.** A
single page-level number cannot tell a reviewer *which* words to check,
and "this page is 62% confident" is not something anybody can act on. The
words are kept and the page score is their mean, so both questions have
an answer.
"""

from __future__ import annotations

import io
import shutil
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from shared_core.logging.logger import get_logger

from app.models.enums import OcrEngineKind, OcrQuality, ocr_quality_for

logger = get_logger("app.ocr.engine")

TESSERACT_BINARY = "tesseract"

MIN_WORD_CONFIDENCE = 0.0
MAX_WORD_CONFIDENCE = 1.0

_TESSERACT_CONFIDENCE_SCALE = 100.0
"""Tesseract reports confidence as 0-100. Everything downstream of this
module works in 0-1, and the conversion happens here, once -- a
percentage leaking into a threshold comparison silently passes every
check."""

_TESSERACT_NO_CONFIDENCE = -1.0
"""What Tesseract reports for a box it found but could not score --
typically layout boxes rather than words. Dropped rather than clamped to
zero, which would drag the page mean down for boxes that carry no text
to be wrong about."""


@dataclass(frozen=True, slots=True)
class OcrWord:
    """One recognised word, with where it was and how sure the engine was."""

    text: str
    confidence: float
    left: float = 0.0
    top: float = 0.0
    width: float = 0.0
    height: float = 0.0
    line_number: int = 0
    block_number: int = 0


@dataclass(slots=True)
class OcrPage:
    """Everything one page's OCR produced."""

    page_number: int
    text: str = ""
    words: list[OcrWord] = field(default_factory=list)
    engine: OcrEngineKind = OcrEngineKind.NONE
    rotation_degrees: int = 0
    width: float | None = None
    height: float | None = None
    resolution_dpi: int | None = None
    detected_language: str | None = None
    duration_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        """Whether anything usable came out.

        Text with warnings still counts: a page where a watermark
        confused three words is worth indexing, and discarding it to
        punish the three loses the rest.
        """
        return self.error is None and bool(self.text.strip())

    @property
    def confidence(self) -> float:
        """Mean word confidence, or ``0.0`` for a page with no words.

        The mean over *words*, not over characters or boxes: a page whose
        one recognised word scored 0.99 is not a confident page, and
        weighting by anything else hides how little was read.
        """
        scored = [word.confidence for word in self.words if word.text.strip()]
        return sum(scored) / len(scored) if scored else 0.0

    @property
    def quality(self) -> OcrQuality:
        """The confidence band a reviewer acts on."""
        return ocr_quality_for(self.confidence)

    @property
    def low_confidence_words(self) -> list[OcrWord]:
        """The words worth showing a human, worst first.

        What makes a confidence score useful: a reviewer opens the page
        and sees the doubtful words highlighted rather than reading all
        of it looking for the mistake.
        """
        threshold = ocr_quality_floor(OcrQuality.GOOD)
        return sorted(
            (word for word in self.words if word.confidence < threshold),
            key=lambda word: word.confidence,
        )


@dataclass(slots=True)
class OcrResult:
    """Everything one document's OCR produced."""

    pages: list[OcrPage] = field(default_factory=list)
    engine: OcrEngineKind = OcrEngineKind.NONE
    languages: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and any(page.succeeded for page in self.pages)

    @property
    def text(self) -> str:
        """Every page's text, in page order."""
        return "\n\n".join(page.text for page in self.pages if page.text.strip())

    @property
    def confidence(self) -> float:
        """Mean confidence across pages that produced words."""
        scored = [page.confidence for page in self.pages if page.words]
        return sum(scored) / len(scored) if scored else 0.0

    @property
    def lowest_page_confidence(self) -> float | None:
        """The worst page, or ``None`` if nothing was read.

        Reported alongside the mean because the mean is what hides it:
        one unreadable page in forty barely moves an average and is
        exactly the page somebody has to look at.
        """
        scored = [page.confidence for page in self.pages if page.words]
        return min(scored) if scored else None


_QUALITY_FLOORS: dict[OcrQuality, float] = {
    OcrQuality.EXCELLENT: 0.95,
    OcrQuality.GOOD: 0.85,
    OcrQuality.FAIR: 0.70,
    OcrQuality.POOR: 0.40,
    OcrQuality.UNREADABLE: 0.0,
}


def ocr_quality_floor(quality: OcrQuality) -> float:
    """The lowest confidence that still bands as *quality*."""
    return _QUALITY_FLOORS[OcrQuality(str(quality))]


@dataclass(frozen=True, slots=True)
class EngineAvailability:
    """Whether OCR can actually run here, and why not if it cannot."""

    available: bool
    engine: OcrEngineKind
    version: str | None = None
    languages: tuple[str, ...] = ()
    reason: str | None = None

    def require(self) -> None:
        """Assert that OCR is usable.

        Raises:
            OcrUnavailableError: With the reason, which is the whole
                point -- "OCR failed" sends somebody to look at the
                document, and "the tesseract binary is not installed"
                sends them to the deployment.
        """
        if not self.available:
            raise OcrUnavailableError(
                self.reason or f"OCR engine {self.engine!s} is not available."
            )


class OcrUnavailableError(RuntimeError):
    """Raised when OCR was asked for and cannot run.

    Distinct from a page that OCR read badly: one is a deployment
    problem and the other is a document problem, and they go to
    different people.
    """


class OcrEngine(Protocol):
    """What every OCR engine implements."""

    kind: OcrEngineKind

    def probe(self) -> EngineAvailability:
        """Whether this engine can run, checked against the real system."""
        ...

    def read_image(
        self, data: bytes, *, page_number: int = 1, languages: Sequence[str] = ("eng",)
    ) -> OcrPage:
        """Recognise text in one image."""
        ...


class TesseractEngine:
    """OCR through the Tesseract binary, via ``pytesseract``.

    ``pytesseract`` is a thin wrapper that shells out; the recognition
    itself is the binary's, which is a system package. Both halves are
    checked in :meth:`probe`, separately, because "the Python package is
    missing" and "the binary is missing" have different fixes and a
    single "OCR unavailable" makes somebody find out which by
    experiment.
    """

    kind = OcrEngineKind.TESSERACT

    def __init__(self, *, timeout_seconds: float = 120.0, minimum_confidence: float = 0.0) -> None:
        self._timeout = timeout_seconds
        self._minimum_confidence = minimum_confidence

    def probe(self) -> EngineAvailability:
        """Check the wrapper, the binary, and the installed languages."""
        try:
            # Imported here rather than at module scope, and that is the
            # point of this method: the whole module has to be importable
            # on a machine with no OCR at all, so that `probe()` can
            # *report* its absence instead of the service failing to
            # start.
            import pytesseract  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover -- declared dependency
            return EngineAvailability(
                available=False,
                engine=self.kind,
                reason=f"The pytesseract package is not importable: {exc}.",
            )

        if shutil.which(TESSERACT_BINARY) is None:
            return EngineAvailability(
                available=False,
                engine=self.kind,
                reason=(
                    "The tesseract binary is not on PATH. It is a system package rather "
                    "than a Python wheel -- install it in the image (apt-get install "
                    "tesseract-ocr) or disable OCR "
                    "(AIIOS_DOCUMENT_INTELLIGENCE_SERVICE_OCR_ENABLED=false)."
                ),
            )

        try:
            version = str(pytesseract.get_tesseract_version())
            languages = tuple(pytesseract.get_languages(config=""))
        except Exception as exc:
            return EngineAvailability(
                available=False,
                engine=self.kind,
                reason=f"The tesseract binary is present but did not respond: {exc}.",
            )
        return EngineAvailability(
            available=True, engine=self.kind, version=version, languages=languages
        )

    def read_image(
        self, data: bytes, *, page_number: int = 1, languages: Sequence[str] = ("eng",)
    ) -> OcrPage:
        """Recognise text in one image.

        Never raises on a recognition failure: one unreadable page in a
        thousand-page batch must not end the batch, so the failure is
        returned on the page it belongs to.
        """
        started = time.perf_counter()
        try:
            import pytesseract  # noqa: PLC0415
            from PIL import Image  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover -- declared dependency
            return OcrPage(
                page_number=page_number,
                engine=self.kind,
                error=f"OCR dependencies are not importable: {exc}.",
            )

        try:
            with Image.open(io.BytesIO(data)) as image:
                width, height = float(image.width), float(image.height)
                dpi = _dpi_of(image)
                raw = pytesseract.image_to_data(
                    image,
                    lang="+".join(languages) or "eng",
                    output_type=pytesseract.Output.DICT,
                    timeout=self._timeout,
                )
        except Exception as exc:
            return OcrPage(
                page_number=page_number,
                engine=self.kind,
                duration_ms=(time.perf_counter() - started) * 1_000.0,
                error=f"Tesseract could not read page {page_number}: {exc}",
            )

        words = self._to_words(raw)
        kept = [word for word in words if word.confidence >= self._minimum_confidence]
        dropped = len(words) - len(kept)
        page = OcrPage(
            page_number=page_number,
            text=_join_words(kept),
            words=kept,
            engine=self.kind,
            width=width,
            height=height,
            resolution_dpi=dpi,
            duration_ms=(time.perf_counter() - started) * 1_000.0,
        )
        if dropped:
            page.warnings.append(
                f"{dropped} word(s) fell below the {self._minimum_confidence} confidence "
                "floor and were dropped."
            )
        return page

    def _to_words(self, raw: dict[str, list[object]]) -> list[OcrWord]:
        """Turn Tesseract's column-oriented output into word records.

        Its dict is parallel lists, one entry per detected box, which is
        the shape a spreadsheet has rather than the shape code wants.
        """
        words: list[OcrWord] = []
        texts = [str(value) for value in raw.get("text", [])]
        for index, text in enumerate(texts):
            if not text.strip():
                continue
            confidence = _as_float(raw.get("conf", []), index, default=_TESSERACT_NO_CONFIDENCE)
            if confidence == _TESSERACT_NO_CONFIDENCE:
                continue
            words.append(
                OcrWord(
                    text=text,
                    confidence=min(
                        max(confidence / _TESSERACT_CONFIDENCE_SCALE, MIN_WORD_CONFIDENCE),
                        MAX_WORD_CONFIDENCE,
                    ),
                    left=_as_float(raw.get("left", []), index),
                    top=_as_float(raw.get("top", []), index),
                    width=_as_float(raw.get("width", []), index),
                    height=_as_float(raw.get("height", []), index),
                    line_number=int(_as_float(raw.get("line_num", []), index)),
                    block_number=int(_as_float(raw.get("block_num", []), index)),
                )
            )
        return words


def _as_float(column: Sequence[object], index: int, *, default: float = 0.0) -> float:
    """One value from a Tesseract output column, or *default*."""
    try:
        return float(str(column[index]))
    except (IndexError, TypeError, ValueError):
        return default


def _join_words(words: Sequence[OcrWord]) -> str:
    """Rebuild page text from words, breaking lines where Tesseract did.

    Joining everything with spaces would collapse a two-column page into
    one run-on paragraph; the line numbers are the only record of where
    the breaks were.
    """
    lines: list[list[str]] = []
    current_key: tuple[int, int] | None = None
    for word in words:
        key = (word.block_number, word.line_number)
        if key != current_key:
            lines.append([])
            current_key = key
        lines[-1].append(word.text)
    return "\n".join(" ".join(line) for line in lines if line)


def _dpi_of(image: object) -> int | None:
    """The image's own resolution, if it recorded one.

    ``None`` rather than a default: a scan with no DPI is one whose
    physical size is unknown, and assuming 300 makes every downstream
    measurement confidently wrong.
    """
    info = getattr(image, "info", {})
    dpi = info.get("dpi") if isinstance(info, dict) else None
    if isinstance(dpi, tuple | list) and dpi:
        try:
            return int(float(dpi[0]))
        except (TypeError, ValueError):
            return None
    return None


__all__ = [
    "MAX_WORD_CONFIDENCE",
    "MIN_WORD_CONFIDENCE",
    "TESSERACT_BINARY",
    "EngineAvailability",
    "OcrEngine",
    "OcrPage",
    "OcrResult",
    "OcrUnavailableError",
    "OcrWord",
    "TesseractEngine",
    "ocr_quality_floor",
]
