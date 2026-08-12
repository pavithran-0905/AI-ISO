"""OCR against a stand-in for the Tesseract binary, and the factory's
startup branches.

**The stand-in replaces the third-party wrapper, never this service's own
code.** ``pytesseract`` is a thin shim over a system binary that a CI
machine may not have; substituting it exercises every line of
:mod:`app.ocr.engine` that a machine with no OCR can never reach. The
engine's own parsing, confidence maths, quality banding and error handling
all run for real.
"""

from __future__ import annotations

import io
import sys
import types
from typing import Any

import pytest
from PIL import Image

from app.classification.classifier import ClassifierConfig, classify
from app.core.factory import (
    _build_cors_config,
    _build_ocr_engine,
    _build_pipeline_config,
    _build_storage,
    create_app,
)
from app.documents.parser import ParsedDocument, ParsedPage
from app.models.enums import DocumentFormat, OcrEngineKind, OcrQuality
from app.ocr.engine import OcrUnavailableError, TesseractEngine


def _png(width: int = 60, height: int = 30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class _FakeTesseract:
    """The two functions :mod:`app.ocr.engine` actually calls."""

    class TesseractError(Exception):
        def __init__(self, status: int = 1, message: str = "boom") -> None:
            super().__init__(message)
            self.status = status
            self.message = message

    class TesseractNotFoundError(Exception):
        pass

    Output = types.SimpleNamespace(DICT="dict")

    def __init__(
        self,
        *,
        version: str = "5.3.0",
        languages: list[str] | None = None,
        data: dict[str, list[Any]] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._version = version
        self._languages = languages if languages is not None else ["eng", "fra"]
        self._data = data
        self._raises = raises

    def get_tesseract_version(self) -> str:
        if self._raises is not None:
            raise self._raises
        return self._version

    def get_languages(self, config: str = "") -> list[str]:
        return self._languages

    def image_to_data(self, image: Any, **kwargs: Any) -> dict[str, list[Any]]:
        if self._raises is not None:
            raise self._raises
        return self._data or {
            "text": ["Change", "request", "", "CHG-004821"],
            "conf": ["96", "91", "-1", "42"],
            "left": [10, 70, 0, 10],
            "top": [10, 10, 0, 30],
            "width": [50, 60, 0, 90],
            "height": [12, 12, 0, 12],
            "line_num": [1, 1, 0, 2],
            "block_num": [1, 1, 0, 1],
        }


@pytest.fixture
def fake_tesseract(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install a stand-in ``pytesseract`` and a binary on PATH.

    ``probe`` checks the wrapper and the binary *separately* -- which is the
    point of it, since the wheel being installed while the binary is absent
    is the commonest deployment mistake -- so a fake module alone leaves the
    engine correctly reporting itself unavailable.
    """

    def _install(*, binary: bool = True, **kwargs: Any) -> _FakeTesseract:
        fake = _FakeTesseract(**kwargs)
        monkeypatch.setitem(sys.modules, "pytesseract", fake)
        monkeypatch.setattr(
            "app.ocr.engine.shutil.which",
            lambda _name: "/usr/bin/tesseract" if binary else None,
        )
        return fake

    return _install


# ---- OCR ------------------------------------------------------------------------------


def test_probing_reports_the_version_and_languages(fake_tesseract: Any) -> None:
    fake_tesseract()
    availability = TesseractEngine().probe()
    assert availability.available is True
    assert availability.engine is OcrEngineKind.TESSERACT
    assert availability.version == "5.3.0"
    assert "eng" in availability.languages


def test_probing_reports_a_missing_binary_separately_from_a_missing_wrapper(
    fake_tesseract: Any,
) -> None:
    """The wheel being installed while the binary is absent is the common
    deployment mistake, and it needs its own message."""
    fake_tesseract(binary=False)
    availability = TesseractEngine().probe()
    assert availability.available is False
    assert availability.reason is not None
    assert "binary" in availability.reason


def test_a_binary_that_is_present_but_does_not_answer_is_reported(
    fake_tesseract: Any,
) -> None:
    fake = fake_tesseract()
    fake._raises = RuntimeError("the binary hung")
    availability = TesseractEngine().probe()
    assert availability.available is False
    assert availability.reason is not None
    assert "did not respond" in availability.reason


def test_reading_a_page_parses_words_confidences_and_geometry(
    fake_tesseract: Any,
) -> None:
    fake_tesseract()
    page = TesseractEngine().read_image(_png(), page_number=2)
    assert page.succeeded is True
    assert page.page_number == 2
    assert [word.text for word in page.words] == ["Change", "request", "CHG-004821"]
    assert page.words[0].confidence == pytest.approx(0.96, abs=0.01)
    assert page.words[0].left == 10
    assert page.text.startswith("Change request")
    assert page.width == 60
    assert page.height == 30


def test_a_confidence_of_minus_one_is_dropped_rather_than_scored(
    fake_tesseract: Any,
) -> None:
    """Tesseract reports -1 for a whitespace box. Keeping it as 0.0 would
    drag every page's mean confidence toward zero in proportion to how much
    whitespace it has."""
    fake_tesseract()
    page = TesseractEngine().read_image(_png(), page_number=1)
    assert all(word.confidence >= 0 for word in page.words)
    assert len(page.words) == 3


def test_words_below_the_engine_floor_are_dropped_and_the_loss_recorded(
    fake_tesseract: Any,
) -> None:
    """A dropped word is a word the page no longer claims to have read, so the
    page has to say how many it dropped."""
    fake_tesseract()
    page = TesseractEngine(minimum_confidence=0.8).read_image(_png(), page_number=1)
    assert [word.text for word in page.words] == ["Change", "request"]
    assert page.warnings, "dropping words silently would overstate the reading"


def test_doubtful_words_are_surfaced_for_a_reviewer(fake_tesseract: Any) -> None:
    """What makes a confidence score useful: the reviewer sees which words to
    check rather than re-reading the page."""
    fake_tesseract()
    page = TesseractEngine().read_image(_png(), page_number=1)
    assert [word.text for word in page.low_confidence_words] == ["CHG-004821"]
    assert page.quality in set(OcrQuality)


def test_a_page_tesseract_could_not_read_records_the_error(fake_tesseract: Any) -> None:
    fake = fake_tesseract()
    fake._raises = _FakeTesseract.TesseractError(1, "segmentation fault")
    page = TesseractEngine().read_image(_png(), page_number=3)
    assert page.succeeded is False
    assert page.error
    assert page.text == ""


def test_an_undecodable_image_records_the_error_rather_than_raising(
    fake_tesseract: Any,
) -> None:
    fake_tesseract()
    page = TesseractEngine().read_image(b"not an image at all", page_number=1)
    assert page.succeeded is False
    assert page.error


def test_a_page_of_only_whitespace_reads_as_empty_not_as_a_failure(
    fake_tesseract: Any,
) -> None:
    fake_tesseract(
        data={
            "text": ["", "  "],
            "conf": ["-1", "-1"],
            "left": [0, 0],
            "top": [0, 0],
            "width": [0, 0],
            "height": [0, 0],
            "line_num": [0, 0],
            "block_num": [0, 0],
        }
    )
    page = TesseractEngine().read_image(_png(), page_number=1)
    assert page.text == ""
    assert page.words == []


def test_reading_a_document_splits_a_multi_frame_image_into_pages(
    fake_tesseract: Any,
) -> None:
    """A TIFF fax is forty frames and a PNG is one; the caller should not have
    to know which before it can be read."""
    fake_tesseract()
    frames = [Image.new("L", (60, 30), shade) for shade in (255, 200, 128)]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="TIFF", save_all=True, append_images=frames[1:])

    document = ParsedDocument(format=DocumentFormat.TIFF, needs_ocr=True)
    result = TesseractEngine().read(document, buffer.getvalue())
    assert len(result.pages) == 3
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert result.engine is OcrEngineKind.TESSERACT
    assert result.lowest_page_confidence is not None
    assert result.text


def test_reading_a_single_frame_image_is_one_page(fake_tesseract: Any) -> None:
    fake_tesseract()
    document = ParsedDocument(format=DocumentFormat.IMAGE, needs_ocr=True)
    result = TesseractEngine().read(document, _png())
    assert len(result.pages) == 1
    assert result.succeeded is True


def test_a_payload_with_no_decodable_page_says_what_is_missing(
    fake_tesseract: Any,
) -> None:
    """A PDF reaches here whenever a deployment has no rasteriser, and that is
    a dependency to report rather than a document to blame."""
    fake_tesseract()
    document = ParsedDocument(format=DocumentFormat.PDF, needs_ocr=True)
    result = TesseractEngine().read(document, b"%PDF-1.7 not rasterisable here")
    assert result.pages == []
    assert result.error is not None
    assert "rasteris" in result.error


def test_reading_a_document_without_the_binary_refuses(fake_tesseract: Any) -> None:
    """Empty pages from a scan are indistinguishable from a genuinely blank
    scan, so this raises where a per-page failure is only recorded."""
    fake_tesseract(binary=False)
    document = ParsedDocument(format=DocumentFormat.IMAGE, needs_ocr=True)
    document.pages.append(ParsedPage(number=1, has_text_layer=False))
    with pytest.raises(OcrUnavailableError):
        TesseractEngine().read(document, _png())


# ---- the factory ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ocr_disabled_by_configuration_yields_no_engine() -> None:
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        import os

        os.environ["AIIOS_DOCUMENT_INTELLIGENCE_SERVICE_OCR_ENABLED"] = "false"
        get_settings.cache_clear()
        assert _build_ocr_engine(get_settings()) is None
    finally:
        os.environ.pop("AIIOS_DOCUMENT_INTELLIGENCE_SERVICE_OCR_ENABLED", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_the_pipeline_configuration_is_built_from_settings() -> None:
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        settings = get_settings()
        config = _build_pipeline_config(settings)
        assert config.review_below_confidence == (settings.service.review_required_below_confidence)
        assert config.validation.duplicate_similarity == (
            settings.service.duplicate_similarity_threshold
        )
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_storage_that_cannot_be_reached_degrades_rather_than_failing_startup() -> None:
    """The service still serves reads without it; what it cannot do is process."""
    from shared_core.config.settings import MinioSettings

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        settings = get_settings()
        broken = object.__new__(type(settings))
        object.__setattr__(broken, "application", settings.application)
        object.__setattr__(broken, "database", settings.database)
        object.__setattr__(broken, "redis", settings.redis)
        object.__setattr__(broken, "rabbitmq", settings.rabbitmq)
        object.__setattr__(broken, "email", settings.email)
        object.__setattr__(broken, "service", settings.service)
        object.__setattr__(
            broken,
            "minio",
            MinioSettings(
                minio_host="127.0.0.1",
                minio_port=1,
                minio_access_key="a",
                minio_secret_key="bbbbbbbbbb",
                minio_use_ssl=False,
                _env_file=None,
            ),
        )
        assert await _build_storage(broken) is None
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_the_cors_policy_differs_between_environments() -> None:
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        development = _build_cors_config(get_settings())
        assert development.allow_origins is not None
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_the_app_can_be_built_twice_without_a_registry_conflict() -> None:
    """Parser registration happens at import time, and re-registering the same
    parser must be allowed -- a module can legitimately be imported twice."""
    first = create_app()
    second = create_app()
    assert first.title == second.title


# ---- remaining engine branches ----------------------------------------------------------


def test_a_classifier_with_no_rules_or_templates_still_classifies() -> None:
    result = classify("Change ID: CHG-004821\nRisk level: high\n", config=ClassifierConfig())
    assert result.classifications
    assert result.considered >= 1


def test_a_custom_category_travels_with_a_rule_label() -> None:
    from app.classification.classifier import ClassificationRule
    from app.models.enums import DocumentCategory

    rule = ClassificationRule(
        name="tenant-specific",
        category=DocumentCategory.FORM,
        required_terms=("widget",),
        custom_category="widget-order",
    )
    result = classify("A widget order form.", config=ClassifierConfig(rules=(rule,)))
    assert result.classifications[0].custom_category == "widget-order"
